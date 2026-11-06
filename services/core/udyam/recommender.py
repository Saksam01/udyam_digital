"""Picks a segment bundle, scales access to the number of sites, and adds the needs the customer chose."""

from __future__ import annotations
from udyam.quote_engine import build_quote, _gate_fail, PRIMARY_ACCESS

CATEGORY_KEYS = {
    "connectivity": "Connectivity",
    "communication": "Communication",
    "cloud": "Cloud & Productivity",
    "security": "Security",
    "iot": "IoT & Physical",
}


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
    """Base bundles. One primary internet link per site, business lines, and a segment staple."""
    seg, emp, sites = prof["segment"], prof["employees"], prof["num_sites"]
    seats = max(1, round(0.7 * emp))
    gst = prof["gstin_status"] == "active"
    if seg == "micro":
        return [("Dukaan Smart Store", {"P01": sites, "P07": 2, "P19": 1}),
                ("Dukaan Connect",     {"P01": sites, "P07": 2})]
    if seg == "prof":
        c = []
        if gst and prof["city_tier"] == 1 and emp >= 5:
            c.append(("Practice Pro", {"P03": sites, "P16": emp, "P08": 3, "P20": min(emp, 8)}))
        c.append(("Practice Essentials", {"P02": sites, "P16": seats, "P07": 2}))
        return c
    if seg == "multi":
        lines = max(1, round(sites / 2))
        # Multi-site: one link per site plus automatic backup so no branch goes offline.
        return [("Chain Store Essentials", {"P01": sites, "P09": sites, "P08": lines, "P19": sites}),
                ("Chain Starter",          {"P01": sites, "P08": lines, "P07": 2})]
    if seg == "mfg":
        c = []
        if gst and emp >= 10:
            c.append(("Factory Leased Line", {"P05": sites, "P08": 4, "P16": seats, "P21": sites}))
        if gst and prof["city_tier"] == 1 and emp >= 5:
            c.append(("Factory Fibre", {"P03": sites, "P08": 4, "P16": seats, "P20": min(emp, 8)}))
        c.append(("Factory Starter", {"P01": sites, "P08": 2, "P16": seats}))
        return c
    return [("Starter Connect", {"P01": sites, "P07": 2})]


def _has_category(cat, raw, items, catname) -> bool:
    return any(raw.get(pid, {}).get("category") == catname for pid in items)


def _add_categories(cat, raw, prof, items, categories):
    """For each category the customer asked for, add the cheapest product that fits, if we don't already have one."""
    seg = prof["segment"]
    added, skipped = [], []
    for c in categories or []:
        catname = CATEGORY_KEYS.get(c)
        if not catname or _has_category(cat, raw, items, catname):
            continue
        best = None
        for pid, p in cat.items():
            if raw.get(pid, {}).get("category") != catname or pid in items:
                continue
            if seg not in p.targets or _gate_fail(cat[pid], prof):
                continue
            if pid in PRIMARY_ACCESS and any(x in items for x in PRIMARY_ACCESS):
                continue  # one primary access only
            if p.requires_one_of and not any(x in items for x in p.requires_one_of):
                continue
            price = p.pmin + p.pmax
            if best is None or price < best[0]:
                best = (price, pid)
        if best:
            items[best[1]] = 1
            added.append(c)
        else:
            skipped.append(c)
    return added, skipped


def pick(cat, raw, profile_raw: dict, city_tiers: dict | None = None, categories: list[str] | None = None):
    prof = to_engine_profile(profile_raw, city_tiers)
    chosen = None
    for name, items in _candidates(prof):
        q = build_quote(cat, prof, items)
        if chosen is None:
            chosen = (name, dict(items))
        if q["status"] != "blocked":
            chosen = (name, dict(items))
            break
    if chosen is None:
        chosen = ("Starter Connect", {"P01": max(1, prof["num_sites"]), "P07": 2})
    name, items = chosen
    added, skipped = _add_categories(cat, raw, prof, items, categories or [])
    quote = build_quote(cat, prof, items)
    return name, items, prof, quote, {"included_needs": added, "skipped_needs": skipped}


def _eligibility(prof: dict, p) -> list[str]:
    reasons = []
    if prof["city_tier"] not in p.tiers:
        reasons.append(f"available only in tier {sorted(p.tiers)} cities")
    if prof["employees"] < p.min_emp:
        reasons.append(f"needs at least {p.min_emp} employees")
    if prof["num_sites"] < p.min_sites:
        reasons.append(f"needs at least {p.min_sites} sites")
    if p.gstin and prof["gstin_status"] not in ("active", "unverified"):
        reasons.append("needs an active GSTIN")
    return reasons


def suitable_products(cat, raw, profile_raw, city_tiers=None, categories=None, needs=None):
    """Products that fit the profile, with full detail, so the UI can list and expand them."""
    prof = to_engine_profile(profile_raw, city_tiers)
    seg = prof["segment"]
    wanted = {CATEGORY_KEYS.get(c, c) for c in (categories or [])}
    rec_name, rec_items, _, _, _ = pick(cat, raw, profile_raw, city_tiers, categories)
    has_primary = any(x in rec_items for x in PRIMARY_ACCESS)
    products = []
    for pid in sorted(cat):
        p = cat[pid]
        row = raw.get(pid, {})
        category = row.get("category", "")
        if wanted and category not in wanted:
            continue
        if seg not in p.targets:
            continue
        # Don't offer a second primary internet link as an add-on; it competes with the one in the bundle.
        if pid in PRIMARY_ACCESS and pid not in rec_items and has_primary:
            continue
        reasons = _eligibility(prof, p)
        mid = (p.pmin + p.pmax) / 2
        products.append({
            "product_id": pid,
            "name": p.name,
            "category": category,
            "description": row.get("description", ""),
            "unit": p.unit,
            "price_inr": int(mid) if mid == int(mid) else round(mid, 2),
            "price_range_inr": [p.pmin, p.pmax],
            "setup_inr": p.setup,
            "min_contract_months": p.min_contract,
            "install_days": p.install_days,
            "requires_gstin": p.gstin,
            "eligible": not reasons,
            "eligibility_note": reasons[0] if reasons else None,
            "in_recommended_bundle": pid in rec_items,
        })
    products.sort(key=lambda x: (not x["in_recommended_bundle"], x["category"], x["price_inr"]))
    return {"recommended_bundle": rec_name, "products": products}
