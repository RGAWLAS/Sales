"""Adapter for platforms hosted on Marketplanet (OnePlace).

Marketplanet powers multiple buyer portals under different hostnames,
e.g. ``oneplace.marketplanet.pl`` and ``zakupy2.mbank.pl``. A single
adapter parametrised by base URL handles all of them.

Strategy: static HTML scraping. The public listing page is
``/cgi-bin/modnn/modnn.cgi?md=adverts`` (legacy), newer sites use
``/oneplace/pl/public/`` or a similar path. Try each in order.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


_DETAIL_HREF_RE = re.compile(r"(?:auctions|advert|adverts|demand|postepowanie)/(?:show/|details/|preview/|id/)?(\d+)", re.IGNORECASE)


class MarketplanetAdapter(BaseAdapter):
    LISTING_PATHS = (
        "/cgi-bin/modnn/modnn.cgi?md=adverts",
        "/oneplace/pl/public/",
        "/public/postepowania",
        "/public/demand",
    )

    def __init__(self, base_url: str, source_slug: str, display_name: str) -> None:
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.source_id = f"marketplanet_{source_slug}"
        self.source_name = display_name
        super().__init__()

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("%s: no accessible listing page", self.source_id)
            return []
        soup = BeautifulSoup(html, "lxml")
        return self._parse(soup)

    def _fetch_listing(self, session) -> Optional[str]:
        for path in self.LISTING_PATHS:
            url = urljoin(self.base_url + "/", path.lstrip("/"))
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    self.log.debug("%s: using %s", self.source_id, url)
                    return resp.text
            except Exception as exc:
                self.log.debug("%s: %s unreachable: %s", self.source_id, url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        seen: set[str] = set()
        out: List[RawTender] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            m = _DETAIL_HREF_RE.search(href)
            if not m:
                continue
            ext_id = m.group(1)
            if ext_id in seen:
                continue
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 5:
                continue
            seen.add(ext_id)

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=urljoin(self.base_url + "/", href),
                )
            )

        self.log.info("%s: fetched %d items", self.source_id, len(out))
        return out
