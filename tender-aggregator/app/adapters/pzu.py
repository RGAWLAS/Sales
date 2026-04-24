"""Adapter for PZU's procurement announcements page.

Strategy: static HTML scraping. PZU publishes "postępowania przetargowe"
as an article list on ``pzu.pl/grupa-pzu/o-nas/postepowania-przetargowe``.
Each entry has a heading (tender subject) and a link to a PDF or a detail
subpage. We treat each article/link as a RawTender.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.pzu.pl"
LISTING_PATHS = (
    "/grupa-pzu/o-nas/postepowania-przetargowe",
    "/grupa-pzu/o-nas/przetargi",
    "/przetargi",
)


class PzuAdapter(BaseAdapter):
    source_id = "pzu"
    source_name = "PZU — Postępowania przetargowe"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("pzu: listing unreachable")
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
                self.log.debug("pzu: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        """Iterate over article headings; the nearest anchor is the detail/PDF link."""
        out: List[RawTender] = []
        seen: set[str] = set()

        # Primary pass: each <article> or <li> in the list holds one tender.
        containers = soup.select("article, li.tender, li.postepowanie, div.tender-item")
        if containers:
            for c in containers:
                raw = _extract_container(c)
                if raw and raw.external_id not in seen:
                    seen.add(raw.external_id)
                    out.append(raw)

        # Fallback: extract from headings in the main content column.
        if not out:
            for heading in soup.find_all(["h2", "h3", "h4"]):
                title = " ".join(heading.get_text(" ", strip=True).split())
                if not title or len(title) < 10:
                    continue
                anchor = heading.find("a", href=True) or (heading.find_next("a", href=True))
                href = anchor["href"] if anchor else ""
                key = urljoin(BASE, href) if href else f"pzu::{title[:120]}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    RawTender(
                        external_id=key,
                        title=title[:1000],
                        description=title,
                        organization="PZU",
                        url=key if href else "",
                    )
                )

        self.log.info("pzu: fetched %d items", len(out))
        return out


def _extract_container(container) -> Optional[RawTender]:
    """Pull (title, link) out of one container element."""
    heading = container.find(["h2", "h3", "h4"])
    title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
    if not title or len(title) < 5:
        link = container.find("a", href=True)
        if not link:
            return None
        title = " ".join(link.get_text(" ", strip=True).split())
        if not title or len(title) < 5:
            return None

    anchor = container.find("a", href=True)
    href = anchor["href"] if anchor else ""
    if href and not urlparse(href).netloc:
        href = urljoin(BASE, href)

    ext_id = href or f"pzu::{title[:120]}"
    return RawTender(
        external_id=ext_id,
        title=title[:1000],
        description=title,
        organization="PZU",
        url=href,
    )
