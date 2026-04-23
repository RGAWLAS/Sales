"""Adapter for PGNiG's procurement portal (przetargi.pgnig.pl).

Strategy: static HTML scraping. The PGNiG portal exposes an open-access
listing of current postępowania on the landing page itself; each item
links to a detail page with a numeric id in the URL.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://przetargi.pgnig.pl"
LISTING_PATHS = (
    "/",
    "/pgnig/servlet/HomeServlet",
    "/pgnig/public",
    "/postepowania",
)
_DETAIL_HREF_RE = re.compile(
    r"(?:MP_module|postepowanie_id|demand|auction|MP_postepowanie_id)[=/](\d+)",
    re.IGNORECASE,
)


class PgnigAdapter(BaseAdapter):
    source_id = "pgnig"
    source_name = "PGNiG Przetargi"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("pgnig: listing unreachable")
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
                self.log.debug("pgnig: %s unreachable: %s", url, exc)
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
                    url=urljoin(BASE, href),
                )
            )
        self.log.info("pgnig: fetched %d items", len(out))
        return out
