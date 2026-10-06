from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SESSION_SECRET_PLACEHOLDERS = {
    "CHANGE_ME_TO_A_LONG_RANDOM_SECRET",
    "replace_with_a_long_random_secret",
}
GROQ_API_KEY_PLACEHOLDERS = {
    "PASTE_YOUR_GROQ_API_KEY_HERE",
    "replace_with_your_groq_api_key",
}


@dataclass(frozen=True)
class Settings:
    database_path: Path
    session_secret: str | None
    cookie_secure: bool
    groq_api_key: str | None
    groq_model: str

    @classmethod
    def from_environment(cls) -> "Settings":
        session_secret = os.getenv("SESSION_SECRET") or None
        groq_api_key = os.getenv("GROQ_API_KEY") or None
        return cls(
            database_path=Path(
                os.getenv("DATABASE_PATH") or str(PROJECT_ROOT / "database" / "skillonex.db")
            ).expanduser(),
            session_secret=None
            if session_secret in SESSION_SECRET_PLACEHOLDERS
            else session_secret,
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
            groq_api_key=None
            if groq_api_key in GROQ_API_KEY_PLACEHOLDERS
            else groq_api_key,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        )


settings = Settings.from_environment()
