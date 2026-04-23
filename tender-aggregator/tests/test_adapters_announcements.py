"""Tests for announcement-style adapters: PCK, Synthos, BIP ULC, Polpharma.

All four scrape server-rendered HTML. We mock the HTTP layer and feed
representative fragments to verify the parsing paths.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.bip_ulc import BipUlcAdapter
from app.adapters.pck import PckAdapter
from app.adapters.polpharma import PolpharmaAdapter
from app.adapters.synthos import SynthosAdapter


def _fake_html(text: str):
    r = MagicMock()
    r.status_code = 200
    r.text = text
    r.raise_for_status = MagicMock()
    return r


PCK_HTML = """
<html><body>
<main>
  <article>
    <h2>Zapytanie ofertowe na kampanię reklamową</h2>
    <a href="/przetargi/kampania-2026">Szczegóły</a>
  </article>
  <article>
    <h2>Dostawa środków higienicznych</h2>
    <a href="/przetargi/higiena-2026">Szczegóły</a>
  </article>
</main>
</body></html>
"""


def test_pck_parses_articles():
    adapter = PckAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(PCK_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    # Two paths are scraped (/przetargi, /ogloszenia); with the same mocked
    # HTML they'd return the same items. Dedup keeps just one of each.
    assert "Zapytanie ofertowe na kampanię reklamową" in titles
    assert "Dostawa środków higienicznych" in titles
    assert len({r.external_id for r in out}) == len(out)


SYNTHOS_HTML = """
<html><body>
  <article>
    <h3>Postępowanie na usługi marketingowe</h3>
    <a href="/przetargi/usługi-marketingowe.pdf">Pobierz</a>
  </article>
  <article>
    <h3>Zakup chemikaliów</h3>
    <a href="https://external.example.com/details/9">szczegóły</a>
  </article>
</body></html>
"""


def test_synthos_parses_listing_external_and_internal_links():
    adapter = SynthosAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(SYNTHOS_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert len(out) == 2
    urls = [r.url for r in out]
    assert any("external.example.com" in u for u in urls)
    assert any(u.startswith("https://www.synthosgroup.com/") for u in urls)


BIP_HTML = """
<html><body>
<table>
  <tr><td><a href="/index.php?dok=12345">Ogłoszenie o zamówieniu publicznym — kampania informacyjna</a></td></tr>
  <tr><td><a href="/bip/67890.html">Przetarg nieograniczony — remont budynku</a></td></tr>
  <tr><td><a href="/">Strona główna</a></td></tr>
</table>
</body></html>
"""


def test_bip_ulc_extracts_ids():
    adapter = BipUlcAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(BIP_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    ids = {r.external_id for r in out}
    assert "12345" in ids
    assert "67890" in ids


POLPHARMA_HTML = """
<html><body>
  <article>
    <h3>Zapytanie ofertowe — usługi kreacji reklamowej</h3>
    <a href="/aktualnosci/kreacja-2026">Czytaj więcej</a>
  </article>
  <article>
    <h3>Dostawa substratów do produkcji</h3>
    <a href="/aktualnosci/substraty-2026">Czytaj więcej</a>
  </article>
</body></html>
"""


def test_polpharma_parses_articles():
    adapter = PolpharmaAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(POLPHARMA_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    assert "Zapytanie ofertowe — usługi kreacji reklamowej" in titles
    assert "Dostawa substratów do produkcji" in titles
    assert all(r.url.startswith("https://www.polpharma.pl/") for r in out)


def test_empty_listing_does_not_crash():
    for adapter in (PckAdapter(), SynthosAdapter(), BipUlcAdapter(), PolpharmaAdapter()):
        with patch.object(adapter, "http_get", return_value=_fake_html("<html></html>")), \
             patch.object(adapter, "request_delay_seconds", 0):
            assert adapter.fetch() == []
