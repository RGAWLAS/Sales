"""Adapter for Polpharma's procurement announcements.

Polpharma publishes tender notices in the corporate news section,
filtered by category: ``/aktualnosci/kategoria/ogloszenia``. The page
renders as a list of news cards with a title and a link to the detail
article.

Strategy: static HTML scraping.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.polpharma.pl"
LISTING_PATHS = (
    "/aktualnosci/kategoria/ogloszenia",
    "/aktualnosci/ogloszenia",
    "/ogloszenia",
)


class PolpharmaAdapter(BaseAdapter):
    source_id = "polpharma"
    source_name = "Polpharma — Ogłoszenia"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("polpharma: listing unreachable")
            return []
        soup = BeautifulSoup(html, "lxml")
        return self._parse(soup)

    def _fetch_listing(self, session) -> Optional[str]:
        for path in LISTING_PATHS:
            url = urljoin(BASE, path)
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    return resp.text
            except Exception as exc:
                self.log.debug("polpharma: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        containers = soup.select("article, li.news-item, div.news-item, div.post, div.entry")
        if not containers:
            # Fallback: any heading with a nearby link inside the main column.
            containers = soup.find_all(["article"])

        for c in containers:
            heading = c.find(["h1", "h2", "h3", "h4"])
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
            anchor = c.find("a", href=True)
            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 8:
                continue
            href = anchor["href"] if anchor else ""
            url = urljoin(BASE, href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"polpharma::{title[:120]}"
            if ext_id in seen:
                continue
            seen.add(ext_id)
            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=url,
                )
            )

        self.log.info("polpharma: fetched %d items", len(out))
        return out
