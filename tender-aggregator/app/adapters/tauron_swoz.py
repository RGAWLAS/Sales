"""Adapter for SWOZ — Tauron's procurement portal (swoz.tauron.pl).

Strategy: static HTML scraping with BeautifulSoup. SWOZ renders its
public listing fully server-side; JS on the page is used only for
optional filtering widgets which we don't need. No public JSON API is
exposed for unauthenticated users.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://swoz.tauron.pl"
LISTING_PATHS = (
    "/servlet/HomeServlet",
    "/public",
    "/postepowania",
    "/",
)
_DETAIL_HREF_RE = re.compile(
    r"(?:MP_module_id|MP_postepowanie_id|postepowanie_id|demand_id)=(\d+)",
    re.IGNORECASE,
)


class TauronSwozAdapter(BaseAdapter):
    source_id = "tauron_swoz"
    source_name = "Tauron SWOZ"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("tauron_swoz: listing unreachable")
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
                self.log.debug("tauron_swoz: %s unreachable: %s", url, exc)
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
        self.log.info("tauron_swoz: fetched %d items", len(out))
        return out
