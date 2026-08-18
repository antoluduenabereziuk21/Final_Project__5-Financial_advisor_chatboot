from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        self.api_prefix = os.getenv("API_PREFIX", "")

        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins = [
            origin.strip() for origin in raw_origins.split(",") if origin.strip()
        ]

        self.vector_db_host = os.getenv("VECTOR_DB_HOST", "localhost")
        self.vector_db_port = int(os.getenv("VECTOR_DB_PORT", "5432"))
        self.vector_db_user = os.getenv("VECTOR_DB_USER", "ml_engineer")
        self.vector_db_password = os.getenv("VECTOR_DB_PASSWORD", "ml_password_2026")
        self.vector_db_name = os.getenv("VECTOR_DB_NAME", "financial_rag_vectors")

        # Optional Supabase REST/RPC configuration.
        # Used for vector retrieval over HTTPS instead of requiring a direct
        # PostgreSQL connection.
        self.supabase_url: str | None = os.getenv("SUPABASE_URL")
        self.supabase_key: str | None = os.getenv("SUPABASE_KEY")

        self.groq_api_key: str | None = os.getenv("GROQ_API_KEY")
        self.groq_model: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


settings = Settings()
