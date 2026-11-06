"""Picks the first candidate bundle that passes every rule gate, then adds the needs the customer asked for."""

from __future__ import annotations
from udyam.quote_engine import build_quote, _gate_fail

# A need the advisor asks about maps to one catalogue product.
NEED_PRODUCT = {"pos": "P19", "cctv": "P23", "email": "P16", "whatsapp": "P15", "wifi": "P22", "failover": "P09"}


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


def _apply_needs(cat, prof: dict, items: dict, need_keys: list[str]):
    """Add each asked-for need to the bundle if the profile is eligible; report what was skipped."""
    included, skipped = [], []
    for k in need_keys:
        pid = NEED_PRODUCT.get(k)
        if not pid or pid not in cat:
            continue
        if _gate_fail(cat[pid], prof):
            skipped.append(k)
        else:
            items.setdefault(pid, 1)
            included.append(k)
    return included, skipped


def pick(cat, profile_raw: dict, city_tiers: dict | None = None, needs: list[str] | None = None):
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
        chosen = ("Starter Connect", {"P01": 1, "P07": 2})
    name, items = chosen
    included, skipped = _apply_needs(cat, prof, items, needs or [])
    quote = build_quote(cat, prof, items)
    return name, items, prof, quote, {"included_needs": included, "skipped_needs": skipped}


CATEGORY_KEYS = {
    "connectivity": "Connectivity",
    "communication": "Communication",
    "cloud": "Cloud & Productivity",
    "security": "Security",
    "iot": "IoT & Physical",
}


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
    rec_name, rec_items, _, _, _ = pick(cat, profile_raw, city_tiers, needs or [])
    products = []
    for pid in sorted(cat):
        p = cat[pid]
        row = raw.get(pid, {})
        category = row.get("category", "")
        if wanted and category not in wanted:
            continue
        if seg not in p.targets:
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
