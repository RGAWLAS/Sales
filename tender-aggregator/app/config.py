"""Application configuration loaded from environment variables."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration. All fields populated from .env or environment."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/tenders.db"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    notification_email: str = ""

    timezone: str = "Europe/Warsaw"
    scrape_hour: int = 6
    scrape_minute: int = 0
    digest_hour: int = 8
    digest_minute: int = 30
    send_empty_digest: bool = False
    digest_include_signals: bool = True

    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000

    log_level: str = "INFO"

    filters_path: str = str(BASE_DIR / "config" / "filters.yml")
    logs_dir: str = str(BASE_DIR / "logs")
    data_dir: str = str(BASE_DIR / "data")

    @property
    def base_dir(self) -> Path:
        return BASE_DIR


settings = Settings()


def configure_logging() -> None:
    """Set up root logger with rotating file handler + stderr handler."""
    logs_dir = Path(settings.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if root.handlers:
        return

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
