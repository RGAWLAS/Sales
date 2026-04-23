"""Adapter registry.

Adding a new source is a two-step, one-file change:

    1. Import the adapter class here.
    2. Append an instance to ``ADAPTERS``.

No other part of the codebase needs modification.
"""
from __future__ import annotations

from typing import Dict, List

from app.adapters.base import BaseAdapter
from app.adapters.ezamowienia import EzamowieniaAdapter
from app.adapters.eb2b import Eb2bAdapter


ADAPTERS: List[BaseAdapter] = [
    EzamowieniaAdapter(),
    Eb2bAdapter(subdomain="nask", display_name="eB2B NASK"),
    Eb2bAdapter(subdomain="kowr", display_name="eB2B KOWR"),
]


def get_adapter(source_id: str) -> BaseAdapter | None:
    """Return the adapter with the given ``source_id`` or None."""
    for a in ADAPTERS:
        if a.source_id == source_id:
            return a
    return None


def all_adapters_by_id() -> Dict[str, BaseAdapter]:
    return {a.source_id: a for a in ADAPTERS}
