"""Unit tests for audio transcoding between 8kHz mulaw and 8kHz PCM16."""

import base64
import pytest
from app.services.speech.audio_transcoder import (
    calculate_rms_energy,
    chunk_audio,
    decode_twilio_payload,
    encode_twilio_payload,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
    MULAW_FRAME_SIZE_20MS,
    PCM_FRAME_SIZE_20MS,
)


def test_mulaw_to_pcm16_conversion():
    """Verify 8kHz mulaw converts to 16-bit PCM with expected 2x byte size."""
    # 160 bytes of mulaw (20ms) should become 320 bytes of 16-bit linear PCM
    mulaw_data = b"\xff" * MULAW_FRAME_SIZE_20MS
    pcm_data = mulaw_to_pcm16(mulaw_data)
    assert len(pcm_data) == PCM_FRAME_SIZE_20MS
    assert isinstance(pcm_data, bytes)


def test_pcm16_to_mulaw_conversion():
    """Verify 16-bit linear PCM converts to mulaw with expected 0.5x byte size."""
    # 320 bytes of PCM16 (20ms) should become 160 bytes of mulaw
    pcm_data = b"\x00\x00" * 160
    mulaw_data = pcm16_to_mulaw(pcm_data)
    assert len(mulaw_data) == MULAW_FRAME_SIZE_20MS
    assert isinstance(mulaw_data, bytes)


def test_roundtrip_transcoding():
    """Verify audio roundtrips without crashing or unexpected length changes."""
    original_mulaw = bytes([i % 256 for i in range(320)])
    pcm = mulaw_to_pcm16(original_mulaw)
    assert len(pcm) == 640
    recon_mulaw = pcm16_to_mulaw(pcm)
    assert len(recon_mulaw) == len(original_mulaw)


def test_twilio_payload_encoding_and_decoding():
    """Verify base64 decoding and encoding for Twilio media stream payloads."""
    raw_audio = b"\x80\x81\x82\x83\x84\x85"
    b64_str = encode_twilio_payload(raw_audio)
    assert b64_str == base64.b64encode(raw_audio).decode("ascii")

    decoded = decode_twilio_payload(b64_str)
    assert decoded == raw_audio


def test_empty_payloads():
    """Verify empty inputs safely return empty outputs without raising exceptions."""
    assert mulaw_to_pcm16(b"") == b""
    assert pcm16_to_mulaw(b"") == b""
    assert decode_twilio_payload("") == b""
    assert encode_twilio_payload(b"") == ""
    assert chunk_audio(b"") == []
    assert calculate_rms_energy(b"") == 0


def test_odd_byte_length_handling():
    """Verify odd byte lengths are safely truncated to whole 16-bit frames without crashing."""
    odd_pcm = b"\x00\x10\x00\x20\x00"  # 5 bytes (2.5 frames)
    # Should safely convert 4 bytes into 2 mulaw bytes rather than raising audioop.error
    mulaw = pcm16_to_mulaw(odd_pcm)
    assert len(mulaw) == 2
    assert isinstance(mulaw, bytes)

    # RMS energy calculation should also handle odd bytes cleanly
    energy = calculate_rms_energy(odd_pcm)
    assert energy >= 0



def test_chunking_audio():
    """Verify chunk_audio cleanly slices audio buffers into uniform frame sizes."""
    data = b"\xaa" * 400
    chunks = chunk_audio(data, chunk_size=160)
    assert len(chunks) == 3
    assert len(chunks[0]) == 160
    assert len(chunks[1]) == 160
    assert len(chunks[2]) == 80


def test_rms_energy_calculation():
    """Verify RMS energy calculation correctly reflects silence and non-silent audio."""
    silence = b"\x00\x00" * 160
    assert calculate_rms_energy(silence) == 0

    # Non-silent 16-bit PCM signal
    signal = b"\x00\x10" * 160
    energy = calculate_rms_energy(signal)
    assert energy > 0

