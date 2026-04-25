from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    app_host: str = "https://claimcall.yourdomain.com"
    environment: str = "development"
    log_level: str = "INFO"

    # Twilio
    twilio_account_sid: str
    twilio_api_key_sid: str
    twilio_api_key_secret: str
    twilio_phone_number: str
    twilio_validate_requests: bool = True

    # ElevenLabs
    elevenlabs_api_key: str
    elevenlabs_agent_id: str
    elevenlabs_webhook_secret: str

    # AI-Coustics — .env uses AICOUSTICS_API_KEY; aic-sdk expects AIC_SDK_LICENSE
    aicoustics_api_key: str = ""
    aicoustics_enabled: bool = True
    el_is_mulaw: bool = False

    @property
    def aic_sdk_license(self) -> str:
        return self.aicoustics_api_key

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Audio
    apply_telephone_filter: bool = True
    telephone_filter_order: int = 4

    # Notifications
    claims_manager_phone: str = ""
    claims_manager_email: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
