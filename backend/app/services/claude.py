"""Shared Claude call with structured output and user-facing (Traditional Chinese) errors."""
from datetime import datetime, timedelta, timezone
from typing import Optional, Type, TypeVar

import anthropic
from pydantic import BaseModel

from app.core.config import settings

# Background jobs still "pending" after this long are treated as dead and may be restarted.
STALE_AFTER = timedelta(minutes=10)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

T = TypeVar("T", bound=BaseModel)


class ClaudeError(Exception):
    """Raised when Claude can't produce output; the message is safe to show to users."""


def require_key() -> None:
    """Fail before fetching data for a prompt that can never be sent."""
    if not settings.ANTHROPIC_API_KEY:
        raise ClaudeError("後端沒有設定 ANTHROPIC_API_KEY。")


def parse(prompt: str, output_format: Type[T], effort: str = "medium") -> T:
    require_key()
    try:
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
            output_format=output_format,
            # Retry on another model automatically if a safety classifier declines.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
    except anthropic.AuthenticationError as e:
        raise ClaudeError("ANTHROPIC_API_KEY 無效或沒有設定。") from e
    except anthropic.RateLimitError as e:
        raise ClaudeError("Claude API 請求過於頻繁，請稍後再試。") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Claude API 錯誤（{e.status_code}）：{e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ClaudeError("無法連線到 Claude API，請稍後再試。") from e
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise ClaudeError(f"Claude 沒有產生內容（stop_reason={response.stop_reason}）")
    return response.parsed_output


def as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive UTC datetimes, Postgres returns aware ones; normalise both."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_stale(started: Optional[datetime]) -> bool:
    started = as_utc(started)
    return started is not None and datetime.now(timezone.utc) - started >= STALE_AFTER
