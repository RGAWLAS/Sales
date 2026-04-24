"""Adapter for BIP Urzędu Lotnictwa Cywilnego (bip.ulc.gov.pl).

BIP pages follow a standard Polish government template: announcements
are rendered as tables or lists with a date, title and a link to the
detail subpage (typically ``?dok=<id>`` or ``/bip/<id>.html``).

Strategy: static HTML scraping. The BIP template is mostly server-rendered
and accessible without JS.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://bip.ulc.gov.pl"
LISTING_PATHS = (
    "/index.php/ogloszenia/zamowienia-publiczne",
    "/index.php/ogloszenia",
    "/zamowienia-publiczne",
    "/przetargi",
)
_DETAIL_HREF_RE = re.compile(r"(?:\?dok=|/bip/|/index\.php\?.*?id=)(\d+)", re.IGNORECASE)


class BipUlcAdapter(BaseAdapter):
    source_id = "bip_ulc"
    source_name = "BIP Urząd Lotnictwa Cywilnego"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("bip_ulc: listing unreachable")
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
                self.log.debug("bip_ulc: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 10:
                continue

            m = _DETAIL_HREF_RE.search(href)
            ext_id: Optional[str]
            if m:
                ext_id = m.group(1)
            else:
                # Fall back to title-based id if the URL lacks a numeric id.
                # Still dedup-safe via content_hash on source+external_id.
                path = urlparse(href).path
                if not path or path in ("/", "#"):
                    continue
                ext_id = path

            if ext_id in seen:
                continue
            seen.add(ext_id)

            full_url = urljoin(BASE, href) if not urlparse(href).netloc else href
            out.append(
                RawTender(
                    external_id=str(ext_id),
                    title=title[:1000],
                    description=title,
                    organization=self.source_name,
                    url=full_url,
                )
            )

        self.log.info("bip_ulc: fetched %d items", len(out))
        return out
