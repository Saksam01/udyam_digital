"""Picks the first candidate bundle that passes every rule gate."""

from __future__ import annotations
from udyam.quote_engine import build_quote


def to_engine_profile(p: dict, city_tiers: dict | None = None) -> dict:
    city = (p.get("city") or "").strip().title()
    tier = p.get("city_tier")
    if tier in (1, 2, "1", "2"):
        tier = int(tier)
    elif city_tiers and city in city_tiers:
        tier = city_tiers[city]
    else:
        tier = 2  # unknown city -> tier 2
    return {
        "segment": p.get("segment", "micro"),
        "city_tier": tier,
        "employees": max(1, min(int(p.get("employees") or 1), 500)),
        "num_sites": max(1, min(int(p.get("num_sites") or 1), 50)),
        "gstin_status": (p.get("gstin_status") or "none").lower(),
    }


def _candidates(prof: dict) -> list[tuple[str, dict]]:
    seg, emp, sites = prof["segment"], prof["employees"], prof["num_sites"]
    seats = max(1, round(0.7 * emp))
    gst = prof["gstin_status"] == "active"
    if seg == "micro":
        return [("Dukaan Smart Store", {"P01": 1, "P07": 2, "P19": 1}),
                ("Dukaan Connect",     {"P01": 1, "P07": 2})]
    if seg == "prof":
        c = []
        if gst and prof["city_tier"] == 1 and emp >= 5:
            c.append(("Practice Pro", {"P03": 1, "P16": emp, "P08": 3, "P20": min(emp, 8)}))
        c.append(("Practice Essentials", {"P02": 1, "P16": seats, "P07": 2}))
        return c
    if seg == "multi":
        lines = max(1, round(sites / 2))
        return [("Chain Store Essentials", {"P01": sites, "P09": sites, "P08": lines, "P19": sites}),
                ("Chain Starter",          {"P01": sites, "P08": lines, "P07": 2})]
    if seg == "mfg":
        c = []
        if gst and emp >= 10:
            c.append(("Factory Leased Line + IoT", {"P05": 1, "P08": 4, "P16": seats, "P21": 1}))
        if gst and prof["city_tier"] == 1 and emp >= 5:
            c.append(("Factory Fibre", {"P03": 1, "P08": 4, "P16": seats, "P20": min(emp, 8)}))
        c.append(("Factory Starter", {"P01": 1, "P08": 2, "P16": seats}))
        return c
    return [("Starter Connect", {"P01": 1, "P07": 2})]


def pick(cat, profile_raw: dict, city_tiers: dict | None = None):
    prof = to_engine_profile(profile_raw, city_tiers)
    fallback = None
    for name, items in _candidates(prof):
        q = build_quote(cat, prof, items)
        fallback = fallback or (name, items, q)
        if q["status"] != "blocked":
            return name, items, prof, q
    base = {"P01": 1, "P07": 2}  # last resort
    return "Starter Connect", base, prof, build_quote(cat, prof, base)
