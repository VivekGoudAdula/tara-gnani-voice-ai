"""Unit tests for Twilio Media Stream WebSocket gateway and session pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.routers.media_streams import VoiceStreamSession
from app.services.speech.audio_transcoder import encode_twilio_payload, MULAW_FRAME_SIZE_20MS
from app.services.speech.gnani_prisma import PrismaEvent


def run_coroutine(coro):
    """Execute non-suspending coroutine synchronously without Windows socketpair event loop."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_session_initialization():
    """Verify session initializes conversation engine, language, and clients properly."""
    mock_ws = MagicMock()
    session = VoiceStreamSession(mock_ws, mock_mode=True)

    params = {
        "customer_name": "Ramesh",
        "language": "te-IN",
        "bank_name": "Gnani Bank",
        "product_name": "Festive Loan",
        "loan_amount": "2,00,000",
        "interest_rate": "11.25%",
        "communication_id": "comm_123",
    }
    run_coroutine(session.initialize_session(params, mock_mode=True))

    assert session.engine is not None
    assert session.engine.customer_name == "Ramesh"
    assert session.engine.language == "te-in"
    assert session.engine.loan_amount == "2,00,000"
    assert session.prisma is not None
    assert session.timbre is not None
    assert session.communication_id == "comm_123"


def test_barge_in_interruption_sends_clear_event():
    """Verify barge-in while playing sends clear event to Twilio and halts playback."""
    sent_messages = []

    async def mock_send_text(text: str):
        sent_messages.append(text)

    mock_ws = MagicMock()
    mock_ws.send_text = mock_send_text

    session = VoiceStreamSession(mock_ws, mock_mode=True)
    session.stream_sid = "MZ123456789"
    session.is_playing = True

    run_coroutine(session.handle_barge_in())

    assert session.is_interrupted is True
    assert session.barge_in_count == 1
    assert len(sent_messages) == 1

    clear_msg = json.loads(sent_messages[0])
    assert clear_msg.get("event") == "clear"
    assert clear_msg.get("streamSid") == "MZ123456789"


def test_handle_customer_transcript_generates_turn_reply():
    """Verify customer transcript triggers dialogue progression and records history."""
    mock_ws = MagicMock()
    session = VoiceStreamSession(mock_ws, mock_mode=True)
    session.stream_sid = "MZtest_sid"
    params = {"customer_name": "Sunita", "language": "hi-IN"}
    run_coroutine(session.initialize_session(params, mock_mode=True))

    spoken_texts = []

    async def mock_speak_text(text: str):
        spoken_texts.append(text)

    session.speak_text = mock_speak_text

    event = PrismaEvent(
        event_type="transcript",
        transcript="Haan, mujhe loan chahiye",
        is_final=True,
        confidence=0.97,
        language="hi-IN",
    )

    run_coroutine(session.handle_customer_transcript(event))

    assert len(session.transcripts) >= 2
    assert session.transcripts[0]["speaker"] == "customer"
    assert session.transcripts[0]["text"] == "Haan, mujhe loan chahiye"
    assert session.transcripts[1]["speaker"] == "agent"
    assert len(session.transcripts[1]["text"]) > 0
    assert len(spoken_texts) == 1
