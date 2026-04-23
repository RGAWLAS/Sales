"""Tests for dedup, persistence, and status transitions."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.adapters.base import RawTender
from app.filters import FilterConfig
from app.models import StatusChange, Tender, TenderCategory, TenderStatus
from app.services import (
    change_status,
    compute_content_hash,
    fetch_new_since,
    persist_raw_tenders,
    update_notes,
)


@pytest.fixture()
def cfg() -> FilterConfig:
    return FilterConfig(
        cpv_codes=["79340000"],
        keywords=["reklama", "marketing"],
        exclude_keywords=[],
    )


def _raw(title="Reklama prasowa", ext_id="X-1") -> RawTender:
    return RawTender(
        external_id=ext_id,
        title=title,
        description="opis",
        organization="ACME sp. z o.o.",
        url=f"https://example.com/{ext_id}",
        cpv_codes=["79340000-1"],
        published_at=datetime(2026, 4, 1),
        deadline=datetime(2026, 4, 15),
    )


def test_content_hash_stable(cfg):
    h1 = compute_content_hash("src", _raw())
    h2 = compute_content_hash("src", _raw())
    assert h1 == h2


def test_content_hash_differs_by_source(cfg):
    assert compute_content_hash("a", _raw()) != compute_content_hash("b", _raw())


def test_persist_dedup(db_session, cfg):
    raws = [_raw("Reklama w internecie", "1"), _raw("Reklama w prasie", "2")]
    found, new = persist_raw_tenders(db_session, "test", raws, cfg)
    assert (found, new) == (2, 2)

    # Second run — same keys, nothing new inserted.
    raws2 = [_raw("Reklama w internecie", "1"), _raw("Reklama w prasie", "2")]
    found2, new2 = persist_raw_tenders(db_session, "test", raws2, cfg)
    assert new2 == 0
    assert found2 == 2

    assert db_session.query(Tender).count() == 2


def test_persist_filters_out_non_matching(db_session, cfg):
    raws = [
        _raw("Reklama w radio", "m1"),
        RawTender(external_id="skip", title="Odśnieżanie", cpv_codes=[]),
    ]
    _, new = persist_raw_tenders(db_session, "test", raws, cfg)
    assert new == 1


def test_status_change_records_history(db_session, cfg):
    persist_raw_tenders(db_session, "test", [_raw("Reklama", "a")], cfg)
    tender = db_session.query(Tender).first()

    change_status(db_session, tender.id, TenderStatus.INTERESTED)
    change_status(db_session, tender.id, TenderStatus.APPLIED)

    db_session.refresh(tender)
    assert tender.status == TenderStatus.APPLIED
    changes = db_session.query(StatusChange).filter_by(tender_id=tender.id).all()
    assert len(changes) == 2
    assert {c.to_status for c in changes} == {TenderStatus.INTERESTED, TenderStatus.APPLIED}


def test_status_change_noop_when_same_status(db_session, cfg):
    persist_raw_tenders(db_session, "test", [_raw("Reklama 2", "b")], cfg)
    tender = db_session.query(Tender).first()
    change_status(db_session, tender.id, TenderStatus.NEW)
    assert db_session.query(StatusChange).count() == 0


def test_update_notes(db_session, cfg):
    persist_raw_tenders(db_session, "test", [_raw("Reklama 3", "c")], cfg)
    tender = db_session.query(Tender).first()
    update_notes(db_session, tender.id, "moje notatki")
    db_session.refresh(tender)
    assert tender.notes == "moje notatki"


def test_persist_preserves_category_early_signal(db_session, cfg):
    raw = RawTender(
        external_id="sig-1",
        title="Reklama: nowa kampania w prasie",
        description="zapowiedź",
        organization="news",
        url="https://example.com/1",
        cpv_codes=[],
        category="EARLY_SIGNAL",
    )
    _, new = persist_raw_tenders(db_session, "news_demo", [raw], cfg)
    assert new == 1
    t = db_session.query(Tender).one()
    assert t.category == TenderCategory.EARLY_SIGNAL


def test_fetch_new_since_respects_category(db_session, cfg):
    t_raw = _raw("Reklama — przetarg", "t1")
    s_raw = RawTender(
        external_id="s1",
        title="Reklama news",
        description="",
        url="https://x",
        cpv_codes=[],
        category="EARLY_SIGNAL",
    )
    persist_raw_tenders(db_session, "a", [t_raw], cfg)
    persist_raw_tenders(db_session, "b", [s_raw], cfg)

    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(hours=1)

    all_rows = fetch_new_since(db_session, since)
    tenders_only = fetch_new_since(db_session, since, category=TenderCategory.TENDER)
    signals_only = fetch_new_since(db_session, since, category=TenderCategory.EARLY_SIGNAL)

    assert len(all_rows) == 2
    assert len(tenders_only) == 1
    assert len(signals_only) == 1
    assert tenders_only[0].category == TenderCategory.TENDER
    assert signals_only[0].category == TenderCategory.EARLY_SIGNAL
