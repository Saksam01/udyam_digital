from __future__ import annotations
import csv, functools, math, os
from decimal import Decimal, ROUND_HALF_UP
from udyam.quote_engine import build_quote, _gate_fail, PRIMARY_ACCESS
from udyam import profiles

GST_RATE = Decimal("0.18")

CATEGORY_KEYS = {
    "connectivity": "Connectivity",
    "communication": "Communication",
    "cloud": "Cloud & Productivity",
    "security": "Security",
    "iot": "IoT & Physical",
}

DIGITAL_MAX_DAYS = 2

NEED_GROUPS = {
    "internet": ("P01", "P02", "P03", "P04", "P05", "P06", "P09", "P11", "P10"),
    "calls": ("P07", "P08", "P12", "P13"),
    "customer_chat": ("P15", "P14"),
    "cloud": ("P16", "P17", "P18"),
    "payments": ("P19",),
    "security": ("P23", "P20", "P21"),
    "wifi": ("P22",),
    "tracking": ("P25", "P24"),
}


def to_engine_profile(p: dict, city_tiers: dict | None = None) -> dict:
    spec = profiles.spec_for(p.get("business_type"), p.get("segment"))
    city = (p.get("city") or "").strip().title()
    tier = p.get("city_tier")
    if tier in (1, 2, "1", "2"):
        tier = int(tier)
    elif city_tiers and city in city_tiers:
        tier = city_tiers[city]
    else:
        tier = 2
    return {
        "segment": spec.segment if (p.get("business_type") or "").lower() in profiles.SPECS else p.get("segment", spec.segment),
        "city_tier": tier,
        "employees": max(1, min(int(p.get("employees") or 1), 500)),
        "num_sites": max(1, min(int(p.get("num_sites") or 1), 50)),
        "gstin_status": (p.get("gstin_status") or "none").lower(),
    }


@functools.lru_cache(maxsize=1)
def _history() -> tuple:
    from udyam.data_loader import DATA_DIR
    rows = []
    path = os.path.join(DATA_DIR, "smb_leads.csv")
    if not os.path.exists(path):
        return tuple()
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("outcome") == "Activated" and r.get("bundle_products"):
                pids = {x.split("x")[0] for x in r["bundle_products"].split(";") if x}
                rows.append((r.get("business_type", ""), r.get("segment", ""), frozenset(pids)))
    return tuple(rows)


def popularity(spec: profiles.Spec, segment_name: str | None = None) -> tuple[dict, int]:
    """Share of similar customers that bought each product."""
    hist = _history()
    mine = [h for h in hist if h[0] in spec.data_types]
    if len(mine) < 8:
        seg_names = {"micro": "Micro retail & services", "prof": "Professional offices",
                     "multi": "Small multi-site businesses", "mfg": "Small manufacturers"}
        mine = [h for h in hist if h[1] == seg_names.get(spec.segment)]
    n = len(mine)
    out: dict[str, float] = {}
    for _, _, pids in mine:
        for p in pids:
            out[p] = out.get(p, 0) + 1
    return ({p: c / n for p, c in out.items()} if n else {}), n


def _qty(rule: str, prof: dict, spec: profiles.Spec, seats: int) -> int:
    emp, sites = prof["employees"], prof["num_sites"]
    if rule.isdigit():
        return int(rule)
    if rule == "sites":
        return sites
    if rule == "seats":
        return seats
    if rule == "counters":
        return sites * (2 if emp / sites >= 12 else 1)
    if rule == "devs":
        return max(1, min(emp, 15))
    if rule == "devs4":
        return max(2, min(emp // 4, 10))
    if rule == "cams":
        return min(2 * sites, 12)
    if rule == "cams4":
        return min(4 * sites, 16)
    if rule == "vehicles":
        return max(1, min(emp // 12, 6))
    return 1


def _default_qty(cat, pid: str, prof: dict, spec: profiles.Spec, seats: int) -> int:
    by_pid = {"P23": "cams", "P20": "devs", "P24": "devs4", "P25": "vehicles", "P19": "counters", "P12": None}
    if pid == "P12":
        return max(2, min(prof["employees"] // 5, 10))
    if pid in by_pid:
        return _qty(by_pid[pid], prof, spec, seats)
    unit = cat[pid].unit
    if unit == "per site":
        return prof["num_sites"]
    if unit == "per user":
        return max(1, seats or round(0.7 * prof["employees"]))
    return 1


def _lines_qty(spec: profiles.Spec, prof: dict) -> tuple[str, int]:
    plan, ratio, mn, mx = spec.lines
    n = max(mn, round(ratio * prof["employees"]))
    if spec.lines_per_site:
        n = max(n, math.ceil(spec.lines_per_site * prof["num_sites"]))
    return plan, max(1, min(n, mx))


def _usable(cat, pid: str, prof: dict, items: dict) -> bool:
    p = cat.get(pid)
    if p is None or _gate_fail(p, prof):
        return False
    if p.requires_one_of and not any(x in items for x in p.requires_one_of):
        return False
    return True


def _sized(spec: profiles.Spec, prof: dict) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    emp = prof["employees"]
    seat_roles = profiles.role_seats(emp, spec.roles)
    seats = sum(n for _, n in seat_roles)
    return seat_roles, seats


def _base_items(cat, spec: profiles.Spec, prof: dict) -> tuple[dict, list[tuple[str, int]]]:
    seat_roles, seats = _sized(spec, prof)
    sites = prof["num_sites"]
    items: dict[str, int] = {}
    for pid in spec.access:
        if _usable(cat, pid, prof, items):
            items[pid] = sites
            break
    if not items:
        items["P01"] = sites
    plan, n = _lines_qty(spec, prof)
    if _usable(cat, plan, prof, items):
        items[plan] = n
    for entry in spec.core:
        pid, rule = entry[0], entry[1]
        fallback = entry[2] if len(entry) > 2 else None
        if _usable(cat, pid, prof, items):
            items[pid] = _qty(rule, prof, spec, seats)
        elif fallback and _usable(cat, fallback[0], prof, items):
            items[fallback[0]] = _qty(fallback[1], prof, spec, seats)
    return items, seat_roles


def _add_categories(cat, raw, spec, prof, items, categories, pop, seats=0):
    added, skipped = [], []
    for c in categories or []:
        catname = CATEGORY_KEYS.get(c)
        if not catname:
            continue
        if any(raw.get(pid, {}).get("category") == catname for pid in items):
            continue
        order = [p for p in spec.suggest if raw.get(p, {}).get("category") == catname]
        rest = sorted((p for p in cat if raw.get(p, {}).get("category") == catname and p not in order and p not in PRIMARY_ACCESS),
                      key=lambda p: (-pop.get(p, 0), cat[p].pmin))
        chosen = next((p for p in order + rest if p not in items and _usable(cat, p, prof, items)), None)
        if chosen:
            items[chosen] = _default_qty(cat, chosen, prof, spec, seats)
            added.append(c)
        else:
            skipped.append(c)
    return added, skipped


def _add_groups(cat, spec, prof, items, groups, pop, seats):
    added, covered, skipped = [], [], []
    for g in groups:
        pids = NEED_GROUPS[g]
        if any(p in items for p in pids):
            covered.append(g)
            continue
        ranked = [p for p in spec.suggest if p in pids] + sorted((p for p in pids if p not in spec.suggest), key=lambda p: (-pop.get(p, 0), pids.index(p)))
        chosen = next((p for p in ranked if p not in PRIMARY_ACCESS and _usable(cat, p, prof, items)), None)
        if chosen:
            items[chosen] = _default_qty(cat, chosen, prof, spec, seats)
            added.append(g)
        else:
            skipped.append(g)
    return added, covered, skipped


def _tag_products(cat, spec, prof, items, tags, seats):
    added, skipped = [], []
    for tag in tags or []:
        if tag in NEED_GROUPS:
            continue
        pid = profiles.NEED_TAGS.get(tag)
        if not pid or pid in items:
            continue
        if pid in PRIMARY_ACCESS:
            continue
        if _usable(cat, pid, prof, items):
            items[pid] = _default_qty(cat, pid, prof, spec, seats)
            added.append(tag)
        else:
            skipped.append(tag)
    return added, skipped


def _add_products(cat, spec, prof, items, pids, seats):
    for pid in pids or []:
        if pid in items or pid in PRIMARY_ACCESS or pid not in cat:
            continue
        if _usable(cat, pid, prof, items):
            items[pid] = _default_qty(cat, pid, prof, spec, seats)


def _money(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), ROUND_HALF_UP))


def with_tax(quote: dict, gstin_status: str) -> dict:
    ex = Decimal(quote["monthly_inr"])
    gst = (ex * GST_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)
    setup = Decimal(quote["setup_total_inr"])
    setup_gst = (setup * GST_RATE).quantize(Decimal("0.01"), ROUND_HALF_UP)
    quote["tax"] = {
        "rate_pct": 18, "monthly_ex_gst": _money(ex), "monthly_gst": _money(gst), "monthly_incl_gst": _money(ex + gst),
        "setup_ex_gst": _money(setup), "setup_gst": _money(setup_gst), "setup_incl_gst": _money(setup + setup_gst),
        "itc_monthly": _money(gst) if gstin_status in ("active", "unverified") else "0.00",
        "itc_eligible": gstin_status in ("active", "unverified"),
    }
    quote["price_basis"] = "excl. GST; GST at 18% shown separately"
    return quote


def decorate(cat, raw, quote: dict, spec: profiles.Spec, prof: dict, seat_roles, pop: dict) -> dict:
    """Owner-facing names and notes."""
    sites = prof["num_sites"]
    for ln in quote["lines"]:
        pid, q = ln["product_id"], ln["qty"]
        ln["label"] = spec.labels.get(pid) or profiles.LABEL.get(pid, ln["name"])
        ln["spec"] = ln["name"]
        ln["category"] = raw.get(pid, {}).get("category", "")
        ln["kind"] = "digital" if ln["install_days"] <= DIGITAL_MAX_DAYS else "field"
        if pid == "P16" and spec.roles:
            ln["note"] = ", ".join(f"{n} {label}" for label, n in seat_roles)
        elif pid in ("P07", "P08"):
            ln["note"] = f"{q} line{'s' if q > 1 else ''} for you and your key staff"
        elif pid == "P19":
            ln["note"] = f"{q} billing counter{'s' if q > 1 else ''}"
        elif pid == "P23":
            ln["note"] = f"{q} camera{'s' if q > 1 else ''}"
        elif pid in ("P20", "P24"):
            ln["note"] = f"{q} device{'s' if q > 1 else ''}"
        elif pid == "P25":
            ln["note"] = f"{q} vehicle{'s' if q > 1 else ''}"
        elif pid == "P12":
            ln["note"] = f"{q} call channel{'s' if q > 1 else ''}"
        elif ln["unit"] == "per site" and sites > 1:
            ln["note"] = f"one per location, {q} locations"
        share = pop.get(pid)
        if share is not None and share >= 0.25:
            ln["popularity"] = round(share * 100)
    return quote


def pick(cat, raw, profile_raw: dict, city_tiers: dict | None = None, categories: list[str] | None = None,
         need_tags: list[str] | None = None, want_products: list[str] | None = None):
    prof = to_engine_profile(profile_raw, city_tiers)
    spec = profiles.spec_for(profile_raw.get("business_type"), prof["segment"])
    pop, _ = popularity(spec)
    items, seat_roles = _base_items(cat, spec, prof)
    seats = sum(n for _, n in seat_roles)
    added, skipped = _add_categories(cat, raw, spec, prof, items, categories, pop, seats)
    groups = [t for t in (need_tags or []) if t in NEED_GROUPS]
    g_added, g_covered, g_skipped = _add_groups(cat, spec, prof, items, groups, pop, seats)
    t_added, t_skipped = _tag_products(cat, spec, prof, items, need_tags, seats)
    _add_products(cat, spec, prof, items, want_products, seats)
    quote = build_quote(cat, prof, items)
    if quote["status"] == "blocked":
        bad = {v["product"] for v in quote["violations"] if v["severity"] == "block" and v["product"]}
        bad -= {pid for pid in items if pid in spec.access}
        for pid in bad:
            items.pop(pid, None)
        quote = build_quote(cat, prof, items)
    quote["bundle_name"] = spec.bundle
    decorate(cat, raw, quote, spec, prof, seat_roles, pop)
    with_tax(quote, prof["gstin_status"])
    final = {l["product_id"] for l in quote["lines"]}
    g_lost = [g for g in g_added + g_covered if not any(p in final for p in NEED_GROUPS[g])]
    extras = {"asked": groups + [t for t in (need_tags or []) if t in profiles.NEED_TAGS] + list(categories or []), "included_needs": [g for g in g_added + g_covered if g not in g_lost] + added + t_added,
              "skipped_needs": g_skipped + g_lost + skipped + t_skipped,
              "business": spec.name, "tagline": spec.tagline, "why": spec.why, "seat_roles": seat_roles}
    return spec.bundle, items, prof, quote, extras


def quote_items(cat, raw, profile_raw: dict, items: dict, city_tiers=None, price_point: str = "list") -> dict:
    prof = to_engine_profile(profile_raw, city_tiers)
    spec = profiles.spec_for(profile_raw.get("business_type"), prof["segment"])
    pop, _ = popularity(spec)
    seat_roles, _ = _sized(spec, prof)
    quote = build_quote(cat, prof, items, price_point)
    quote["bundle_name"] = spec.bundle
    decorate(cat, raw, quote, spec, prof, seat_roles, pop)
    return with_tax(quote, prof["gstin_status"])


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


def suitable_products(cat, raw, profile_raw, city_tiers=None, categories=None, needs=None, need_tags=None):
    prof = to_engine_profile(profile_raw, city_tiers)
    spec = profiles.spec_for(profile_raw.get("business_type"), prof["segment"])
    wanted = {CATEGORY_KEYS.get(c, c) for c in (categories or [])}
    rec_name, rec_items, _, _, _ = pick(cat, raw, profile_raw, city_tiers, categories, need_tags)
    pop, n_similar = popularity(spec)
    has_primary = any(x in rec_items for x in PRIMARY_ACCESS)
    rank = {pid: i for i, pid in enumerate(spec.suggest)}
    products = []
    for pid in sorted(cat):
        p = cat[pid]
        row = raw.get(pid, {})
        category = row.get("category", "")
        if wanted and category not in wanted and pid not in rec_items:
            continue
        if pid in PRIMARY_ACCESS and pid not in rec_items and has_primary:
            continue
        reasons = _eligibility(prof, p)
        share = pop.get(pid, 0)
        if prof["segment"] not in p.targets and pid not in rec_items and pid not in rank and share < 0.1:
            continue
        mid = (p.pmin + p.pmax) / 2
        products.append({
            "product_id": pid, "name": p.name, "label": spec.labels.get(pid) or profiles.LABEL.get(pid, p.name),
            "category": category, "description": row.get("description", ""), "unit": p.unit,
            "price_inr": int(mid) if mid == int(mid) else round(mid, 2), "price_range_inr": [p.pmin, p.pmax],
            "setup_inr": p.setup, "min_contract_months": p.min_contract, "install_days": p.install_days,
            "requires_gstin": p.gstin, "eligible": not reasons, "eligibility_note": reasons[0] if reasons else None,
            "in_recommended_bundle": pid in rec_items, "recommended_for_you": pid in rank,
            "popularity_pct": round(share * 100) if share >= 0.15 else None,
        })
    products.sort(key=lambda x: (not x["in_recommended_bundle"], not x["recommended_for_you"],
                                 rank.get(x["product_id"], 99), -(x["popularity_pct"] or 0), x["price_inr"]))
    return {"recommended_bundle": rec_name, "business": spec.name, "similar_customers": n_similar, "products": products}
