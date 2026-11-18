from datetime import time
from zoneinfo import available_timezones

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    api_token: str
    database_url: str
    user_timezone: str = "America/New_York"
    work_start: time = time(9)
    work_end: time = time(17)
    default_effort_minutes: int = 60
    llm_model: str = ""  # never hard coded: set LLM_MODEL when a real client is wired in
    llm_daily_token_budget: int = 20000
    stale_after_hours: int = 26
    google_client_secrets_path: str = "./secrets/client_secret.json"
    google_token_path: str = "./secrets/google_token.json"
    calendar_ids: str = "primary"
    obsidian_vault_path: str = ""
    obsidian_ignore_globs: str = "templates/*,archive/*"
    sync_interval_minutes: int = 0  # 0 = off. Set 15 to sync on a timer while the app runs locally

    @field_validator("user_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("USER_TIMEZONE is not a valid IANA time zone")
        return v
