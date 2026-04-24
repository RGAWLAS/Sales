"""Adapter for Save The Children international tender notices.

Save The Children publishes open tenders at ``savethechildren.net/tenders``.
The page is a paginated list of "opportunity" cards with a title, a
deadline and a link to the full description. Content is in English, so
keyword filtering should be configured with English-language keywords
where relevant.

Strategy: static HTML scraping.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://www.savethechildren.net"
LISTING_PATHS = (
    "/tenders",
    "/what-we-do/tenders",
    "/procurement",
)
_DEADLINE_RE = re.compile(
    r"(?:deadline|closing date|closes?|by)\s*[:\-]?\s*"
    r"(\d{1,2}[\s/\-.]\w+[\s/\-.]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


class SaveTheChildrenAdapter(BaseAdapter):
    source_id = "save_the_children"
    source_name = "Save The Children — Tenders"
    request_delay_seconds = 1.5

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        html = self._fetch_listing(session)
        if not html:
            self.log.warning("save_the_children: listing unreachable")
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
                self.log.debug("save_the_children: %s unreachable: %s", url, exc)
        return None

    def _parse(self, soup: BeautifulSoup) -> List[RawTender]:
        out: List[RawTender] = []
        seen: set[str] = set()

        containers = soup.select(
            "article, div.view-content .views-row, div.tender, div.opportunity, li.tender"
        )
        if not containers:
            containers = soup.find_all("article")

        for c in containers:
            heading = c.find(["h1", "h2", "h3", "h4"])
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
            anchor = (heading.find("a", href=True) if heading else None) or c.find("a", href=True)
            if not title and anchor is not None:
                title = " ".join(anchor.get_text(" ", strip=True).split())
            if not title or len(title) < 8:
                continue
            href = anchor["href"] if anchor else ""
            url = urljoin(BASE, href) if href and not urlparse(href).netloc else (href or "")
            ext_id = url or f"stc::{title[:120]}"
            if ext_id in seen:
                continue
            seen.add(ext_id)

            body_text = c.get_text(" ", strip=True)
            deadline = _extract_deadline(body_text)

            out.append(
                RawTender(
                    external_id=ext_id,
                    title=title[:1000],
                    description=body_text[:2000] if body_text else title,
                    organization=self.source_name,
                    url=url,
                    deadline=deadline,
                )
            )

        self.log.info("save_the_children: fetched %d items", len(out))
        return out


def _extract_deadline(text: str) -> Optional[datetime]:
    if not text:
        return None
    m = _DEADLINE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
