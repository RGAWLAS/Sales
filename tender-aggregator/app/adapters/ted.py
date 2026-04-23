"""Adapter for TED (Tenders Electronic Daily, ted.europa.eu).

Strategy: POST to the public TED Search API ``/api/v3/notices/search``.
This is a first-class REST API maintained by the EU Publications Office,
so no HTML scraping is needed. We narrow the query to Poland + recent
publication dates; further filtering (keyword / CPV) happens downstream
in ``app.filters``.

API docs: https://docs.ted.europa.eu/api/index.html
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.adapters.base import BaseAdapter, RawTender


SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
NOTICE_URL_TEMPLATE = "https://ted.europa.eu/en/notice/-/detail/{publication_number}"


class TedAdapter(BaseAdapter):
    source_id = "ted"
    source_name = "TED (Tenders Electronic Daily)"
    request_delay_seconds = 1.0

    #: How many days back to look. TED publishes ~1000 notices/day, so this
    #: combined with the Poland filter yields a manageable volume.
    LOOKBACK_DAYS = 14
    PAGE_SIZE = 100
    MAX_PAGES = 10

    #: Response fields we ask for. TED's query language uses hyphenated keys.
    FIELDS = [
        "publication-number",
        "notice-title",
        "notice-type",
        "publication-date",
        "buyer-name",
        "buyer-country",
        "deadline-receipt-tender-date-lot",
        "deadline-receipt-expression-interest-date-lot",
        "classification-cpv",
        "description-lot",
        "description-procurement",
        "links",
    ]

    def fetch(self) -> List[RawTender]:
        session = self.build_session()
        session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        since = (datetime.utcnow() - timedelta(days=self.LOOKBACK_DAYS)).strftime("%Y%m%d")
        query = f"publication-date>={since} AND buyer-country=POL"

        results: List[RawTender] = []
        for page in range(1, self.MAX_PAGES + 1):
            payload = {
                "query": query,
                "fields": self.FIELDS,
                "page": page,
                "limit": self.PAGE_SIZE,
                "scope": "ACTIVE",
                "checkQuerySyntax": False,
            }
            try:
                resp = self.http_post(session, SEARCH_URL, json=payload, timeout=45)
            except Exception as exc:
                self.log.warning("TED page %d failed: %s", page, exc)
                break

            try:
                data = resp.json()
            except ValueError:
                self.log.warning("TED: non-JSON response on page %d", page)
                break

            notices = data.get("notices") or data.get("content") or []
            if not notices:
                break

            for item in notices:
                raw = _notice_to_raw(item)
                if raw is not None:
                    results.append(raw)

            total = data.get("totalNoticeCount") or data.get("total") or 0
            if page * self.PAGE_SIZE >= total and total > 0:
                break
            if len(notices) < self.PAGE_SIZE:
                break

        self.log.info("TED: fetched %d notices", len(results))
        return results


def _pick_lang(value: Any, preferred: tuple[str, ...] = ("pol", "eng", "fra", "deu")) -> str:
    """TED returns many fields as ``{lang_code: text}`` dicts. Pick best lang."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        # Sometimes a list of {lang: ..., value: ...} shapes.
        for entry in value:
            if isinstance(entry, dict):
                for key in preferred:
                    if key in entry and entry[key]:
                        return str(entry[key])
                for v in entry.values():
                    if isinstance(v, str) and v:
                        return v
            elif isinstance(entry, str) and entry:
                return entry
        return ""
    if isinstance(value, dict):
        for key in preferred:
            if key in value and value[key]:
                v = value[key]
                return _pick_lang(v, preferred)
        for v in value.values():
            if isinstance(v, str) and v:
                return v
            if isinstance(v, (list, dict)):
                s = _pick_lang(v, preferred)
                if s:
                    return s
    return ""


def _pick_cpv(item: Dict[str, Any]) -> List[str]:
    cpv = item.get("classification-cpv") or item.get("cpvCode") or item.get("cpv")
    if cpv is None:
        return []
    if isinstance(cpv, str):
        return [cpv]
    if isinstance(cpv, list):
        out: List[str] = []
        for c in cpv:
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, dict):
                v = c.get("code") or c.get("value")
                if v:
                    out.append(str(v))
        return out
    return []


def _notice_to_raw(item: Dict[str, Any]) -> Optional[RawTender]:
    pub = item.get("publication-number") or item.get("ND") or item.get("id")
    if not pub:
        return None

    title = _pick_lang(item.get("notice-title") or item.get("TI") or item.get("title"))
    description = _pick_lang(
        item.get("description-lot")
        or item.get("description-procurement")
        or item.get("description")
    )
    buyer = _pick_lang(item.get("buyer-name") or item.get("AA"))

    link = ""
    links = item.get("links")
    if isinstance(links, dict):
        link = _pick_lang(links.get("html")) or _pick_lang(links)
    if not link:
        link = NOTICE_URL_TEMPLATE.format(publication_number=pub)

    return RawTender(
        external_id=str(pub),
        title=title or f"TED notice {pub}",
        description=description,
        organization=buyer,
        url=link,
        cpv_codes=_pick_cpv(item),
        published_at=_parse_ted_date(item.get("publication-date") or item.get("PD")),
        deadline=_parse_ted_date(
            item.get("deadline-receipt-tender-date-lot")
            or item.get("deadline-receipt-expression-interest-date-lot")
        ),
    )


def _parse_ted_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        # Possible {"value": "..."} shape.
        value = value.get("value") or next(iter(value.values()), None)
    if not isinstance(value, str) or not value:
        return None
    s = value
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:len(fmt) + 0 if fmt != "%Y-%m-%dT%H:%M:%S" else 19], fmt)
        except ValueError:
            continue
    return None
