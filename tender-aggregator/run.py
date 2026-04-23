"""Entrypoint: start the APScheduler in-process alongside the uvicorn server."""
from __future__ import annotations

import logging

import uvicorn

from app.config import configure_logging, settings
from app.database import init_db
from app.scheduler import build_scheduler


logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    init_db()

    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "Scheduler started (scrape=%02d:%02d, digest=%02d:%02d, tz=%s)",
        settings.scrape_hour, settings.scrape_minute,
        settings.digest_hour, settings.digest_minute,
        settings.timezone,
    )

    try:
        uvicorn.run(
            "app.main:app",
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            reload=False,
            log_level=settings.log_level.lower(),
        )
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
