"""Tender filtering: CPV prefix + keyword matching.

A tender passes when:
  - any of its CPV codes *starts with* any configured CPV prefix, OR
  - any keyword appears in (title + description), case-insensitive and
    accent-insensitive,
AND none of the ``exclude_keywords`` match.

The list of keywords that matched is returned so callers can persist them.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

import yaml


logger = logging.getLogger(__name__)


@dataclass
class FilterConfig:
    cpv_codes: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)

    @property
    def normalized_keywords(self) -> List[str]:
        return [_normalize(k) for k in self.keywords]

    @property
    def normalized_exclude(self) -> List[str]:
        return [_normalize(k) for k in self.exclude_keywords]


@dataclass
class FilterDecision:
    passed: bool
    keywords_matched: List[str] = field(default_factory=list)
    cpv_hits: List[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    """Lowercase and strip diacritics for fuzzy matching."""
    if not text:
        return ""
    nfd = unicodedata.normalize("NFD", text)
    without_diacritics = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return without_diacritics.lower()


def load_filter_config(path: str | Path) -> FilterConfig:
    """Load filters from a YAML file."""
    p = Path(path)
    if not p.exists():
        logger.warning("Filters config not found at %s; using empty config", p)
        return FilterConfig()
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return FilterConfig(
        cpv_codes=[str(c) for c in data.get("cpv_codes", []) or []],
        keywords=[str(k) for k in data.get("keywords", []) or []],
        exclude_keywords=[str(k) for k in data.get("exclude_keywords", []) or []],
    )


def _cpv_hits(cpvs: Iterable[str], prefixes: Iterable[str]) -> List[str]:
    cpvs_list = [c for c in cpvs if c]
    prefixes_list = list(prefixes)
    hits: List[str] = []
    for cpv in cpvs_list:
        for pref in prefixes_list:
            if cpv.startswith(pref):
                hits.append(cpv)
                break
    return hits


def _keyword_hits(text_normalized: str, keywords_normalized: List[str], originals: List[str]) -> List[str]:
    matched: List[str] = []
    for norm, orig in zip(keywords_normalized, originals):
        if norm and norm in text_normalized:
            matched.append(orig)
    return matched


def evaluate(
    title: str,
    description: str,
    cpv_codes: Optional[Iterable[str]],
    config: FilterConfig,
) -> FilterDecision:
    """Apply filter rules to a tender candidate."""
    haystack = _normalize(f"{title or ''} {description or ''}")

    excludes = _keyword_hits(haystack, config.normalized_exclude, config.exclude_keywords)
    if excludes:
        return FilterDecision(passed=False, keywords_matched=[], cpv_hits=[])

    cpv_hits = _cpv_hits(cpv_codes or [], config.cpv_codes)
    kw_hits = _keyword_hits(haystack, config.normalized_keywords, config.keywords)

    passed = bool(cpv_hits) or bool(kw_hits)
    return FilterDecision(passed=passed, keywords_matched=kw_hits, cpv_hits=cpv_hits)
