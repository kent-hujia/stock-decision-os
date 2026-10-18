import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Stock Decision OS"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
    FINMIND_API_KEY: str = os.getenv("FINMIND_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

    class Config:
        env_file = ".env"

settings = Settings()
