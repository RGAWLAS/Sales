"""Persistence / business logic: dedup, save, status transitions."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import RawTender
from app.filters import FilterConfig, evaluate
from app.models import ScrapeRun, StatusChange, Tender, TenderStatus


logger = logging.getLogger(__name__)


def compute_content_hash(source: str, raw: RawTender) -> str:
    """Produce a stable hash for dedup.

    Prefer ``source + external_id`` (stable); fall back to ``source + url``.
    """
    if raw.external_id:
        key = f"{source}|id|{raw.external_id}"
    elif raw.url:
        key = f"{source}|url|{raw.url}"
    else:
        key = f"{source}|title|{raw.title}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def persist_raw_tenders(
    session: Session,
    source_id: str,
    raws: Iterable[RawTender],
    filter_config: FilterConfig,
) -> Tuple[int, int]:
    """Filter, dedup, and persist a batch of raw tenders.

    Returns a ``(found_total, new_count)`` tuple.
    ``found_total`` counts raws that passed the filter; ``new_count`` counts
    rows actually inserted.
    """
    found = 0
    new_count = 0

    for raw in raws:
        decision = evaluate(raw.title, raw.description, raw.cpv_codes, filter_config)
        if not decision.passed:
            continue
        found += 1

        h = compute_content_hash(source_id, raw)
        existing = session.execute(
            select(Tender).where(Tender.content_hash == h)
        ).scalar_one_or_none()

        if existing is not None:
            # Refresh cheap, user-invisible fields if the source updated them.
            existing.title = raw.title
            if raw.description:
                existing.description = raw.description
            if raw.organization:
                existing.organization = raw.organization
            if raw.url:
                existing.url = raw.url
            if raw.cpv_codes:
                existing.cpv_codes = raw.cpv_codes
            if raw.deadline:
                existing.deadline = raw.deadline
            continue

        tender = Tender(
            source=source_id,
            external_id=raw.external_id or "",
            title=raw.title[:1000],
            description=raw.description or "",
            organization=raw.organization or "",
            url=raw.url or "",
            cpv_codes=list(raw.cpv_codes or []),
            keywords_matched=list(decision.keywords_matched),
            published_at=raw.published_at,
            deadline=raw.deadline,
            scraped_at=datetime.utcnow(),
            status=TenderStatus.NEW,
            content_hash=h,
        )
        session.add(tender)
        new_count += 1

    session.commit()
    return found, new_count


def change_status(
    session: Session,
    tender_id: int,
    new_status: TenderStatus,
) -> Optional[Tender]:
    """Update tender status, writing an audit row. Returns the tender or None."""
    tender = session.get(Tender, tender_id)
    if tender is None:
        return None
    if tender.status == new_status:
        return tender

    old = tender.status
    tender.status = new_status
    session.add(StatusChange(tender_id=tender.id, from_status=old, to_status=new_status))
    session.commit()
    return tender


def update_notes(session: Session, tender_id: int, notes: str) -> Optional[Tender]:
    tender = session.get(Tender, tender_id)
    if tender is None:
        return None
    tender.notes = notes
    session.commit()
    return tender


def record_scrape_run_start(session: Session, adapter_id: str) -> ScrapeRun:
    run = ScrapeRun(adapter=adapter_id, started_at=datetime.utcnow(), status="OK")
    session.add(run)
    session.commit()
    return run


def record_scrape_run_end(
    session: Session,
    run: ScrapeRun,
    *,
    found_count: int,
    new_count: int,
    status: str = "OK",
    error_message: Optional[str] = None,
) -> None:
    run.finished_at = datetime.utcnow()
    run.found_count = found_count
    run.new_count = new_count
    run.status = status
    run.error_message = error_message
    session.commit()


def fetch_new_since(session: Session, since: datetime) -> List[Tender]:
    """Return NEW-status tenders scraped after ``since``, newest first."""
    stmt = (
        select(Tender)
        .where(Tender.status == TenderStatus.NEW, Tender.scraped_at >= since)
        .order_by(Tender.scraped_at.desc())
    )
    return list(session.execute(stmt).scalars().all())
