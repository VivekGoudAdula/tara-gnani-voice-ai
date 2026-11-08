"""Twilio Media Streams WebSocket gateway routing audio between Twilio and Gnani Voice AI."""

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.db import get_db
from app.services.speech.language import normalize_language_code
from app.services.conversation.models import AgentTurnResponse
from app.services.conversation.orchestrator import ConversationOrchestrator
from app.services.conversation.voice_response import TurnResponse, VoiceResponseEngine
from app.services.speech.audio_transcoder import (
    chunk_audio,
    decode_twilio_payload,
    encode_twilio_payload,
    mulaw_to_pcm16,
    MULAW_FRAME_SIZE_20MS,
)
from app.services.speech.gnani_prisma import GnaniPrismaClient, PrismaEvent
from app.services.speech.gnani_timbre import GnaniTimbreClient

logger = logging.getLogger("tara.voice.media_stream")
router = APIRouter(tags=["voice_streaming"])


class VoiceStreamSession:
    """
    Manages the state and real-time audio pipeline for an active phone call session.
    """

    def __init__(self, websocket: WebSocket, mock_mode: Optional[bool] = None):
        self.ws = websocket
        self.mock_mode = mock_mode
        self.stream_sid: Optional[str] = None
        self.call_sid: Optional[str] = None
        self.communication_id: Optional[str] = None
        self.tenant_id: Optional[str] = None

        self.engine: Optional[VoiceResponseEngine] = None
        self.orchestrator: Optional[ConversationOrchestrator] = None
        self.prisma: Optional[GnaniPrismaClient] = None
        self.timbre: Optional[GnaniTimbreClient] = None

        self.is_playing = False
        self.is_interrupted = False
        self.barge_in_count = 0
        self.transcripts: List[Dict[str, str]] = []
        self._playback_lock = asyncio.Lock()

    async def initialize_session(self, custom_params: Dict[str, str], mock_mode: Optional[bool] = None) -> None:
        """Initialize conversation engine, Prisma STT, and Timbre TTS from stream parameters."""
        effective_mock = mock_mode if mock_mode is not None else self.mock_mode
        customer_name = custom_params.get("customer_name", "Customer")
        raw_language = custom_params.get("language", settings.voice_default_language)
        language = normalize_language_code(raw_language)
        bank_name = custom_params.get("bank_name", "Gnani Bank")
        product_name = custom_params.get("product_name", "Personal Loan")
        loan_amount = custom_params.get("loan_amount", "5,00,000")
        interest_rate = custom_params.get("interest_rate", "10.49%")
        self.communication_id = custom_params.get("communication_id")
        self.tenant_id = custom_params.get("tenant_id")

        self.engine = VoiceResponseEngine(
            customer_name=customer_name,
            bank_name=bank_name,
            product_name=product_name,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            language=language,
        )

        # Initialize Phase 3 Intelligent Conversation Orchestrator
        try:
            db = get_db()
            self.orchestrator = ConversationOrchestrator(
                db=db,
                tenant_id=self.tenant_id or "default_tenant",
                mock_mode=effective_mock,
            )
            await self.orchestrator.initialize(
                custom_params=custom_params,
                session_id=self.stream_sid or "stream_session",
                call_sid=self.call_sid,
            )
        except Exception as exc:
            logger.warning("Could not initialize full ConversationOrchestrator: %s", exc)

        self.timbre = GnaniTimbreClient(default_language=language, mock_mode=effective_mock)

        # Initialize Prisma STT with barge-in callback
        self.prisma = GnaniPrismaClient(
            language=language,
            mock_mode=effective_mock,
            on_speech_start=self.handle_barge_in,
            on_transcript=self.handle_customer_transcript,
        )
        await self.prisma.connect()


        # Update initial in-progress status in DB if communication_id exists
        await self._persist_status_update("IN_PROGRESS")

    async def handle_barge_in(self) -> None:
        """
        Triggered when customer begins speaking while agent audio may be playing.
        Immediately sends Twilio 'clear' event to flush buffered audio on the handset.
        """
        if self.is_playing and self.stream_sid:
            logger.info("Barge-in detected on stream %s. Clearing Twilio audio buffer.", self.stream_sid)
            self.is_interrupted = True
            self.barge_in_count += 1
            clear_event = {
                "event": "clear",
                "streamSid": self.stream_sid,
            }
            try:
                await self.ws.send_text(json.dumps(clear_event))
            except Exception as exc:
                logger.warning("Failed to send clear event to Twilio: %s", exc)

    async def handle_customer_transcript(self, event: PrismaEvent) -> None:
        """
        Process recognized customer speech turn and synthesize dialogue response.
        """
        if not event.is_final or not event.transcript.strip():
            return

        customer_text = event.transcript.strip()
        logger.info("Customer transcript received on stream %s: '%s'", self.stream_sid, customer_text)
        self.transcripts.append({"speaker": "customer", "text": customer_text})

        spoken_reply = ""
        is_complete = False

        # 1. Process via Phase 3 Intelligent Conversation Orchestrator
        if self.orchestrator:
            try:
                orch_resp: AgentTurnResponse = await self.orchestrator.process_customer_speech(customer_text)
                spoken_reply = orch_resp.spoken_text
                is_complete = orch_resp.is_call_complete
            except Exception as exc:
                logger.error("Orchestrator error, falling back to rule engine: %s", exc)

        # 2. Fallback to rule engine if orchestrator produced no spoken reply
        if not spoken_reply and self.engine:
            turn_response: TurnResponse = self.engine.process_customer_turn(customer_text)
            spoken_reply = turn_response.response_text
            is_complete = turn_response.is_call_complete

        if spoken_reply:
            self.transcripts.append({"speaker": "agent", "text": spoken_reply})
            await self.speak_text(spoken_reply)

        if is_complete:
            logger.info("Call concluded on stream %s", self.stream_sid)

    async def speak_text(self, text: str) -> None:
        """
        Synthesize text response to 8kHz mu-law and stream paced audio chunks to Twilio.
        """
        if not text or not self.timbre or not self.stream_sid:
            return

        async with self._playback_lock:
            self.is_playing = True
            self.is_interrupted = False

            try:
                mulaw_audio = await self.timbre.synthesize_mulaw(
                    text=text,
                    language=self.engine.language if self.engine else None,
                )
                if not mulaw_audio:
                    return

                # Stream in 80ms frames (640 bytes) with 400ms pre-buffering to prevent jitter underrun
                chunk_size = 640
                chunks = chunk_audio(mulaw_audio, chunk_size=chunk_size)
                start_time = time.perf_counter()

                for idx, chunk in enumerate(chunks):
                    if self.is_interrupted:
                        logger.info("Playback interrupted by customer barge-in. Halting audio stream.")
                        break

                    b64_payload = encode_twilio_payload(chunk)
                    media_event = {
                        "event": "media",
                        "streamSid": self.stream_sid,
                        "media": {
                            "payload": b64_payload,
                        },
                    }
                    try:
                        await self.ws.send_text(json.dumps(media_event))
                    except (WebSocketDisconnect, RuntimeError):
                        logger.debug("Client disconnected during playback stream")
                        break

                    # Frame duration in seconds (8000 bytes/sec for G.711 mu-law)
                    frame_dur = len(chunk) / 8000.0
                    # Maintain ~400ms buffer ahead of real-time playout
                    target_time = start_time + max(0.0, ((idx + 1) * frame_dur) - 0.400)
                    now = time.perf_counter()
                    sleep_needed = target_time - now
                    if sleep_needed > 0.020:
                        await asyncio.sleep(sleep_needed)
                    else:
                        # Cooperative yield to ensure event loop receives inbound customer audio
                        await asyncio.sleep(0.001)

            except Exception as exc:
                logger.error("Error during speech playback to Twilio: %s", exc)
            finally:
                self.is_playing = False

    async def play_initial_greeting(self) -> None:
        """Generate and play initial greeting at the start of the call."""
        try:
            if self.orchestrator:
                greeting = self.orchestrator.get_initial_greeting()
            elif self.engine:
                greeting = self.engine.generate_initial_greeting()
            else:
                greeting = "నమస్కారం, నేను తారా మాట్లాడుతున్నాను."

            logger.info("Playing initial greeting on stream %s: '%s'", self.stream_sid, greeting)
            self.transcripts.append({"speaker": "agent", "text": greeting})
            await self.speak_text(greeting)
        except Exception as exc:
            logger.error("Error in initial greeting playback: %s", exc)

    def _build_comm_query(self) -> Optional[Dict[str, Any]]:
        """Construct database query to locate communication record by ID or CallSid."""
        if self.communication_id:
            cid = ObjectId(self.communication_id) if ObjectId.is_valid(self.communication_id) else self.communication_id
            return {"_id": cid}
        if self.call_sid:
            return {"provider_ref": self.call_sid}
        return None

    async def _persist_status_update(self, new_status: str) -> None:
        """Safely record status transition in MongoDB communications collection."""
        query = self._build_comm_query()
        if not query:
            return
        try:
            db = get_db()
            now_utc = datetime.now(timezone.utc)
            await db.communications.update_one(
                query,
                {"$set": {"status": new_status, "updated_at": now_utc}},
            )
        except Exception as exc:
            logger.debug("Database update skipped or failed: %s", exc)

    async def _persist_call_outcome(self, turn_resp: Optional[TurnResponse] = None) -> None:
        """Persist final conversation outcome, interest level, and turn history."""
        query = self._build_comm_query()
        if not query:
            return
        try:
            db = get_db()
            now_utc = datetime.now(timezone.utc)
            interest = turn_resp.interest_level if turn_resp else (self.engine.detected_interest if self.engine else "unknown")
            intent = turn_resp.intent if turn_resp else "session_closed"
            turns = turn_resp.turn_index if turn_resp else (self.engine.turn_count if self.engine else len(self.transcripts))

            outcome_data = {
                "interest_level": interest,
                "intent": intent,
                "turn_count": turns,
                "barge_in_count": self.barge_in_count,
                "transcripts": self.transcripts,
                "completed_at": now_utc,
            }
            await db.communications.update_one(
                query,
                {"$set": {
                    "outcome": outcome_data,
                    "updated_at": now_utc,
                }},
            )
        except Exception as exc:
            logger.debug("Outcome persistence skipped or failed: %s", exc)

    async def close(self) -> None:
        """Clean up streaming session resources and STT connections."""
        if self.orchestrator:
            try:
                await self.orchestrator.finalize_session()
            except Exception as exc:
                logger.debug("Orchestrator finalization error: %s", exc)
        elif self.transcripts:
            await self._persist_call_outcome(None)

        if self.prisma:
            await self.prisma.close()
        if self.timbre:
            await self.timbre.close()
        logger.info("Voice stream session closed for stream %s", self.stream_sid)



@router.websocket("/voice/stream")
async def handle_twilio_voice_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint receiving bidirectional Twilio Media Streams.

    Exchanges 8kHz G.711 mu-law audio packets, transcribing inbound customer audio via
    Gnani Prisma STT, generating multi-turn dialogue responses, and streaming synthesized
    speech back to the customer via Gnani Timbre TTS.
    """
    await websocket.accept()
    logger.info("New WebSocket connection accepted on /api/voice/stream")
    session = VoiceStreamSession(websocket)

    try:
        while True:
            raw_message = await websocket.receive_text()
            if not raw_message:
                continue

            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                logger.warning("Non-JSON frame received on voice stream: %s", raw_message[:100])
                continue

            event_type = data.get("event")

            if event_type == "connected":
                logger.info("Twilio media stream connected (protocol: %s)", data.get("protocol"))

            elif event_type == "start":
                start_data = data.get("start", {})
                session.stream_sid = data.get("streamSid") or start_data.get("streamSid")
                session.call_sid = start_data.get("callSid")
                custom_params = start_data.get("customParameters", {})

                logger.info(
                    "Stream started: StreamSid=%s, CallSid=%s, Params=%s",
                    session.stream_sid,
                    session.call_sid,
                    custom_params,
                )

                # Initialize voice pipeline for this call session
                await session.initialize_session(custom_params)

                # Immediately play personalized introductory greeting
                asyncio.create_task(session.play_initial_greeting())

            elif event_type == "media":
                media_data = data.get("media", {})
                b64_payload = media_data.get("payload")

                if b64_payload and session.prisma and session.prisma.is_connected:
                    # Transcode 8kHz mulaw audio packet to 8kHz linear PCM16
                    mulaw_bytes = decode_twilio_payload(b64_payload)
                    pcm16_bytes = mulaw_to_pcm16(mulaw_bytes)
                    await session.prisma.send_audio(pcm16_bytes)

            elif event_type == "stop":
                logger.info("Twilio stream stop event received for stream %s", session.stream_sid)
                break

    except WebSocketDisconnect:
        logger.info("Twilio Media Stream disconnected by client (StreamSid: %s)", session.stream_sid)
    except Exception as exc:
        logger.error("Unhandled exception in voice stream handler: %s", exc, exc_info=True)
    finally:
        await session.close()
