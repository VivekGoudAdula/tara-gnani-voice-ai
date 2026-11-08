"""Audio transcoding utilities for Twilio Media Streams (8kHz mulaw) and Gnani AI (8kHz linear PCM16)."""

import base64
import logging
from typing import List

try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop  # type: ignore
    except ImportError:
        audioop = None  # type: ignore

logger = logging.getLogger("tara.speech.transcoder")

# Standard frame constants for 8000 Hz mono audio
TWILIO_SAMPLE_RATE = 8000
PCM_SAMPLE_WIDTH = 2  # 16-bit linear PCM (2 bytes per sample)
MULAW_SAMPLE_WIDTH = 1  # 8-bit mulaw (1 byte per sample)

# 20ms audio frame sizes
MULAW_FRAME_SIZE_20MS = 160  # 8000 samples/sec * 0.02 sec * 1 byte = 160 bytes
PCM_FRAME_SIZE_20MS = 320  # 8000 samples/sec * 0.02 sec * 2 bytes = 320 bytes


def mulaw_to_pcm16(mulaw_bytes: bytes) -> bytes:
    """
    Convert 8kHz G.711 mu-law audio bytes into signed 16-bit linear PCM (little-endian).

    Args:
        mulaw_bytes: Raw 8-bit mu-law audio bytes.

    Returns:
        16-bit linear PCM bytes at identical sample rate (8000 Hz).
    """
    if not mulaw_bytes:
        return b""
    if audioop is None:
        raise RuntimeError("audioop module not available for audio transcoding")
    return audioop.ulaw2lin(mulaw_bytes, PCM_SAMPLE_WIDTH)


def pcm16_to_mulaw(pcm_bytes: bytes) -> bytes:
    """
    Convert signed 16-bit linear PCM audio bytes into 8-bit G.711 mu-law audio.

    Args:
        pcm_bytes: 16-bit linear PCM bytes (8000 Hz, mono).

    Returns:
        8-bit mu-law audio bytes at identical sample rate (8000 Hz).
    """
    if not pcm_bytes:
        return b""
    if audioop is None:
        raise RuntimeError("audioop module not available for audio transcoding")
    # Ensure whole number of 2-byte frames
    if len(pcm_bytes) % PCM_SAMPLE_WIDTH != 0:
        pcm_bytes = pcm_bytes[:-(len(pcm_bytes) % PCM_SAMPLE_WIDTH)]
    return audioop.lin2ulaw(pcm_bytes, PCM_SAMPLE_WIDTH)


def resample_pcm16(pcm_bytes: bytes, in_rate: int, out_rate: int) -> bytes:
    """
    Resample 16-bit linear PCM audio between sample rates (e.g. 24kHz -> 8kHz or 8kHz -> 16kHz).

    Args:
        pcm_bytes: 16-bit linear PCM bytes.
        in_rate: Source sampling frequency in Hz (e.g. 24000 or 8000).
        out_rate: Destination sampling frequency in Hz (e.g. 8000 or 16000).

    Returns:
        Resampled 16-bit linear PCM bytes.
    """
    if not pcm_bytes:
        return b""
    if in_rate == out_rate:
        return pcm_bytes
    if audioop is None:
        raise RuntimeError("audioop module not available for audio rate conversion")
    # Ensure whole number of 2-byte frames
    if len(pcm_bytes) % PCM_SAMPLE_WIDTH != 0:
        pcm_bytes = pcm_bytes[:-(len(pcm_bytes) % PCM_SAMPLE_WIDTH)]
    if not pcm_bytes:
        return b""
    resampled, _ = audioop.ratecv(pcm_bytes, PCM_SAMPLE_WIDTH, 1, in_rate, out_rate, None)
    return resampled




def decode_twilio_payload(base64_payload: str) -> bytes:
    """
    Decode a base64 encoded audio payload received from a Twilio Media Stream.

    Args:
        base64_payload: Base64 string from Twilio media event.

    Returns:
        Raw 8-bit mu-law audio bytes.
    """
    if not base64_payload:
        return b""
    return base64.b64decode(base64_payload)


def encode_twilio_payload(mulaw_bytes: bytes) -> str:
    """
    Encode raw 8-bit mu-law audio bytes into a base64 string for Twilio Media Stream transmission.

    Args:
        mulaw_bytes: Raw 8-bit mu-law audio bytes.

    Returns:
        Base64 encoded ASCII string.
    """
    if not mulaw_bytes:
        return ""
    return base64.b64encode(mulaw_bytes).decode("ascii")


def chunk_audio(audio_bytes: bytes, chunk_size: int = MULAW_FRAME_SIZE_20MS) -> List[bytes]:
    """
    Slice audio byte buffer into uniform chunks for streaming packet delivery.

    Args:
        audio_bytes: Continuous audio byte buffer.
        chunk_size: Size of each chunk in bytes (default 160 bytes for 20ms mulaw).

    Returns:
        List of audio byte slices.
    """
    if not audio_bytes:
        return []
    return [audio_bytes[i : i + chunk_size] for i in range(0, len(audio_bytes), chunk_size)]


def calculate_rms_energy(pcm_bytes: bytes) -> int:
    """
    Calculate the Root Mean Square (RMS) energy of a 16-bit linear PCM audio fragment.

    Args:
        pcm_bytes: 16-bit linear PCM bytes.

    Returns:
        Integer RMS amplitude value (0 to 32767).
    """
    if not pcm_bytes or audioop is None:
        return 0
    # Ensure whole number of 2-byte frames
    if len(pcm_bytes) % PCM_SAMPLE_WIDTH != 0:
        pcm_bytes = pcm_bytes[:-(len(pcm_bytes) % PCM_SAMPLE_WIDTH)]
    if not pcm_bytes:
        return 0
    return audioop.rms(pcm_bytes, PCM_SAMPLE_WIDTH)


