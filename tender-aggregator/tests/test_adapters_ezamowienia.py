"""Mock-based tests for the ezamowienia adapter's JSON parsing."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.ezamowienia import (
    EzamowieniaAdapter,
    _extract_items,
    _item_to_raw,
    _parse_dt,
)


def _fake_response(payload):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    r.text = "{}"
    return r


def test_extract_items_handles_variants():
    assert _extract_items({"Data": [{"x": 1}]}) == [{"x": 1}]
    assert _extract_items({"data": [{"x": 2}]}) == [{"x": 2}]
    assert _extract_items({"Items": [{"x": 3}]}) == [{"x": 3}]
    assert _extract_items({}) == []


def test_item_to_raw_basic():
    item = {
        "ObjectId": "abc-123",
        "OrderObject": "Usługi reklamowe dla jednostki",
        "OrganizationName": "Urząd X",
        "CpvCodes": ["79340000-1", "79341200"],
        "PublicationDate": "2026-04-20T10:00:00Z",
        "SubmittingOffersDate": "2026-05-05T12:00:00",
    }
    raw = _item_to_raw(item)
    assert raw is not None
    assert raw.external_id == "abc-123"
    assert "Usługi reklamowe" in raw.title
    assert raw.organization == "Urząd X"
    assert raw.cpv_codes == ["79340000-1", "79341200"]
    assert raw.published_at is not None
    assert raw.deadline is not None
    assert raw.url.endswith("abc-123")


def test_item_to_raw_skips_without_id():
    assert _item_to_raw({"OrderObject": "bez id"}) is None


def test_parse_dt_variants():
    assert _parse_dt(None) is None
    assert _parse_dt("") is None
    assert _parse_dt("2026-04-20") is not None
    assert _parse_dt("2026-04-20T10:00:00Z") is not None
    assert _parse_dt("2026-04-20T10:00:00") is not None
    assert _parse_dt("not a date") is None


def test_fetch_end_to_end_with_mock():
    adapter = EzamowieniaAdapter()
    page1 = {
        "Data": [
            {
                "ObjectId": "1",
                "OrderObject": "Kampania reklamowa",
                "OrganizationName": "Instytut Y",
                "CpvCodes": ["79341400"],
                "PublicationDate": "2026-04-20T09:00:00Z",
            },
            {
                "ObjectId": "2",
                "OrderObject": "Usługi sprzątania",
                "OrganizationName": "Szkoła Z",
                "CpvCodes": ["90910000"],
                "PublicationDate": "2026-04-20T09:30:00Z",
            },
        ]
    }
    page2 = {"Data": []}

    call_seq = [page1, page2]

    def side_effect(*args, **kwargs):
        payload = call_seq.pop(0) if call_seq else {"Data": []}
        return _fake_response(payload)

    with patch.object(adapter, "http_post", side_effect=side_effect):
        with patch.object(adapter, "request_delay_seconds", 0):
            out = adapter.fetch()

    assert len(out) == 2
    assert out[0].external_id == "1"
    assert out[1].external_id == "2"
