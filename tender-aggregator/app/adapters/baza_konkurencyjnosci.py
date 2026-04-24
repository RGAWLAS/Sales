"""Adapter for Baza Konkurencyjności (bazakonkurencyjnosci.funduszeeuropejskie.gov.pl).

Strategy: REST JSON endpoint ``/api/publicrequest``. The public listing
page on the portal is a SPA that calls this endpoint directly — easy to
rediscover in DevTools. Going straight to the API avoids having to spin
up Playwright for client-side rendered content.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.adapters.base import BaseAdapter, RawTender


BASE = "https://bazakonkurencyjnosci.funduszeeuropejskie.gov.pl"
SEARCH_URL = f"{BASE}/api/publicrequest"
DETAIL_URL_TEMPLATE = f"{BASE}/ogloszenia/{{id}}"


class BazaKonkurencyjnosciAdapter(BaseAdapter):
    source_id = "baza_konkurencyjnosci"
    source_name = "Baza Konkurencyjności"
    request_delay_seconds = 1.0

    PAGE_SIZE = 50
    MAX_PAGES = 10

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        session.headers.update({"Accept": "application/json"})

        results: List[RawTender] = []
        for page in range(self.MAX_PAGES):
            params = {
                "max": self.PAGE_SIZE,
                "offset": page * self.PAGE_SIZE,
                "orderBy": "publicationDate",
                "orderDirection": "DESC",
                # "status" etc. could narrow results server-side; we leave it
                # open and let the downstream filter do the work so we pick
                # up all flavours of publication status.
            }
            try:
                resp = self.http_get(session, SEARCH_URL, params=params, timeout=30)
            except Exception as exc:
                self.log.warning("BK page %d failed: %s", page, exc)
                break

            try:
                data = resp.json()
            except ValueError:
                self.log.warning("BK: non-JSON response on page %d", page)
                break

            items = _extract_items(data)
            if not items:
                break

            for item in items:
                raw = _item_to_raw(item)
                if raw is not None:
                    results.append(raw)

            if len(items) < self.PAGE_SIZE:
                break

        self.log.info("Baza Konkurencyjności: fetched %d items", len(results))
        return results


def _extract_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "content", "data", "results", "announcements"):
            v = payload.get(key)
            if isinstance(v, list):
                return v
    return []


def _item_to_raw(item: Dict[str, Any]) -> Optional[RawTender]:
    ext_id = item.get("id") or item.get("announcementId") or item.get("uuid")
    if not ext_id:
        return None

    title = item.get("title") or item.get("subject") or item.get("name") or ""
    description = (
        item.get("description")
        or item.get("subjectDescription")
        or item.get("shortDescription")
        or ""
    )
    organization = (
        item.get("advertiserName")
        or item.get("ordererName")
        or item.get("announcerName")
        or ""
    )
    cpv = item.get("cpvCodes") or item.get("cpv") or []
    cpv_list: List[str]
    if isinstance(cpv, list):
        cpv_list = []
        for c in cpv:
            if isinstance(c, str):
                cpv_list.append(c)
            elif isinstance(c, dict):
                v = c.get("code") or c.get("value") or c.get("cpv")
                if v:
                    cpv_list.append(str(v))
    elif isinstance(cpv, str):
        cpv_list = [cpv]
    else:
        cpv_list = []

    return RawTender(
        external_id=str(ext_id),
        title=str(title),
        description=str(description),
        organization=str(organization),
        url=DETAIL_URL_TEMPLATE.format(id=ext_id),
        cpv_codes=cpv_list,
        published_at=_parse_dt(item.get("publicationDate") or item.get("publishDate")),
        deadline=_parse_dt(
            item.get("deadline") or item.get("submissionDeadline") or item.get("endDate")
        ),
    )


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None
