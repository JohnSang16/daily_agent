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
    anthropic_api_key: str = ""
    llm_model: str = ""  # never hard coded: set LLM_MODEL when a real client is wired in
    llm_daily_token_budget: int = 20000
    # api = Console credits, cli = headless Claude Code on the logged in subscription
    llm_backend: str = "api"
    claude_cli_path: str = "claude"
    stale_after_hours: int = 26
    stale_overdue_days: int = 14  # overdue longer than this is hidden from /today, 0 shows all
    google_client_secrets_path: str = "./secrets/client_secret.json"
    google_token_path: str = "./secrets/google_token.json"
    icollege_feed_url_path: str = "~/.config/icollege-feed-url"
    # same search as /daily full's OA sweep (spec 15)
    gmail_oa_query: str = (
        "newer_than:12d (HackerRank OR HireVue OR ModernHire OR CodeSignal OR Glider OR "
        '"online assessment" OR "pre-employment assessment")'
    )
    calendar_ids: str = "primary"
    obsidian_vault_path: str = ""
    obsidian_ignore_globs: str = "templates/*,archive/*,_archive/*"
    # set to sync from a local git checkout instead of obsidian_vault_path
    obsidian_repo_url: str = ""
    obsidian_deploy_key_path: str = "./secrets/vault_deploy_key"
    obsidian_checkout_dir: str = "./vault_checkout"
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"  # sandbox (fake banks) or production
    token_encryption_key: str = ""
    ask_private_globs: str = ""  # folders kept out of the ask index entirely
    # spec 13 homework agent
    kernel_api_key: str = ""
    kernel_profile: str = "school"  # a browser profile used only for school sites
    agent_model: str = "claude-sonnet-5-5"
    agent_escalate_model: str = (
        "claude-opus-5-5"  # used for the rest of a session after a failed step
    )
    agent_effort: str = "medium"
    agent_allowed_hosts: str = (
        "gastate.view.usg.edu,gsu.edu,pearson.com,pearsoncmg.com,pearsoned.com"
    )
    agent_max_steps: int = 60
    agent_max_minutes: int = 30
    agent_session_token_budget: int = 600_000
    agent_daily_token_budget: int = 2_000_000
    gemini_api_key: str = ""  # free tier, used only by the homework solver
    # the solver ladder, cheapest first (spec 13 component 7)
    solver_models: str = "gemini-3.6-flash,gemini-3.8-flash,claude-sonnet-5-5,claude-opus-5-5"
    school_notes_globs: str = "career/school/*"  # what homework mode searches (spec 19)
    # deadline questions read dated lines from these notes (spec 14)
    deadline_notes_globs: str = "career/faang-prep/oa-tracker.md,career/school/*"
    ask_llm_blocked_globs: str = "cox/*"  # searchable, but text never sent to the LLM
    sync_interval_minutes: int = 0  # 0 = off. Set 15 to sync on a timer while the app runs locally

    @field_validator("user_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("USER_TIMEZONE is not a valid IANA time zone")
        return v
