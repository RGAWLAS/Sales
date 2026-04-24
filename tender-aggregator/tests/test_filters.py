"""Filter logic: CPV prefix match + keyword match + diacritics-insensitive."""
from __future__ import annotations

from app.filters import FilterConfig, evaluate


def make_config() -> FilterConfig:
    return FilterConfig(
        cpv_codes=["79340000", "72413000"],
        keywords=["reklam", "marketing", "public relations"],
        exclude_keywords=["nieruchomość"],
    )


def test_cpv_prefix_matches_sub_code():
    cfg = make_config()
    d = evaluate(
        title="Budowa drogi",
        description="ogólny opis",
        cpv_codes=["79340000-1"],
        config=cfg,
    )
    assert d.passed is True
    assert "79340000-1" in d.cpv_hits
    assert d.keywords_matched == []


def test_keyword_match_case_and_diacritics():
    cfg = make_config()
    d = evaluate(
        title="Usługi REKLAmy w internecie",
        description="",
        cpv_codes=[],
        config=cfg,
    )
    assert d.passed
    assert "reklam" in d.keywords_matched


def test_keyword_in_description_only():
    cfg = make_config()
    d = evaluate(
        title="Zapytanie",
        description="Szukamy dostawcy usług public relations na kwartał",
        cpv_codes=[],
        config=cfg,
    )
    assert d.passed
    assert "public relations" in d.keywords_matched


def test_reject_when_exclude_keyword_present():
    cfg = make_config()
    d = evaluate(
        title="Marketing dla nieruchomości komercyjnych",
        description="",
        cpv_codes=["79340000-1"],
        config=cfg,
    )
    assert d.passed is False


def test_no_match_when_neither_cpv_nor_keyword():
    cfg = make_config()
    d = evaluate(
        title="Odśnieżanie chodników",
        description="Sezon zimowy",
        cpv_codes=["90620000"],
        config=cfg,
    )
    assert d.passed is False
    assert d.keywords_matched == []
    assert d.cpv_hits == []


def test_multiple_keywords_all_returned():
    cfg = make_config()
    d = evaluate(
        title="Marketing i reklama w mediach",
        description="",
        cpv_codes=[],
        config=cfg,
    )
    assert d.passed
    assert set(d.keywords_matched) >= {"marketing", "reklam"}
