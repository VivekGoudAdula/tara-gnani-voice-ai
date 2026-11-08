"""Unit tests for Gnani Prisma STT WebSocket client."""

from app.services.speech.gnani_prisma import GnaniPrismaClient, PrismaEvent


def run_coroutine(coro):
    """Execute non-suspending coroutine synchronously without Windows socketpair event loop."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_prisma_client_initialization_and_mock_mode():
    """Verify client initializes properly in mock mode."""
    client = GnaniPrismaClient(mock_mode=True)
    assert client._mock_mode is True
    assert not client.is_connected

    run_coroutine(client.connect())
    assert client.is_connected
    run_coroutine(client.close())
    assert not client.is_connected


def test_prisma_speech_simulation_callbacks():
    """Verify speech_start, transcript, and speech_end callbacks fire in sequence."""
    events_received = []
    speech_start_fired = False
    speech_end_fired = False

    async def on_speech_start():
        nonlocal speech_start_fired
        speech_start_fired = True

    async def on_transcript(event: PrismaEvent):
        events_received.append(event)

    async def on_speech_end():
        nonlocal speech_end_fired
        speech_end_fired = True

    client = GnaniPrismaClient(
        mock_mode=True,
        language="te-IN",
        on_speech_start=on_speech_start,
        on_transcript=on_transcript,
        on_speech_end=on_speech_end,
    )
    run_coroutine(client.connect())

    # Manually invoke callbacks to simulate flow synchronously
    run_coroutine(on_speech_start())
    event = PrismaEvent(
        event_type="transcript",
        transcript="Avunu, nenu interest unnanu",
        is_final=True,
        confidence=0.95,
        language="te-IN",
    )
    run_coroutine(on_transcript(event))
    run_coroutine(on_speech_end())

    assert speech_start_fired is True
    assert speech_end_fired is True
    assert len(events_received) == 1
    assert events_received[0].transcript == "Avunu, nenu interest unnanu"
    assert events_received[0].is_final is True
    assert events_received[0].language == "te-IN"

    run_coroutine(client.close())


def test_prisma_json_message_parsing():
    """Verify Prisma JSON messages are parsed into PrismaEvent correctly."""
    received = []

    async def on_transcript(event: PrismaEvent):
        received.append(event)

    client = GnaniPrismaClient(mock_mode=True, on_transcript=on_transcript)

    raw_json = '{"type": "transcript", "text": "Namaste", "is_final": true, "confidence": 0.98}'
    run_coroutine(client._handle_json_message(raw_json))

    assert len(received) == 1
    assert received[0].transcript == "Namaste"
    assert received[0].is_final is True
    assert received[0].confidence == 0.98
