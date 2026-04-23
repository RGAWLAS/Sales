"""Adapter for MMP Online — procurement announcements.

MMP Online publishes procurement notices at ``/przetargi``. The page
uses a flat list of posts with heading + short lead + detail link.

Strategy: static HTML scraping.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://mmponline.pl"
LISTING_PATHS = (
    "/przetargi",
    "/przetargi/",
    "/ogloszenia",
)


class MmpOnlineAdapter(BaseAdapter):
    source_id = "mmp_online"
    source_name = "MMP Online — Przetargi"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("mmp_online: listing unreachable")
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
                self.log.debug("mmp_online: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        containers = soup.select("article, div.post, li.post, div.entry, div.news-item")
        for c in containers:
            heading = c.find(["h1", "h2", "h3", "h4"])
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
            anchor = (heading.find("a", href=True) if heading else None) or c.find("a", href=True)
            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 8:
                continue
            href = anchor["href"] if anchor else ""
            url = urljoin(BASE, href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"mmp_online::{title[:120]}"
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

        self.log.info("mmp_online: fetched %d items", len(out))
        return out
