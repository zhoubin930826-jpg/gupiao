from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Stock Pilot API"
    api_prefix: str = "/api"
    app_mode: str = "demo"
    app_timezone: str = "Asia/Shanghai"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )
    enable_task_scheduler: bool = True
    scheduler_market_hour: int = 18
    scheduler_market_minute: int = 10
    scheduler_signal_hour: int = 18
    scheduler_signal_minute: int = 20
    scheduler_publish_hour: int = 18
    scheduler_publish_minute: int = 30
    enable_akshare_sync: bool = False
    akshare_request_timeout: int = 20
    akshare_retry_attempts: int = 3
    akshare_retry_delay_ms: int = 1200
    akshare_stock_limit: int = 80
    akshare_history_days: int = 180
    akshare_max_workers: int = 6
    business_database_url: str = f"sqlite:///{(DATA_DIR / 'stockpilot.db').as_posix()}"
    market_database_path: str = (DATA_DIR / "market.duckdb").as_posix()


@lru_cache
def get_settings() -> Settings:
    return Settings()
