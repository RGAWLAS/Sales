"""Adapter for Wirtualne Media — advertising industry news / tender column.

This is an editorial news feed, not a procurement platform. Articles on
``wirtualnemedia.pl/wiadomosci/reklama/przetargi`` are journalists'
mentions of upcoming tenders, agency reviews, pitches etc. — a useful
early-warning channel but not a formal procurement. We flag every row
from this source as ``EARLY_SIGNAL`` so the dashboard and digest can
separate it from real tenders.

Strategy: static HTML scraping (server-rendered list of article cards).
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.wirtualnemedia.pl"
LISTING_PATHS = (
    "/wiadomosci/reklama/przetargi",
    "/artykuly/reklama-przetargi",
    "/reklama/przetargi",
)


class WirtualneMediaAdapter(BaseAdapter):
    source_id = "wirtualnemedia_przetargi"
    source_name = "Wirtualne Media — Reklama: przetargi"
    request_delay_seconds = 2.0  # Be gentle on an editorial site.

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("wirtualnemedia: listing unreachable")
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
                self.log.debug("wirtualnemedia: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        containers = soup.select("article, li.article, div.article, div.news-item, div.entry")
        for c in containers:
            heading = c.find(["h1", "h2", "h3"])
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
            anchor = (heading.find("a", href=True) if heading else None) or c.find("a", href=True)
            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 12:
                continue
            href = anchor["href"] if anchor else ""
            url = urljoin(BASE, href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"wm::{title[:120]}"
            if ext_id in seen:
                continue
            seen.add(ext_id)
            # Pull a short lead paragraph for richer keyword matching.
            lead = c.find(["p", "div.lead", "div.desc"])
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

        self.log.info("wirtualnemedia: fetched %d items", len(out))
        return out
