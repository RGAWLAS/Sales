"""Tests for dedup, persistence, and status transitions."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.adapters.base import RawTender
from app.filters import FilterConfig
from app.models import StatusChange, Tender, TenderStatus
from app.services import (
    change_status,
    compute_content_hash,
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
