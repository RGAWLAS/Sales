"""Adapter for Veolia's procurement portal section (veolia.pl).

Strategy: static HTML scraping. Veolia publishes its current
postępowania on a single info page on the corporate website. There's
no dedicated procurement platform URL to hit; we scrape the info page
and extract both in-page cards and outbound links to external auctions.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.veolia.pl"
LISTING_PATHS = (
    "/platforma-zakupowa",
    "/zakupy",
    "/przetargi",
)


class VeoliaAdapter(BaseAdapter):
    source_id = "veolia"
    source_name = "Veolia — Platforma Zakupowa"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("veolia: listing unreachable")
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
                self.log.debug("veolia: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        """Extract heading-style items (h2/h3/card titles) and their links."""
        out: List[RawTender] = []
        seen: set[str] = set()

        # Veolia uses either <article> cards or a list of <a> links inside
        # the main content area. We accept both by looking for any <a> whose
        # title text is long enough to plausibly be a tender subject.
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 15:
                continue
            # Skip pure navigation items.
            if title.lower() in {"więcej", "czytaj więcej", "zobacz", "zobacz więcej", "wróć", "kontakt"}:
                continue
            # Heuristic: tender links point to a subpage under /platforma-zakupowa,
            # /zakupy/... or to an external auction platform.
            parsed = urlparse(href)
            if not (parsed.path.startswith(("/platforma", "/zakupy", "/przetargi"))
                    or parsed.netloc and parsed.netloc != urlparse(BASE).netloc):
                continue
            key = href if parsed.netloc else urljoin(BASE, href)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                RawTender(
                    external_id=key,
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=key,
                )
            )

        self.log.info("veolia: fetched %d items", len(out))
        return out
