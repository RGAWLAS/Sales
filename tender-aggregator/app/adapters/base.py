"""Adapter base classes and data contracts.

Adding a new source = write a subclass of ``BaseAdapter`` that implements
``fetch()`` and register it in ``app.adapters.registry``. No other files
need to be touched.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


logger = logging.getLogger(__name__)


@dataclass
class RawTender:
    """Data carrier for a single tender as produced by an adapter.

    Adapters should populate as many fields as are cheaply available; the
    filtering / persistence layer does not require any field beyond the
    identifiers and title.

    ``category`` defaults to "TENDER". Adapters scraping editorial /
    news sources should set it to "EARLY_SIGNAL" so the UI and digest can
    treat those rows as radar blips rather than formal procurements.
    """

    external_id: str
    title: str
    description: str = ""
    organization: str = ""
    url: str = ""
    cpv_codes: List[str] = field(default_factory=list)
    published_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    category: str = "TENDER"


class BaseAdapter(ABC):
    """Abstract adapter. Subclasses fetch *all* current listings from a source.

    Filtering and deduplication are handled by the caller; adapters should
    return the raw data as faithfully as possible.
    """

    source_id: str = ""       # Unique, stable identifier, e.g. "ezamowienia"
    source_name: str = ""     # Human-readable, e.g. "Platforma e-Zamówienia"
    enabled: bool = True
    request_delay_seconds: float = 1.0
    user_agent: str = (
        "Mozilla/5.0 (compatible; TenderAggregatorBot/1.0; "
        "+https://example.com/tender-aggregator)"
    )

    def __init__(self) -> None:
        self.log = logging.getLogger(f"adapter.{self.source_id or self.__class__.__name__}")

    @abstractmethod
    def fetch(self) -> List[RawTender]:
        """Return all currently advertised tenders from the source."""
        raise NotImplementedError

    # ---- shared helpers ----------------------------------------------------

    def build_session(self) -> requests.Session:
        """Create a requests.Session preconfigured with a User-Agent header."""
        s = requests.Session()
        s.headers.update({"User-Agent": self.user_agent, "Accept-Language": "pl,en;q=0.7"})
        return s

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException,)),
        reraise=True,
    )
    def http_get(
        self,
        session: requests.Session,
        url: str,
        *,
        params: Optional[dict] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """HTTP GET with retry + polite delay."""
        self.log.debug("GET %s params=%s", url, params)
        resp = session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        time.sleep(self.request_delay_seconds)
        return resp

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException,)),
        reraise=True,
    )
    def http_post(
        self,
        session: requests.Session,
        url: str,
        *,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        timeout: int = 30,
    ) -> requests.Response:
        self.log.debug("POST %s", url)
        resp = session.post(url, json=json, data=data, timeout=timeout)
        resp.raise_for_status()
        time.sleep(self.request_delay_seconds)
        return resp


def iter_adapters(adapters: Iterable[BaseAdapter]) -> Iterable[BaseAdapter]:
    """Yield enabled adapters only."""
    for a in adapters:
        if a.enabled:
            yield a
