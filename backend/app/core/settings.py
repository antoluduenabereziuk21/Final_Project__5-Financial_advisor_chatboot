import os


class Settings:
    def __init__(self) -> None:
        self.api_prefix = os.getenv("API_PREFIX", "")
        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


settings = Settings()