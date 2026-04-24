"""Adapter for Platforma e-Zamówienia (ezamowienia.gov.pl).

Strategy: POST to the public "Board/Search" JSON endpoint used by the
front-end of the platform. This is a direct JSON API (no HTML scraping),
discovered via the browser DevTools Network tab when paging through the
public listing on ezamowienia.gov.pl. Using the JSON endpoint is much more
stable than parsing the rendered HTML.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.adapters.base import BaseAdapter, RawTender


SEARCH_URL = "https://ezamowienia.gov.pl/mo-board/api/v1/Board/Search"
DETAIL_URL_TEMPLATE = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/{id}"


class EzamowieniaAdapter(BaseAdapter):
    source_id = "ezamowienia"
    source_name = "Platforma e-Zamówienia"
    request_delay_seconds = 1.0

    #: Number of pages pulled per run. Each page is PAGE_SIZE notices.
    MAX_PAGES = 5
    PAGE_SIZE = 100

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        results: List[RawTender] = []
        for page in range(1, self.MAX_PAGES + 1):
            payload = {
                "SortingColumnName": "PublicationDate",
                "SortingDirection": "DESC",
                "Page": page,
                "PageSize": self.PAGE_SIZE,
            }
            try:
                resp = self.http_post(session, SEARCH_URL, json=payload, timeout=30)
            except Exception as exc:
                self.log.warning("ezamowienia page %d failed: %s", page, exc)
                break

            try:
                data = resp.json()
            except ValueError:
                self.log.warning("ezamowienia: non-JSON response on page %d", page)
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

        self.log.info("ezamowienia: fetched %d items", len(results))
        return results


def _extract_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find the items array in the response, being tolerant of naming variations."""
    for key in ("Data", "data", "Items", "items", "Result", "result"):
        v = payload.get(key)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            for k2 in ("Data", "data", "Items", "items"):
                inner = v.get(k2)
                if isinstance(inner, list):
                    return inner
    return []


def _item_to_raw(item: Dict[str, Any]) -> Optional[RawTender]:
    ext_id = (
        item.get("ObjectId")
        or item.get("Id")
        or item.get("NoticeId")
        or item.get("CaseNumber")
        or item.get("OrderNumber")
    )
    if not ext_id:
        return None

    title = (
        item.get("OrderObject")
        or item.get("Subject")
        or item.get("Name")
        or ""
    )
    organization = item.get("OrganizationName") or item.get("OfficeName") or ""
    cpv = item.get("CpvCodes") or item.get("CPVCodes") or item.get("CpvCode")
    cpv_list: List[str]
    if isinstance(cpv, list):
        cpv_list = [str(c) for c in cpv if c]
    elif isinstance(cpv, str) and cpv:
        cpv_list = [cpv]
    else:
        cpv_list = []

    return RawTender(
        external_id=str(ext_id),
        title=str(title),
        description=str(item.get("Description") or item.get("OrderObject") or ""),
        organization=str(organization),
        url=DETAIL_URL_TEMPLATE.format(id=ext_id),
        cpv_codes=cpv_list,
        published_at=_parse_dt(item.get("PublicationDate") or item.get("PublicationDateTime")),
        deadline=_parse_dt(item.get("SubmittingOffersDate") or item.get("SubmissionDeadline")),
    )


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    # Handle ISO with "Z" suffix
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
