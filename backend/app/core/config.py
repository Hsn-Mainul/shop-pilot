from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://chatbot:chatbot@localhost:5432/chatbot"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 14
    cors_origins: str = "http://localhost:5175,http://localhost:5173,http://127.0.0.1:5175,http://127.0.0.1:5173"

    # Local uvicorn bind (python -m app.main). Default 8001 avoids common Windows :8000 conflicts.
    app_host: str = "127.0.0.1"
    app_port: int = 8001

    # Background jobs (Celery) — see app/core/celery_app.py
    redis_url: str = "redis://localhost:6379/0"

    # LLM provider for the AI Orchestrator (OpenAI-compatible chat completions API;
    # also works with Ollama or any compatible gateway by overriding llm_base_url).
    llm_provider: str = "ollama"  # "ollama", "openai", "custom"
    llm_api_key: str | None = None
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5vl:3b"

    # Multi-Tier Precision & Resilient Fallback Providers
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_backup_model: str = "qwen/qwen3.8-27b"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"

    # Ollama native API & RAG embeddings configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5vl:3b"
    ollama_embed_model: str = "all-minilm"

    # Speech-to-text for voice notes (OpenAI-compatible audio transcription API).
    asr_api_key: str | None = None
    asr_base_url: str = "https://api.openai.com/v1"
    asr_model: str = "whisper-1"

    # Telephony / voice calling (Twilio Voice REST API).
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_whatsapp_from: str | None = None  # e.g. "whatsapp:+14155238886"
    twilio_voice_webhook_url: str | None = None  # TwiML URL Twilio fetches when the call connects

    # Outbound transactional/campaign email (SMTP — works with any real mailbox/provider).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    smtp_use_tls: bool = True

    # Meta (Facebook/Instagram/WhatsApp) Graph API — used for social publishing and,
    # together with Integration.config, per-Shop OAuth.
    # v19.0 returned "(100) Unsupported request - method type: post" sending an
    # image to an Instagram-scoped recipient id — the newer Page-linked
    # Instagram messaging architecture needs a current API version.
    meta_graph_base_url: str = "https://graph.facebook.com/v23.0"
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    meta_oauth_redirect_uri: str | None = None
    meta_webhook_verify_token: str | None = None
    # "Facebook Login for Business" configuration ID — Meta now requires Instagram
    # messaging permissions (instagram_manage_messages etc.) to be requested through a
    # named Configuration created in the App Dashboard (Use Cases > Instagram API with
    # Unified Login > Create new configuration), rather than as plain OAuth scopes.
    # When set, the connect URL uses config_id instead of a scope list.
    meta_login_config_id: str | None = None

    # Public base URL used to build Twilio TwiML / OAuth callback URLs.
    public_base_url: str = "http://localhost:8001"

    # Optional OAuth apps for non-Meta providers (authorize URL + code exchange).
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None
    stripe_client_id: str | None = None
    stripe_client_secret: str | None = None
    stripe_oauth_redirect_uri: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_ollama(self) -> bool:
        return (
            (self.llm_provider or "").lower() == "ollama"
            or "11434" in (self.llm_base_url or "")
            or "11434" in (self.ollama_base_url or "")
        )

    @property
    def effective_groq_api_key(self) -> str | None:
        import os
        return self.groq_api_key or os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ__APIKEY")

    @property
    def effective_groq_model(self) -> str:
        import os
        return os.environ.get("GROQ_MODEL") or os.environ.get("GROQ__MODEL") or self.groq_model

    @property
    def llm_configured(self) -> bool:
        if self.effective_groq_api_key or self.openai_api_key or self.gemini_api_key or self.llm_api_key:
            return True
        if self.is_ollama:
            return bool(self.ollama_base_url or self.llm_base_url)
        return False

    @property
    def effective_asr_api_key(self) -> str | None:
        # Reuse the Groq key already configured for chat, rather than requiring a second,
        # separate ASR_API_KEY — Groq serves an OpenAI-compatible Whisper endpoint too.
        return self.asr_api_key or self.effective_groq_api_key

    @property
    def effective_asr_base_url(self) -> str:
        if self.asr_api_key:
            return self.asr_base_url
        return "https://api.groq.com/openai/v1" if self.effective_groq_api_key else self.asr_base_url

    @property
    def effective_asr_model(self) -> str:
        if self.asr_api_key:
            return self.asr_model
        return "whisper-large-v3-turbo" if self.effective_groq_api_key else self.asr_model

    @property
    def asr_configured(self) -> bool:
        return bool(self.effective_asr_api_key)

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from_address)

    @property
    def meta_configured(self) -> bool:
        return bool(self.meta_app_id and self.meta_app_secret)


settings = Settings()
