"""Adapter for white-label platforms running on Logintrade.

Each Logintrade tenant is served from ``{subdomain}.logintrade.net`` with
the same public listing URLs, so one class parametrised by subdomain is
enough.

Strategy: static HTML scraping with BeautifulSoup. Logintrade listings
are fully server-rendered; no JS execution is required. The public
unauthenticated URL ``/rejestracja/ogloszenia.html`` lists every open
procedure for a given tenant.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


_DETAIL_HREF_RE = re.compile(r"/rejestracja/(?:aktualneogloszenia|ustawz|ustawnz)\.html\?.*?(?:m|kod|id|ID)=(\w+)")
_ALT_DETAIL_HREF_RE = re.compile(r"/rejestracja/(?:przetargi\d*|zapytanie)\.html\?[^'\" ]*")


class LogintradeAdapter(BaseAdapter):
    LISTING_PATHS = (
        "/rejestracja/ogloszenia.html",
        "/rejestracja/przetargi.html",
        "/rejestracja/aktualneogloszenia.html",
    )

    def __init__(self, subdomain: str, display_name: Optional[str] = None) -> None:
        self.subdomain = subdomain
        self.source_id = f"logintrade_{subdomain}"
        self.source_name = display_name or f"Logintrade ({subdomain})"
        self.base_url = f"https://{subdomain}.logintrade.net"
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
            url = urljoin(self.base_url, path)
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    self.log.debug("%s: using %s", self.source_id, url)
                    return resp.text
            except Exception as exc:
                self.log.debug("%s: %s unreachable: %s", self.source_id, url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        seen_ids: set[str] = set()
        out: List[RawTender] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            ext_id: Optional[str] = None

            m = _DETAIL_HREF_RE.search(href)
            if m:
                ext_id = m.group(1)
            elif _ALT_DETAIL_HREF_RE.search(href):
                # Fall back to the full path as id (dedup still works).
                ext_id = href.split("?", 1)[-1][:80]

            if not ext_id or ext_id in seen_ids:
                continue
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 5:
                continue
            seen_ids.add(ext_id)

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=urljoin(self.base_url, href),
                )
            )

        self.log.info("%s: fetched %d items", self.source_id, len(out))
        return out
