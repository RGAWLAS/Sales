"""Adapter registry.

Adding a new source is a two-step, one-file change:

    1. Import the adapter class here.
    2. Append an instance to ``ADAPTERS``.

No other part of the codebase needs modification.
"""
from __future__ import annotations

from typing import Dict, List

from app.adapters.base import BaseAdapter
from app.adapters.baltona import BaltonaAdapter
from app.adapters.baza_konkurencyjnosci import BazaKonkurencyjnosciAdapter
from app.adapters.bip_ulc import BipUlcAdapter
from app.adapters.eb2b import Eb2bAdapter
from app.adapters.ezamowienia import EzamowieniaAdapter
from app.adapters.grupa_azoty import GrupaAzotyAdapter
from app.adapters.logintrade import LogintradeAdapter
from app.adapters.marketplanet import MarketplanetAdapter
from app.adapters.mmp_online import MmpOnlineAdapter
from app.adapters.pck import PckAdapter
from app.adapters.pgnig import PgnigAdapter
from app.adapters.platformazakupowa import PlatformaZakupowaAdapter
from app.adapters.polpharma import PolpharmaAdapter
from app.adapters.pzu import PzuAdapter
from app.adapters.save_the_children import SaveTheChildrenAdapter
from app.adapters.synthos import SynthosAdapter
from app.adapters.tauron_swoz import TauronSwozAdapter
from app.adapters.ted import TedAdapter
from app.adapters.veolia import VeoliaAdapter


ADAPTERS: List[BaseAdapter] = [
    # API-first, cross-country / cross-tenant sources.
    EzamowieniaAdapter(),
    TedAdapter(),
    BazaKonkurencyjnosciAdapter(),
    PlatformaZakupowaAdapter(),

    # eB2B white-label tenants.
    Eb2bAdapter(subdomain="nask", display_name="eB2B NASK"),
    Eb2bAdapter(subdomain="kowr", display_name="eB2B KOWR"),

    # Logintrade white-label tenants.
    LogintradeAdapter(subdomain="lpp", display_name="Logintrade LPP"),
    LogintradeAdapter(subdomain="grupazywiec", display_name="Logintrade Grupa Żywiec"),
    LogintradeAdapter(subdomain="anwim", display_name="Logintrade Anwim"),

    # Marketplanet / OnePlace buyer portals.
    MarketplanetAdapter(
        base_url="oneplace.marketplanet.pl",
        source_slug="oneplace",
        display_name="Marketplanet OnePlace",
    ),
    MarketplanetAdapter(
        base_url="zakupy2.mbank.pl",
        source_slug="mbank",
        display_name="mBank Zakupy (Marketplanet)",
    ),

    # Grupa Azoty — two public portals.
    GrupaAzotyAdapter(
        base_url="przetargi.grupaazoty.com",
        source_slug="przetargi",
        display_name="Grupa Azoty — Przetargi",
    ),
    GrupaAzotyAdapter(
        base_url="platformazakupowa.grupaazoty.com",
        source_slug="platforma",
        display_name="Grupa Azoty — Platforma Zakupowa",
    ),

    # Custom per-company procurement portals.
    TauronSwozAdapter(),
    PgnigAdapter(),
    VeoliaAdapter(),
    PzuAdapter(),

    # NGO / corporate news-style announcement pages.
    PckAdapter(),
    SynthosAdapter(),
    BipUlcAdapter(),
    PolpharmaAdapter(),
    BaltonaAdapter(),
    MmpOnlineAdapter(),
    SaveTheChildrenAdapter(),
]


def get_adapter(source_id: str) -> BaseAdapter | None:
    """Return the adapter with the given ``source_id`` or None."""
    for a in ADAPTERS:
        if a.source_id == source_id:
            return a
    return None


def all_adapters_by_id() -> Dict[str, BaseAdapter]:
    return {a.source_id: a for a in ADAPTERS}
