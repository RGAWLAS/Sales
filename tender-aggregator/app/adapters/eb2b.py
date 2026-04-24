"""Adapter for platforms hosted on the eB2B white-label procurement system.

Each client of eB2B (e.g. NASK, KOWR) runs at ``{subdomain}.eb2b.com.pl``
with the same page structure. One class, parametrised by subdomain, is
enough to cover any eB2B-powered site; instances are registered in
``registry.py``.

Strategy: static HTML scraping with BeautifulSoup. The public listing page
is server-rendered and contains the full list of currently published
postępowania, so no JavaScript is required. No public JSON endpoint is
exposed for unauthenticated users.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


class Eb2bAdapter(BaseAdapter):
    #: Candidate public listing paths in preference order. Different eB2B
    #: tenants expose slightly different public URLs, so try a few.
    LISTING_PATHS = (
        "/open-preview",
        "/open-auctions.html",
        "/public/postepowania",
        "/auctions",
    )

    def __init__(self, subdomain: str, display_name: Optional[str] = None) -> None:
        self.subdomain = subdomain
        self.source_id = f"eb2b_{subdomain}"
        self.source_name = display_name or f"eB2B ({subdomain})"
        self.base_url = f"https://{subdomain}.eb2b.com.pl"
        super().__init__()

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing_html(session)
        if html is None:
            self.log.warning("%s: no accessible public listing page", self.source_id)
            return []

        soup = BeautifulSoup(html, "lxml")
        return self._parse_listing(soup)

    # ---- internals ---------------------------------------------------------

    def _fetch_listing_html(self, session) -> Optional[str]:
        for path in self.LISTING_PATHS:
            url = urljoin(self.base_url, path)
            try:
                resp = self.http_get(session, url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    self.log.debug("%s: using %s", self.source_id, url)
                    return resp.text
            except Exception as exc:
                self.log.debug("%s: %s unreachable: %s", self.source_id, url, exc)
                continue
        return None

    def _parse_listing(self, soup: BeautifulSoup) -> List[RawTender]:
        """Parse items from listing HTML.

        The page exposes either a table of auctions or a list of cards; both
        use anchor tags whose href contains an auction/postepowanie id. We
        hunt for anchors that point to a detail page and treat their text
        as the title.
        """
        out: List[RawTender] = []
        seen_ids: set[str] = set()

        candidates = soup.find_all("a", href=True)
        for a in candidates:
            href = a["href"]
            ext_id = _extract_id_from_href(href)
            if not ext_id or ext_id in seen_ids:
                continue
            title = " ".join(a.get_text(strip=True).split())
            if not title or len(title) < 5:
                continue
            seen_ids.add(ext_id)

            # Best-effort: pull organization from the nearest row/container.
            organization = _nearest_org_hint(a) or self.source_name

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title,
                    description=title,
                    organization=organization,
                    url=urljoin(self.base_url, href),
                )
            )

        self.log.info("%s: fetched %d items", self.source_id, len(out))
        return out


def _extract_id_from_href(href: str) -> Optional[str]:
    """Pull the numeric id out of common eB2B detail URLs."""
    markers = ("auction/preview/id/", "auctions/", "/preview/id/", "postepowanie/")
    for m in markers:
        if m in href:
            tail = href.split(m, 1)[1]
            # Strip query / fragment / trailing slash
            tail = tail.split("?", 1)[0].split("#", 1)[0].rstrip("/")
            # First path segment
            seg = tail.split("/", 1)[0]
            if seg.isdigit():
                return seg
    return None


def _nearest_org_hint(anchor) -> Optional[str]:
    """Walk up the DOM a few levels looking for a cell that names the buyer."""
    node = anchor
    for _ in range(4):
        parent = getattr(node, "parent", None)
        if parent is None:
            return None
        text = " ".join(parent.get_text(" ", strip=True).split())
        if len(text) > 20 and "Sp." in text or "S.A." in text or "Instytut" in text or "Urząd" in text:
            # Return the shortest line containing the organization-y token.
            for line in text.split("  "):
                if any(tok in line for tok in ("Sp.", "S.A.", "Instytut", "Urząd")):
                    return line.strip()[:200]
        node = parent
    return None
