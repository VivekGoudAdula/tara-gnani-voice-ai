"""Gnani Timbre v2.5 Text-to-Speech HTTP client."""

import logging
import math
from typing import Optional
import httpx

from app.core.config import settings
from app.services.speech.audio_transcoder import pcm16_to_mulaw
from app.services.speech.language import normalize_language_code

logger = logging.getLogger("tara.speech.timbre")

DEFAULT_SAMPLE_RATE = 8000
WAV_HEADER_SIZE = 44


def generate_mock_pcm16(duration_seconds: float = 1.0, frequency_hz: float = 440.0) -> bytes:
    """
    Generate synthetic 8kHz 16-bit linear PCM audio for offline simulation and test environments.

    Args:
        duration_seconds: Audio duration in seconds.
        frequency_hz: Sine wave frequency in Hz (default 440 Hz standard A tone).

    Returns:
        Signed 16-bit little-endian PCM bytes at 8000 Hz.
    """
    sample_count = int(DEFAULT_SAMPLE_RATE * duration_seconds)
    pcm_bytes = bytearray()
    for i in range(sample_count):
        # Generate low-amplitude sine wave to prevent clipping
        sample_val = int(3000.0 * math.sin(2.0 * math.pi * frequency_hz * i / DEFAULT_SAMPLE_RATE))
        pcm_bytes.extend(sample_val.to_bytes(2, byteorder="little", signed=True))
    return bytes(pcm_bytes)


class GnaniTimbreClient:
    """
    Asynchronous client for Gnani Timbre v2.5 Text-to-Speech inference API.

    Converts input text in supported Indian languages into 8000 Hz linear PCM16
    and G.711 mu-law audio suitable for Twilio telephony transmission.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        model: Optional[str] = None,
        default_voice: Optional[str] = None,
        default_language: Optional[str] = None,
        timeout: float = 10.0,
        mock_mode: Optional[bool] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.gnani_api_key
        self.url = url or settings.gnani_timbre_url
        self.model = model or settings.gnani_timbre_model
        self.default_voice = default_voice or settings.gnani_timbre_voice
        self.default_language = normalize_language_code(default_language or settings.voice_default_language)
        self.timeout = timeout
        self.mock_mode = mock_mode if mock_mode is not None else (not bool(self.api_key))
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize persistent HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=60.0),
            )
        return self._client

    async def close(self) -> None:
        """Close persistent HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bytes:
        """
        Synthesize text into raw 8000 Hz linear PCM16 audio bytes.

        Args:
            text: Dialogue text string to convert to speech.
            voice: Voice persona identifier (e.g. "Nalini").
            language: Language code (e.g. "hi-IN", "te-IN", "en-IN").

        Returns:
            Raw 8kHz 16-bit linear PCM bytes.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return b""

        if self.mock_mode:
            logger.info("Gnani Timbre synthesizing in mock mode (length: %d chars)", len(clean_text))
            # Duration proportional to text length (~12 chars per second)
            duration = max(0.5, min(len(clean_text) / 12.0, 5.0))
            return generate_mock_pcm16(duration_seconds=duration)

        payload = {
            "model": self.model,
            "text": clean_text,
            "voice": voice or self.default_voice,
            "language": normalize_language_code(language or self.default_language),
            "audio_config": {
                "sample_rate": DEFAULT_SAMPLE_RATE,
            },
        }

        headers = {
            "X-API-Key-ID": self.api_key,
            "Content-Type": "application/json",
        }

        logger.debug("Requesting Timbre TTS synthesis for %d characters", len(clean_text))
        client = await self._get_client()
        resp = await client.post(self.url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.error("Gnani Timbre TTS failed [%d]: %s", resp.status_code, resp.text)
            raise RuntimeError(f"Gnani Timbre TTS error ({resp.status_code}): {resp.text}")

        content = resp.content
        # Strip 44-byte RIFF header if the server wrapped PCM in a WAV container
        if len(content) > WAV_HEADER_SIZE and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
            content = content[WAV_HEADER_SIZE:]

        # Native 8000 Hz 16-bit linear PCM mono
        return content

    async def synthesize_mulaw(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bytes:
        """
        Synthesize text into 8000 Hz G.711 mu-law audio bytes ready for Twilio media frames.

        Args:
            text: Dialogue text string to convert to speech.
            voice: Voice persona identifier.
            language: Language code.

        Returns:
            Raw 8kHz mu-law audio bytes.
        """
        pcm16_bytes = await self.synthesize(text, voice=voice, language=language)
        return pcm16_to_mulaw(pcm16_bytes)

