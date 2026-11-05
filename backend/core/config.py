# core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List, Optional
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "core.db"


class Settings(BaseSettings):
    APP_NAME: str = "THE_SYSTEM Core"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8001
    SECRET_KEY: str = "your-secret-key-change-in-production"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False
    JWT_SECRET_KEY: str = "THE_SYSTEM-Core-Development-JWT-Key-Change-Before-Production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    REDIS_URL: str = ""
    REDIS_PASSWORD: Optional[str] = None
    
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173",
                              "http://127.0.0.1:8000",      # Frontend
    "http://localhost:8000",      ]
    
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def production_secrets(self):
        if self.APP_ENV.lower() == "production":
            if len(self.JWT_SECRET_KEY) < 32 or "Development" in self.JWT_SECRET_KEY:
                raise ValueError("Production requires a private JWT_SECRET_KEY of at least 32 characters")
            if self.SECRET_KEY == "your-secret-key-change-in-production" or len(self.SECRET_KEY) < 32:
                raise ValueError("Production requires a private SECRET_KEY of at least 32 characters")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
        return self
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() == "release":
            return False
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
