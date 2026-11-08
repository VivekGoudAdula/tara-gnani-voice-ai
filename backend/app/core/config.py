"""Application configuration settings loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core application settings model."""

    app_env: str = "development"
    secret_key: str = "tara-super-secret-jwt-key-replace-in-production-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "tara"
    mongo_db_name_test: str = "tara_test"

    seed_password: str = "ChangeMe123!"
    seed_test_phone_1: str | None = None
    seed_test_phone_2: str | None = None
    seed_test_phone_3: str | None = None

    # Twilio Telephony Configuration (TARA 2.0)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Gnani Voice AI Configuration (TARA 2.0)
    gnani_api_key: str = ""
    gnani_prisma_url: str = "wss://api.vachana.ai/stt/v3/stream"
    gnani_prisma_model: str = "prisma-v3.0"
    gnani_timbre_url: str = "https://api.vachana.ai/api/v1/tts/inference"
    gnani_timbre_model: str = "timbre-v2.5"
    gnani_timbre_voice: str = "Nalini"

    # Voice Pipeline Orchestration
    voice_provider: str = "twilio_gnani"
    voice_default_language: str = "hi-IN"
    voice_stream_path: str = "/api/voice/stream"

    # LLM Reasoning Configuration (Phase 3 Intelligent Engine)
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.8-27b"
    llm_provider: str = "groq"
    llm_temperature: float = 0.2
    llm_timeout: float = 8.0
    llm_max_retries: int = 2

    # Compliance & Safety Configuration
    test_mode: bool = True
    test_allowlist: str = ""
    compliance_exempt_numbers: str = ""
    compliance_check_duplicate_in_flight: bool = True
    compliance_check_frequency_cap: bool = True
    call_window_start: str = "09:00"
    call_window_end: str = "21:00"
    contact_cap_count: int = 2
    contact_cap_days: int = 7
    public_base_url: str = "http://localhost:8000"

    # Campaign Execution Configuration
    campaign_max_recipients: int = 200
    campaign_max_concurrent: int = 2
    campaign_dispatch_delay_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
