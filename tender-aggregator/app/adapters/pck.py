"""Adapter for Polski Czerwony Krzyż (pck.pl).

PCK publishes procurement announcements in two WordPress-style sections:
``/przetargi`` (formal tenders) and ``/ogloszenia`` (general notices).
Both render identically as a list of article cards, so we scrape both
and merge the results.

Strategy: static HTML scraping with BeautifulSoup.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://pck.pl"
LISTING_PATHS = ("/przetargi", "/ogloszenia")


class PckAdapter(BaseAdapter):
    source_id = "pck"
    source_name = "Polski Czerwony Krzyż"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        out: List[RawTender] = []
        seen: set[str] = set()
        for path in LISTING_PATHS:
            url = urljoin(BASE, path)
            try:
                resp = self.http_get(session, url, timeout=30)
            except Exception as exc:
                self.log.debug("pck: %s unreachable: %s", url, exc)
                continue
            if resp.status_code != 200 or not resp.text:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for item in self._parse_section(soup):
                if item.external_id in seen:
                    continue
                seen.add(item.external_id)
                out.append(item)
        self.log.info("pck: fetched %d items", len(out))
        return out

    def _parse_section(self, soup: BeautifulSoup) -> List[RawTender]:
        results: List[RawTender] = []

        # Primary shape: WordPress-ish post cards.
        containers = soup.select("article, li.post, div.post, div.entry, div.news-item")
        if not containers:
            containers = soup.select("main a, div.content a")

        for c in containers:
            heading = c.find(["h1", "h2", "h3", "h4"]) if hasattr(c, "find") else None
            title = ""
            if heading is not None:
                title = " ".join(heading.get_text(" ", strip=True).split())

            anchor = c.find("a", href=True) if hasattr(c, "find") else None
            if anchor is None and getattr(c, "name", "") == "a":
                anchor = c

            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())

            if not title or len(title) < 8:
                continue

            href = anchor["href"] if anchor else ""
            url = urljoin(BASE, href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"pck::{title[:120]}"

            results.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=url,
                )
            )
        return results
