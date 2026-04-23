"""Mock-based tests for the TED adapter — multi-language field picking + CPV."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.ted import (
    TedAdapter,
    _notice_to_raw,
    _parse_ted_date,
    _pick_cpv,
    _pick_lang,
)


def _fake_response(payload):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=payload)
    return r


def test_pick_lang_preferred_first():
    assert _pick_lang({"pol": "polski", "eng": "english"}) == "polski"
    assert _pick_lang({"eng": "english"}) == "english"
    assert _pick_lang("plain string") == "plain string"
    assert _pick_lang(None) == ""


def test_pick_cpv_variants():
    assert _pick_cpv({"classification-cpv": "79340000"}) == ["79340000"]
    assert _pick_cpv({"classification-cpv": ["79340000", "79341200"]}) == ["79340000", "79341200"]
    assert _pick_cpv({"classification-cpv": [{"code": "79340000"}, {"value": "79341200"}]}) == ["79340000", "79341200"]
    assert _pick_cpv({}) == []


def test_parse_ted_date_variants():
    assert _parse_ted_date("20260415") is not None
    assert _parse_ted_date("2026-04-15") is not None
    assert _parse_ted_date("2026-04-15T10:00:00Z") is not None
    assert _parse_ted_date(None) is None


def test_notice_to_raw_uses_polish():
    notice = {
        "publication-number": "123456-2026",
        "notice-title": {"pol": "Usługi reklamowe", "eng": "Advertising services"},
        "description-lot": {"pol": "Szczegółowy opis"},
        "buyer-name": {"pol": "Urząd miasta"},
        "buyer-country": "POL",
        "publication-date": "20260410",
        "deadline-receipt-tender-date-lot": "20260510",
        "classification-cpv": ["79340000"],
    }
    raw = _notice_to_raw(notice)
    assert raw is not None
    assert raw.external_id == "123456-2026"
    assert raw.title == "Usługi reklamowe"
    assert raw.description == "Szczegółowy opis"
    assert raw.organization == "Urząd miasta"
    assert raw.cpv_codes == ["79340000"]
    assert raw.published_at is not None
    assert raw.deadline is not None
    assert "123456-2026" in raw.url


def test_notice_without_publication_number_is_skipped():
    assert _notice_to_raw({"notice-title": {"pol": "Brak ID"}}) is None


def test_fetch_paginates_and_stops_on_empty():
    adapter = TedAdapter()
    page1 = {
        "notices": [
            {
                "publication-number": "1",
                "notice-title": {"pol": "Kampania reklamowa"},
                "buyer-name": {"pol": "Urząd X"},
                "classification-cpv": ["79341400"],
                "publication-date": "20260420",
            }
        ],
        "totalNoticeCount": 1,
    }
    page2 = {"notices": []}

    call_seq = [page1, page2]

    def side_effect(*args, **kwargs):
        payload = call_seq.pop(0) if call_seq else {"notices": []}
        return _fake_response(payload)

    with patch.object(adapter, "http_post", side_effect=side_effect), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()

    assert len(out) == 1
    assert out[0].external_id == "1"
