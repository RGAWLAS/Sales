"""Mock-based tests for the Baza Konkurencyjności adapter."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.baza_konkurencyjnosci import (
    BazaKonkurencyjnosciAdapter,
    _extract_items,
    _item_to_raw,
)


def _fake_response(payload):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    return r


def test_extract_items_variants():
    assert _extract_items([{"id": 1}]) == [{"id": 1}]
    assert _extract_items({"items": [{"id": 2}]}) == [{"id": 2}]
    assert _extract_items({"content": [{"id": 3}]}) == [{"id": 3}]
    assert _extract_items({}) == []


def test_item_to_raw_with_cpv_objects():
    item = {
        "id": "uuid-123",
        "title": "Kampania reklamowa 2026",
        "description": "Opis kampanii",
        "advertiserName": "Beneficjent Sp. z o.o.",
        "publicationDate": "2026-04-20T10:00:00",
        "deadline": "2026-05-10T12:00:00",
        "cpvCodes": [{"code": "79341400"}, {"code": "79342000"}],
    }
    raw = _item_to_raw(item)
    assert raw is not None
    assert raw.external_id == "uuid-123"
    assert raw.title == "Kampania reklamowa 2026"
    assert raw.organization == "Beneficjent Sp. z o.o."
    assert raw.cpv_codes == ["79341400", "79342000"]
    assert raw.published_at is not None
    assert raw.deadline is not None
    assert raw.url.endswith("uuid-123")


def test_item_to_raw_skips_without_id():
    assert _item_to_raw({"title": "brak id"}) is None


def test_fetch_stops_on_empty_page():
    adapter = BazaKonkurencyjnosciAdapter()
    page1 = {
        "items": [
            {
                "id": "a",
                "title": "Usługi reklamowe",
                "advertiserName": "X",
                "cpvCodes": ["79340000"],
                "publicationDate": "2026-04-20",
            }
        ]
    }
    # Short page => loop stops after page 1.
    call_seq = [page1]

    def side_effect(*args, **kwargs):
        if not call_seq:
            return _fake_response({"items": []})
        return _fake_response(call_seq.pop(0))

    with patch.object(adapter, "http_get", side_effect=side_effect), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()

    assert len(out) == 1
    assert out[0].external_id == "a"
