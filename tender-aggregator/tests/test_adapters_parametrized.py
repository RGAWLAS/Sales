"""Tests for the parametrized HTML-scraping adapter pattern.

We don't exercise every tenant, but we do verify:
  - source_id / source_name / base_url are derived correctly per instance
  - Two instances are independent
  - Parsing of a representative HTML listing yields RawTenders
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.adapters.grupa_azoty import GrupaAzotyAdapter
from app.adapters.logintrade import LogintradeAdapter
from app.adapters.marketplanet import MarketplanetAdapter


def _fake_html_response(text: str):
    r = MagicMock()
    r.status_code = 200
    r.text = text
    r.raise_for_status = MagicMock()
    return r


# ---- Identity / parametrisation ---------------------------------------------

def test_logintrade_instances_are_independent():
    a = LogintradeAdapter(subdomain="lpp")
    b = LogintradeAdapter(subdomain="anwim", display_name="Anwim")
    assert a.source_id == "logintrade_lpp"
    assert b.source_id == "logintrade_anwim"
    assert a.base_url == "https://lpp.logintrade.net"
    assert b.base_url == "https://anwim.logintrade.net"
    assert b.source_name == "Anwim"


def test_marketplanet_accepts_bare_hostname():
    a = MarketplanetAdapter(
        base_url="oneplace.marketplanet.pl",
        source_slug="oneplace",
        display_name="OnePlace",
    )
    assert a.base_url == "https://oneplace.marketplanet.pl"
    assert a.source_id == "marketplanet_oneplace"


def test_grupa_azoty_strips_trailing_slash():
    a = GrupaAzotyAdapter(
        base_url="https://przetargi.grupaazoty.com/",
        source_slug="przetargi",
        display_name="GA",
    )
    assert a.base_url == "https://przetargi.grupaazoty.com"


# ---- Parsing -----------------------------------------------------------------

LOGINTRADE_LISTING_HTML = """
<html><body>
<table>
  <tr>
    <td><a href="/rejestracja/aktualneogloszenia.html?m=42&amp;kod=XYZ123">Usługi reklamowe na rok 2026</a></td>
    <td>LPP S.A.</td>
  </tr>
  <tr>
    <td><a href="/rejestracja/ustawz.html?kod=ABC999">Dostawa materiałów biurowych</a></td>
    <td>LPP S.A.</td>
  </tr>
  <tr>
    <td><a href="/inne/ignoruj.html">Bez sensownego id</a></td>
    <td>LPP S.A.</td>
  </tr>
</table>
</body></html>
"""


def test_logintrade_parses_listing_html():
    adapter = LogintradeAdapter(subdomain="lpp")
    with patch.object(adapter, "http_get", return_value=_fake_html_response(LOGINTRADE_LISTING_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    assert "Usługi reklamowe na rok 2026" in titles
    assert "Dostawa materiałów biurowych" in titles
    # "Bez sensownego id" should be excluded — no recognised id in href.
    assert all("Bez sensownego" not in t for t in titles)
    # Dedup by id.
    assert len({r.external_id for r in out}) == len(out)


MARKETPLANET_LISTING_HTML = """
<html><body>
  <ul>
    <li><a href="/auctions/show/12345">Kampania reklamowa Q2</a></li>
    <li><a href="/demand/67890">Audyt marketingowy</a></li>
    <li><a href="/contact">Kontakt</a></li>
  </ul>
</body></html>
"""


def test_marketplanet_parses_listing_html():
    adapter = MarketplanetAdapter(
        base_url="oneplace.marketplanet.pl",
        source_slug="oneplace",
        display_name="OnePlace",
    )
    with patch.object(adapter, "http_get", return_value=_fake_html_response(MARKETPLANET_LISTING_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert {r.external_id for r in out} == {"12345", "67890"}
    assert all(r.url.startswith("https://oneplace.marketplanet.pl/") for r in out)


GRUPA_AZOTY_LISTING_HTML = """
<html><body>
  <div class="tender-list">
    <a href="/przetarg/100">Kampania reklamowa roczna</a>
    <a href="/postepowanie/200">Dostawa stali</a>
    <a href="/karta-kontaktowa">Kontakt</a>
  </div>
</body></html>
"""


def test_grupa_azoty_parses_listing_html():
    adapter = GrupaAzotyAdapter(
        base_url="przetargi.grupaazoty.com",
        source_slug="przetargi",
        display_name="Grupa Azoty",
    )
    with patch.object(adapter, "http_get", return_value=_fake_html_response(GRUPA_AZOTY_LISTING_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert {r.external_id for r in out} == {"100", "200"}


def test_empty_listing_returns_empty_list():
    adapter = LogintradeAdapter(subdomain="lpp")
    with patch.object(adapter, "http_get", return_value=_fake_html_response("<html></html>")), \
         patch.object(adapter, "request_delay_seconds", 0):
        assert adapter.fetch() == []


def test_unreachable_listing_does_not_crash():
    """All listing URLs 5xx → adapter returns empty list, no exception."""
    import requests

    adapter = LogintradeAdapter(subdomain="doesnotexist")
    with patch.object(adapter, "http_get", side_effect=requests.ConnectionError("boom")), \
         patch.object(adapter, "request_delay_seconds", 0):
        assert adapter.fetch() == []
