"""Adapter for platformazakupowa.pl (Open Nexus).

Strategy: Open Nexus exposes a public listing URL that returns rendered
HTML with every currently open "postępowanie" as a list of cards. Each
card links to the detail page with a stable auction id in the URL.

There is no fully public REST API (the one under ``/api/`` requires a
per-buyer token), but the listing HTML is server-rendered and stable
enough for BeautifulSoup.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://platformazakupowa.pl"
LISTING_PATHS = (
    "/all?limit=100",
    "/all",
    "/transakcja/public",
)

_AUCTION_HREF_RE = re.compile(r"/transakcja/(\d+)")


class PlatformaZakupowaAdapter(BaseAdapter):
    source_id = "platformazakupowa"
    source_name = "Platforma Zakupowa (Open Nexus)"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()

        html = self._fetch_listing(session)
        if not html:
            self.log.warning("platformazakupowa: listing page unreachable")
            return []

        soup = BeautifulSoup(html, "lxml")
        return self._parse(soup)

    def _fetch_listing(self, session) -> Optional[str]:
        for path in LISTING_PATHS:
            url = urljoin(BASE, path)
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    self.log.debug("platformazakupowa: using %s", url)
                    return resp.text
            except Exception as exc:
                self.log.debug("platformazakupowa: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        seen_ids: set[str] = set()
        out: List[RawTender] = []

        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            m = _AUCTION_HREF_RE.search(href)
            if not m:
                continue
            ext_id = m.group(1)
            if ext_id in seen_ids:
                continue
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 5:
                continue
            seen_ids.add(ext_id)

            organization = _org_from_siblings(anchor) or ""

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=title,
                    organization=organization,
                    url=urljoin(BASE, href),
                )
            )

        self.log.info("platformazakupowa: fetched %d items", len(out))
        return out


def _org_from_siblings(anchor) -> Optional[str]:
    """Heuristic: look for a nearby element that names the buyer.

    The Open Nexus listing typically puts the buyer name in a sibling or
    parent element; we walk up a few levels and pick a short string that
    resembles an organization name.
    """
    node = anchor
    for _ in range(4):
        parent = getattr(node, "parent", None)
        if parent is None:
            return None
        for candidate in parent.find_all(string=True, recursive=True):
            text = candidate.strip()
            if not text or len(text) < 4 or len(text) > 200:
                continue
            if any(marker in text for marker in ("Sp.", "S.A.", "Urząd", "Instytut", "Spółdzielnia", "Spółka")):
                return text[:200]
        node = parent
    return None
