"""Tests for the custom single-instance portal adapters (PZU, Tauron SWOZ, PGNiG).

We mock the HTTP layer with representative HTML fragments and verify
that the adapter pulls out the expected RawTenders.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.pgnig import PgnigAdapter
from app.adapters.pzu import PzuAdapter
from app.adapters.tauron_swoz import TauronSwozAdapter


def _fake_html(text: str):
    r = MagicMock()
    r.status_code = 200
    r.text = text
    r.raise_for_status = MagicMock()
    return r


TAURON_HTML = """
<html><body>
<table>
  <tr><td><a href="/servlet/HomeServlet?MP_module_id=42&action=view">
    Usługi reklamowe dla Grupy Tauron
  </a></td></tr>
  <tr><td><a href="/servlet/HomeServlet?MP_module_id=55">
    Dostawa słupów energetycznych
  </a></td></tr>
  <tr><td><a href="/kontakt.html">Kontakt</a></td></tr>
</table>
</body></html>
"""


def test_tauron_swoz_parses_listing():
    adapter = TauronSwozAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(TAURON_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert {r.external_id for r in out} == {"42", "55"}
    assert all(r.url.startswith("https://swoz.tauron.pl/") for r in out)


PGNIG_HTML = """
<html><body>
  <ul>
    <li><a href="/pgnig/servlet/HomeServlet?MP_module=100">Zakup czasu antenowego</a></li>
    <li><a href="/pgnig/servlet/HomeServlet?postepowanie_id=200">Dostawa gazu ziemnego</a></li>
    <li><a href="/kontakt">Kontakt</a></li>
  </ul>
</body></html>
"""


def test_pgnig_parses_listing():
    adapter = PgnigAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(PGNIG_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert {r.external_id for r in out} == {"100", "200"}


PZU_HTML = """
<html><body>
  <main>
    <article>
      <h3>Kampania reklamowa PZU Życie 2026</h3>
      <p>Krótki opis postępowania.</p>
      <a href="/grupa-pzu/przetarg/1234.pdf">pobierz PDF</a>
    </article>
    <article>
      <h3>Zakup mediów na kwartał</h3>
      <a href="https://zakupy.external.com/p/5678">szczegóły</a>
    </article>
    <article>
      <h3>Nagłówek bez linku tylko z tekstem</h3>
    </article>
  </main>
</body></html>
"""


def test_pzu_parses_article_containers():
    adapter = PzuAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(PZU_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    assert "Kampania reklamowa PZU Życie 2026" in titles
    assert "Zakup mediów na kwartał" in titles
    # External link preserved as-is.
    ext_links = [r.url for r in out if "external.com" in r.url]
    assert len(ext_links) == 1


def test_pzu_falls_back_to_headings_when_no_articles():
    html = """
    <html><body>
      <div>
        <h3>Postępowanie w trybie z wolnej ręki — kampania</h3>
        <a href="/x.pdf">dokument</a>
        <h3>Drugie ogłoszenie</h3>
        <a href="/y.pdf">dokument</a>
      </div>
    </body></html>
    """
    adapter = PzuAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(html)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert len(out) >= 2
    assert any("kampania" in r.title for r in out)
