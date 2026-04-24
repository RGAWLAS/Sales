"""Generic adapter for scraping corporate news / announcement pages.

Some companies publish procurement-relevant information not in a
dedicated tender portal but mixed into their general news feed.
Keyword-only filtering (configured in ``filters.yml``) is what decides
whether a specific news item is marketing/advertising-relevant — the
adapter just scrapes every card on the page and tags it as an
``EARLY_SIGNAL``.

All instances are parametrised; adding a new source is a one-line
change in ``registry.py``:

    NewsPageSignalAdapter(
        base_url="example.com",
        source_slug="example",
        display_name="Example — Aktualności",
        listing_path="/aktualnosci",
    )
"""
from __future__ import annotations

from typing import List, Optional, Sequence
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


class NewsPageSignalAdapter(BaseAdapter):
    """Scrape a corporate news listing page and tag rows as EARLY_SIGNAL."""

    request_delay_seconds = 2.0

    def __init__(
        self,
        *,
        base_url: str,
        source_slug: str,
        display_name: str,
        listing_path: str,
        fallback_paths: Sequence[str] = (),
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.source_id = f"news_{source_slug}"
        self.source_name = display_name
        self.listing_paths = (listing_path, *fallback_paths)
        super().__init__()

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("%s: listing unreachable", self.source_id)
            return []
        soup = BeautifulSoup(html, "lxml")
        return self._parse(soup)

    def _fetch_listing(self, session) -> Optional[str]:
        for path in self.listing_paths:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    return resp.text
            except Exception as exc:
                self.log.debug("%s: %s unreachable: %s", self.source_id, url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        containers = soup.select(
            "article, li.post, li.news-item, div.post, div.news-item, "
            "div.entry, div.article"
        )
        for c in containers:
            heading = c.find(["h1", "h2", "h3", "h4"])
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
            anchor = (heading.find("a", href=True) if heading else None) or c.find("a", href=True)
            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 12:
                continue
            href = anchor["href"] if anchor else ""
            url = urljoin(self.base_url + "/", href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"{self.source_id}::{title[:120]}"
            if ext_id in seen:
                continue
            seen.add(ext_id)

            lead = c.find(["p", "div.lead", "div.excerpt"])
            description = " ".join(lead.get_text(" ", strip=True).split()) if lead else title

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=description[:2000],
                    organization=self.source_name,
                    url=url,
                    category="EARLY_SIGNAL",
                )
            )

        self.log.info("%s: fetched %d items", self.source_id, len(out))
        return out
