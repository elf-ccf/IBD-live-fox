from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IBD Live AI Discussant"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    openai_api_key: str = ""
    openai_text_model: str = "gpt-4o-mini"
    openai_realtime_model: str = "gpt-realtime-2.1-mini"
    openai_realtime_voice: str = "cedar"
    openai_transcription_model: str = "gpt-4o-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "cedar"

    recall_api_key: str = ""
    recall_region_base_url: str = (
        "https://us-west-2.recall.ai"
    )
    public_base_url: str = ""
    recall_webhook_secret: str = ""

    frontend_origin: str = "http://localhost:5173"

    wake_phrase: str = "hey ai"
    bot_display_name: str = "IBD Live AI"
    deidentified_only: bool = True
    third_party_meeting_integrations_enabled: bool = False
    enable_webex_auto_agent: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
