"""Tests for Baltona, MMP Online, Save The Children adapters."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.adapters.baltona import BaltonaAdapter
from app.adapters.mmp_online import MmpOnlineAdapter
from app.adapters.save_the_children import SaveTheChildrenAdapter, _extract_deadline


def _fake_html(text: str):
    r = MagicMock()
    r.status_code = 200
    r.text = text
    r.raise_for_status = MagicMock()
    return r


BALTONA_HTML = """
<html><body>
  <article class="item">
    <h2><a href="/index.php/przetargi/kampania-2026">Kampania reklamowa dla Baltona</a></h2>
  </article>
  <article class="item">
    <h2><a href="/index.php/przetargi/dostawa-2026">Dostawa wyposażenia sklepów</a></h2>
  </article>
</body></html>
"""


def test_baltona_parses_articles():
    adapter = BaltonaAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(BALTONA_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    assert "Kampania reklamowa dla Baltona" in titles
    assert "Dostawa wyposażenia sklepów" in titles
    assert all(r.url.startswith("https://www.baltona.pl/") for r in out)


MMP_HTML = """
<html><body>
  <div class="post">
    <h3><a href="/przetargi/usługi-marketingowe-2026">Usługi marketingowe 2026</a></h3>
  </div>
  <div class="post">
    <h3><a href="/przetargi/dostawa-materiałów">Dostawa materiałów promocyjnych</a></h3>
  </div>
</body></html>
"""


def test_mmp_online_parses_posts():
    adapter = MmpOnlineAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(MMP_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()
    titles = [r.title for r in out]
    assert "Usługi marketingowe 2026" in titles
    assert "Dostawa materiałów promocyjnych" in titles


STC_HTML = """
<html><body>
  <div class="view-content">
    <div class="views-row">
      <h3><a href="/tenders/media-buying-2026">Media buying services for campaigns</a></h3>
      <div class="lead">Closing date: 2026-05-15 — international opportunity</div>
    </div>
    <div class="views-row">
      <h3><a href="/tenders/office-supplies-2026">Office supplies framework agreement</a></h3>
      <div class="lead">Deadline: 2026-06-01</div>
    </div>
  </div>
</body></html>
"""


def test_save_the_children_parses_rows_and_deadline():
    adapter = SaveTheChildrenAdapter()
    with patch.object(adapter, "http_get", return_value=_fake_html(STC_HTML)), \
         patch.object(adapter, "request_delay_seconds", 0):
        out = adapter.fetch()

    by_title = {r.title: r for r in out}
    assert "Media buying services for campaigns" in by_title
    assert "Office supplies framework agreement" in by_title
    assert by_title["Media buying services for campaigns"].deadline is not None
    assert by_title["Office supplies framework agreement"].deadline is not None


def test_extract_deadline_shapes():
    assert _extract_deadline("Closing date: 2026-05-15 at noon") is not None
    assert _extract_deadline("Deadline: 15/05/2026") is not None
    assert _extract_deadline("No date here") is None


def test_empty_listing_does_not_crash():
    for adapter in (BaltonaAdapter(), MmpOnlineAdapter(), SaveTheChildrenAdapter()):
        with patch.object(adapter, "http_get", return_value=_fake_html("<html></html>")), \
             patch.object(adapter, "request_delay_seconds", 0):
            assert adapter.fetch() == []
