"""Adapter for Synthos Group tender notices.

Synthos publishes active tenders on ``/biezace-ogloszenia-i-przetargi``
as a list of article cards with a title, a short lead, and a link to a
detail page or PDF.

Strategy: static HTML scraping.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.synthosgroup.com"
LISTING_PATHS = (
    "/biezace-ogloszenia-i-przetargi",
    "/ogloszenia-i-przetargi",
    "/przetargi",
)


class SynthosAdapter(BaseAdapter):
    source_id = "synthos"
    source_name = "Synthos Group"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("synthos: listing unreachable")
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
                self.log.debug("synthos: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        # Prefer article / post containers.
        containers = soup.select("article, li.post, div.post, div.news-item, div.announcement")
        if not containers:
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
            ext_id = url or f"synthos::{title[:120]}"
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

        self.log.info("synthos: fetched %d items", len(out))
        return out
