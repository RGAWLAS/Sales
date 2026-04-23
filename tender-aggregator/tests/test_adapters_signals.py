"""Tests for the EARLY_SIGNAL adapters: Wirtualne Media + generic news."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.news_signal import NewsPageSignalAdapter
from app.adapters.wirtualne_media import WirtualneMediaAdapter


def _fake_html(text: str):
    r = MagicMock()
    r.status_code = 200
    r.text = text
    r.raise_for_status = MagicMock()
    return r


WM_HTML = """
<html><body>
  <article>
    <h2><a href="/artykul/kampania-2026">Startuje przetarg na kampanię marki X — budżet 10 mln PLN</a></h2>
    <p class="lead">Firma X ogłosiła przetarg na obsługę kampanii wizerunkowej.</p>
  </article>
  <article>
    <h2><a href="/artykul/pitch-y">Agencje mediowe walczą o budżet firmy Y</a></h2>
    <p>Pitch trwa do końca miesiąca.</p>
  </article>
</body></html>
"""


def test_wirtualne_media_marks_rows_as_early_signal():
    adapter = WirtualneMediaAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(WM_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    assert len(out) == 2
    for raw in out:
        assert raw.category == "EARLY_SIGNAL"
    assert any("Kampania" in r.title or "kampani" in r.title for r in out)


NEWS_HTML = """
<html><body>
  <article class="post">
    <h3><a href="/aktualnosci/nowa-kampania">Bank uruchamia nową kampanię reklamową</a></h3>
    <p>Kampania ma wystartować jesienią 2026.</p>
  </article>
  <article class="post">
    <h3><a href="/aktualnosci/nagrody">Zdobyliśmy nagrodę branżową</a></h3>
  </article>
</body></html>
"""


def test_news_signal_adapter_independent_instances():
    a = NewsPageSignalAdapter(
        base_url="example.com",
        source_slug="demo_a",
        display_name="Demo A",
        listing_path="/aktualnosci",
    )
    b = NewsPageSignalAdapter(
        base_url="other.example.com",
        source_slug="demo_b",
        display_name="Demo B",
        listing_path="/news",
    )
    assert a.source_id == "news_demo_a"
    assert b.source_id == "news_demo_b"
    assert a.base_url == "https://example.com"
    assert b.base_url == "https://other.example.com"


def test_news_signal_adapter_tags_category_and_parses_descriptions():
    adapter = NewsPageSignalAdapter(
        base_url="example.com",
        source_slug="demo",
        display_name="Demo News",
        listing_path="/aktualnosci",
    )
    with patch.object(adapter, "http_get", return_value=_fake_html(NEWS_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()

    assert len(out) == 2
    assert all(r.category == "EARLY_SIGNAL" for r in out)
    by_title = {r.title: r for r in out}
    assert "Bank uruchamia nową kampanię reklamową" in by_title
    first = by_title["Bank uruchamia nową kampanię reklamową"]
    assert "jesień" in first.description or "jesienią" in first.description


def test_news_signal_adapter_returns_empty_on_bad_html():
    adapter = NewsPageSignalAdapter(
        base_url="example.com",
        source_slug="demo",
        display_name="Demo",
        listing_path="/x",
    )
    with patch.object(adapter, "http_get", return_value=_fake_html("<html></html>")), \
         patch.object(adapter, "request_delay_seconds", 0):
        assert adapter.fetch() == []
