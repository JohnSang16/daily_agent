from zoneinfo import available_timezones

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    api_token: str
    database_url: str
    user_timezone: str = "America/New_York"

    @field_validator("user_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("USER_TIMEZONE is not a valid IANA time zone")
        return v
