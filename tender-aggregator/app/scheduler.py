"""APScheduler jobs: daily scrape + daily digest.

Also exposes ``run_adapter_once`` used by the dashboard's "Run now" button
and by the ``run-once`` CLI.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as pytz_timezone

from app.adapters.base import BaseAdapter
from app.adapters.registry import ADAPTERS, get_adapter
from app.config import settings
from app.database import SessionLocal
from app.filters import load_filter_config
from app.models import ScrapeRun
from app.notifier import send_daily_digest
from app.services import (
    persist_raw_tenders,
    record_scrape_run_end,
    record_scrape_run_start,
)


logger = logging.getLogger(__name__)


def run_adapter_once(adapter: BaseAdapter) -> ScrapeRun:
    """Execute a single adapter, persist its results, and log a ScrapeRun."""
    session = SessionLocal()
    try:
        run = record_scrape_run_start(session, adapter.source_id)
        filter_config = load_filter_config(settings.filters_path)

        try:
            raws = adapter.fetch()
        except Exception as exc:
            logger.exception("Adapter %s raised during fetch", adapter.source_id)
            record_scrape_run_end(
                session, run, found_count=0, new_count=0, status="ERROR",
                error_message=str(exc)[:1000],
            )
            return run

        try:
            found, new_count = persist_raw_tenders(session, adapter.source_id, raws, filter_config)
        except Exception as exc:
            logger.exception("Adapter %s raised during persist", adapter.source_id)
            record_scrape_run_end(
                session, run, found_count=0, new_count=0, status="ERROR",
                error_message=str(exc)[:1000],
            )
            return run

        record_scrape_run_end(session, run, found_count=found, new_count=new_count, status="OK")
        logger.info(
            "Adapter %s finished: matched=%d, new=%d",
            adapter.source_id, found, new_count,
        )
        return run
    finally:
        session.close()


def run_all_adapters(max_workers: int = 4) -> List[ScrapeRun]:
    """Run every enabled adapter in parallel, isolated by ThreadPoolExecutor."""
    targets = [a for a in ADAPTERS if a.enabled]
    logger.info("Starting scrape of %d adapters (max_workers=%d)", len(targets), max_workers)
    runs: List[ScrapeRun] = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="scrape") as pool:
        futures = {pool.submit(run_adapter_once, a): a for a in targets}
        for fut in as_completed(futures):
            adapter = futures[fut]
            try:
                runs.append(fut.result())
            except Exception:
                logger.exception("Adapter %s crashed outside adapter run wrapper", adapter.source_id)
    logger.info("Scrape finished (%d runs)", len(runs))
    return runs


def daily_scrape_job() -> None:
    logger.info("[scheduler] daily_scrape_job fired at %s", datetime.now().isoformat())
    run_all_adapters()


def daily_digest_job() -> None:
    logger.info("[scheduler] daily_digest_job fired at %s", datetime.now().isoformat())
    session = SessionLocal()
    try:
        send_daily_digest(session)
    except Exception:
        logger.exception("Digest job failed")
    finally:
        session.close()


def build_scheduler() -> BackgroundScheduler:
    """Create a configured BackgroundScheduler with the two daily jobs."""
    tz = pytz_timezone(settings.timezone)
    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(
        daily_scrape_job,
        CronTrigger(hour=settings.scrape_hour, minute=settings.scrape_minute, timezone=tz),
        id="daily_scrape",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        daily_digest_job,
        CronTrigger(hour=settings.digest_hour, minute=settings.digest_minute, timezone=tz),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return sched


# -- CLI entry point for manual runs (``python -m app.scheduler run-once``) --

def _cli() -> None:
    import argparse

    from app.config import configure_logging
    from app.database import init_db

    parser = argparse.ArgumentParser(description="Tender aggregator manual operations")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run-once", help="Run every enabled adapter once, synchronously")

    one = sub.add_parser("run-adapter", help="Run a single adapter by source_id")
    one.add_argument("source_id")

    sub.add_parser("digest", help="Send the daily digest email now")

    args = parser.parse_args()
    configure_logging()
    init_db()

    if args.cmd == "run-once":
        run_all_adapters()
    elif args.cmd == "run-adapter":
        adapter = get_adapter(args.source_id)
        if adapter is None:
            raise SystemExit(f"No adapter with source_id={args.source_id!r}")
        run_adapter_once(adapter)
    elif args.cmd == "digest":
        session = SessionLocal()
        try:
            send_daily_digest(session)
        finally:
            session.close()


if __name__ == "__main__":
    _cli()
