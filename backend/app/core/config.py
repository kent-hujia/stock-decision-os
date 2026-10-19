import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Stock Decision OS"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
    FINMIND_API_KEY: str = os.getenv("FINMIND_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
    # Cheaper models for routine work; each can be changed with an env var on Railway.
    SWING_MODEL: str = os.getenv("SWING_MODEL", "claude-haiku-5-5")      # chip/technical reading
    REVIEW_MODEL: str = os.getenv("REVIEW_MODEL", "claude-sonnet-5-5")   # closed-trade review
    # Daily after-close check and Gmail notification (Gmail needs an app password, not the account password).
    GMAIL_USER: str = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    NOTIFY_EMAIL: str = os.getenv("NOTIFY_EMAIL", "")  # defaults to GMAIL_USER
    DAILY_CHECK_HOUR: int = int(os.getenv("DAILY_CHECK_HOUR", "22"))  # Taiwan time; margin data lands ~21:30
    PDF_MODEL: str = os.getenv("PDF_MODEL", "claude-sonnet-5-5")         # earnings-call slides

    class Config:
        env_file = ".env"

settings = Settings()
