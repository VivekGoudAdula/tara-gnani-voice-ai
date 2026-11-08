"""Gnani Prisma v3.0 Speech-to-Text streaming WebSocket client."""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional
from pydantic import BaseModel, Field

try:
    import websockets
    try:
        from websockets.asyncio.client import ClientConnection as WebSocketClientProtocol
    except ImportError:
        from websockets.client import WebSocketClientProtocol  # type: ignore
except ImportError:
    websockets = None  # type: ignore
    WebSocketClientProtocol = Any  # type: ignore


from app.core.config import settings
from app.services.speech.audio_transcoder import resample_pcm16
from app.services.speech.language import normalize_language_code


logger = logging.getLogger("tara.speech.prisma")


class PrismaEvent(BaseModel):
    """Normalized Speech-to-Text event emitted by Gnani Prisma."""

    event_type: str = "transcript"  # "speech_start", "transcript", "speech_end", "error"
    transcript: str = ""
    is_final: bool = False
    confidence: float = 1.0
    language: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)


class GnaniPrismaClient:
    """
    Asynchronous streaming client for Gnani Prisma v3.0 STT WebSocket service.

    Streams 8kHz linear PCM16 audio bytes and receives real-time transcription events.
    Supports callbacks for speech_start (barge-in trigger), transcript updates, and completion.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        sample_rate: int = 8000,
        mock_mode: Optional[bool] = None,
        connect_timeout: float = 5.0,
        on_speech_start: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        on_transcript: Optional[Callable[[PrismaEvent], Coroutine[Any, Any, None]]] = None,
        on_speech_end: Optional[Callable[[], Coroutine[Any, Any, None]]] = None,
        on_error: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.gnani_api_key
        self.url = url or settings.gnani_prisma_url
        self.model = model or settings.gnani_prisma_model
        self.language = normalize_language_code(language or settings.voice_default_language)
        self.sample_rate = sample_rate
        self.connect_timeout = connect_timeout

        self.on_speech_start = on_speech_start
        self.on_transcript = on_transcript
        self.on_speech_end = on_speech_end
        self.on_error = on_error

        self._ws: Optional[WebSocketClientProtocol] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._is_connected = False
        self._mock_mode = mock_mode if mock_mode is not None else (not bool(self.api_key))

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket connection is active."""
        return self._is_connected

    async def connect(self) -> None:
        """
        Open WebSocket connection to Gnani Prisma STT and initiate listening loop.
        If mock_mode is True or api_key is missing, enters simulation mode.
        """
        if self._mock_mode:
            logger.info("Gnani Prisma running in mock/offline mode")
            self._is_connected = True
            return

        if websockets is None:
            raise RuntimeError("websockets library is required to connect to Gnani Prisma")

        query_params = f"?model={self.model}&language={self.language}&sample_rate={self.sample_rate}&encoding=pcm16"
        target_url = f"{self.url}{query_params}"
        auth_headers = {
            "X-API-Key-ID": self.api_key,
            "language_code": self.language,
        }

        # Adapt dynamically between websockets v14+ (additional_headers) and legacy (extra_headers)
        connect_kwargs: dict[str, Any] = {}
        try:
            import inspect
            sig = inspect.signature(websockets.connect)
            if "additional_headers" in sig.parameters:
                connect_kwargs["additional_headers"] = auth_headers
            else:
                connect_kwargs["extra_headers"] = auth_headers
        except Exception:
            connect_kwargs["additional_headers"] = auth_headers

        logger.info("Connecting to Gnani Prisma STT at %s", target_url)
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(target_url, **connect_kwargs),
                timeout=self.connect_timeout,
            )

            self._is_connected = True
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.info("Connected to Gnani Prisma STT successfully")
        except Exception as exc:
            logger.error("Failed to connect to Gnani Prisma STT: %s", exc)
            self._is_connected = False
            if self.on_error:
                await self.on_error(str(exc))
            raise

    async def send_audio(self, pcm16_bytes: bytes) -> None:
        """
        Stream raw 8kHz linear PCM16 audio bytes to Prisma STT.

        Args:
            pcm16_bytes: Binary linear PCM chunk.
        """
        if not pcm16_bytes or not self._is_connected:
            return

        if self._mock_mode:
            # In mock mode, audio chunks are safely accepted
            return

        if self._ws:
            try:
                # Upsample 8kHz telephony audio to 16kHz for Prisma VAD and acoustic models
                audio_to_send = (
                    resample_pcm16(pcm16_bytes, 8000, 16000)
                    if self.sample_rate == 8000
                    else pcm16_bytes
                )
                await self._ws.send(audio_to_send)
            except Exception as exc:
                logger.error("Error sending audio to Gnani Prisma: %s", exc)
                if self.on_error:
                    await self.on_error(str(exc))


    async def _listen_loop(self) -> None:
        """Background coroutine receiving and parsing streaming events from Prisma."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                if isinstance(message, str):
                    await self._handle_json_message(message)
                elif isinstance(message, bytes):
                    logger.debug("Received unexpected binary frame from Prisma STT: %d bytes", len(message))
        except asyncio.CancelledError:
            logger.debug("Prisma listen loop cancelled")
        except Exception as exc:
            logger.error("Error in Prisma STT listener loop: %s", exc)
            if self.on_error:
                await self.on_error(str(exc))
        finally:
            self._is_connected = False

    async def _handle_json_message(self, raw_str: str) -> None:
        """Parse JSON response from Prisma and trigger corresponding callbacks."""
        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError:
            logger.warning("Unparseable JSON received from Prisma STT: %s", raw_str)
            return

        # Prisma message schema normalization
        event_type = data.get("type") or data.get("event") or "transcript"
        transcript_text = data.get("text") or data.get("transcript") or ""
        is_final = bool(data.get("is_final") or data.get("final", False))
        confidence = float(data.get("confidence", 1.0))
        lang = data.get("language") or self.language

        event = PrismaEvent(
            event_type=event_type,
            transcript=transcript_text,
            is_final=is_final,
            confidence=confidence,
            language=lang,
            raw=data,
        )

        if event_type in ("speech_start", "vad_speech_start"):
            logger.debug("Prisma detected speech_start (user speaking)")
            if self.on_speech_start:
                await self.on_speech_start()

        elif event_type in ("speech_end", "vad_speech_end"):
            logger.debug("Prisma detected speech_end")
            if self.on_speech_end:
                await self.on_speech_end()

        elif event_type == "error":
            err_msg = data.get("message", "Unknown Prisma error")
            logger.error("Prisma STT error event: %s", err_msg)
            if self.on_error:
                await self.on_error(err_msg)

        else:
            # Transcript event
            if transcript_text and self.on_transcript:
                await self.on_transcript(event)

    async def simulate_user_speech(self, text: str, is_final: bool = True) -> None:
        """
        Simulation helper for testing and mock environments.
        Simulates speech_start -> transcript -> speech_end.
        """
        if self.on_speech_start:
            await self.on_speech_start()
        await asyncio.sleep(0.01)

        event = PrismaEvent(
            event_type="transcript",
            transcript=text,
            is_final=is_final,
            confidence=0.95,
            language=self.language,
            raw={"simulated": True, "text": text},
        )
        if self.on_transcript:
            await self.on_transcript(event)

        if is_final and self.on_speech_end:
            await self.on_speech_end()

    async def close(self) -> None:
        """Gracefully terminate Prisma STT WebSocket connection and cancel listener task."""
        self._is_connected = False
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.debug("Error while closing Prisma WebSocket: %s", exc)
            self._ws = None
        logger.info("Gnani Prisma STT client disconnected")
