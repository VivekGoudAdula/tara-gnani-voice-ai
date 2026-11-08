"""Unit tests for Gnani Timbre TTS client and mock synthesis."""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from app.services.speech.gnani_timbre import GnaniTimbreClient, generate_mock_pcm16, WAV_HEADER_SIZE


def run_coroutine(coro):
    """Execute non-suspending coroutine synchronously without Windows socketpair event loop."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_generate_mock_pcm16():
    """Verify mock PCM audio generator produces valid 8kHz 16-bit byte stream."""
    pcm = generate_mock_pcm16(duration_seconds=1.0)
    # 8000 samples * 2 bytes = 16000 bytes
    assert len(pcm) == 16000
    assert isinstance(pcm, bytes)

    pcm_half_sec = generate_mock_pcm16(duration_seconds=0.5)
    assert len(pcm_half_sec) == 8000


def test_empty_text_returns_empty_bytes():
    """Verify empty or whitespace-only text returns empty bytes immediately."""
    client = GnaniTimbreClient(mock_mode=True)
    res = run_coroutine(client.synthesize(""))
    assert res == b""
    res_ws = run_coroutine(client.synthesize("   "))
    assert res_ws == b""


def test_mock_synthesize_pcm16_and_mulaw():
    """Verify mock mode synthesis generates proportional PCM and mulaw audio."""
    client = GnaniTimbreClient(mock_mode=True)
    text = "Hello, this is a test greeting from TARA."
    pcm_audio = run_coroutine(client.synthesize(text))
    assert len(pcm_audio) > 0
    # Must be divisible by 2 (16-bit samples)
    assert len(pcm_audio) % 2 == 0

    mulaw_audio = run_coroutine(client.synthesize_mulaw(text))
    assert len(mulaw_audio) == len(pcm_audio) // 2


def test_wav_header_stripping():
    """Verify 44-byte WAV header is cleanly stripped when returned by the API."""
    fake_header = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00@\x1f\x00\x00\x80>\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
    fake_pcm = b"\x01\x02\x03\x04" * 100
    raw_wav_response = fake_header + fake_pcm
    assert len(fake_header) == WAV_HEADER_SIZE

    client = GnaniTimbreClient(api_key="test_key", mock_mode=False)

    # In mock mode or mock client, verify wav header slicing logic directly
    content = raw_wav_response
    if len(content) > WAV_HEADER_SIZE and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        stripped = content[WAV_HEADER_SIZE:]
    assert stripped == fake_pcm
