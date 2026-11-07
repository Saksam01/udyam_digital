from __future__ import annotations
import csv, hashlib, json, uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

PRIMARY_ACCESS = ("P01", "P02", "P03", "P04", "P05", "P06")
EXCLUSIVE = [("X.fixed_tiers", {"P01", "P02", "P03", "P04"}), ("X.leased", {"P05", "P06"}), ("X.postpaid", {"P07", "P08"})]
ALTERNATIVES = {"P03": ["P02"], "P06": ["P05", "P03"], "P05": ["P03", "P02"], "P10": ["P09"], "P21": ["P20", "P22"],
                "P12": ["P08"], "P13": ["P08"], "P11": [], "P15": [], "P14": [], "P24": []}
DISCOUNT_FLOOR_OK = lambda profile, contract: contract >= 24 or (profile["segment"] == "multi" and profile["num_sites"] >= 8)

@dataclass(frozen=True)
class Product:
    id: str; name: str; unit: str; pmin: int; pmax: int; setup: int; min_contract: int; tiers: frozenset
    min_emp: int; min_sites: int; gstin: bool; requires_one_of: tuple; install_days: int; targets: frozenset

def load_catalogue(path: str) -> dict[str, Product]:
    cat = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        cat[r["product_id"]] = Product(
            r["product_id"], r["product_name"], r["unit"], int(r["price_min_inr_per_month"]), int(r["price_max_inr_per_month"]),
            int(r["one_time_setup_inr"]), int(r["min_contract_months"]), frozenset(int(t) for t in r["available_city_tiers"].split(";")),
            int(r["min_employees"]), int(r["min_sites"]), r["requires_gstin"] == "Y",
            tuple(x for x in r["requires_one_of"].split("|") if x), int(r["typical_install_days"]), frozenset(r["target_segments"].split(";")))
    return cat

@dataclass
class Violation:
    rule: str; product: str | None; severity: str; message: str; fix: list = field(default_factory=list)

def evaluate(cat, profile: dict, items: dict[str, int]) -> list[Violation]:
    v: list[Violation] = []
    for pid, q in items.items():
        if pid not in cat:
            v.append(Violation("G.unknown_product", pid, "block", f"{pid} is not in the catalogue")); continue
        p = cat[pid]
        if q < 1: v.append(Violation("B.qty_min", pid, "block", "quantity must be at least 1"))
        if p.unit == "per site" and q > profile["num_sites"]:
            v.append(Violation("B.qty_per_site", pid, "block", f"{p.name} is per site; max {profile['num_sites']}"))
        if profile["city_tier"] not in p.tiers:
            v.append(Violation("G.tier", pid, "block", f"{p.name} is sold only in tier {sorted(p.tiers)} cities", ALTERNATIVES.get(pid, [])))
        if profile["employees"] < p.min_emp:
            v.append(Violation("G.min_employees", pid, "block", f"{p.name} needs at least {p.min_emp} employees", ALTERNATIVES.get(pid, [])))
        if profile["num_sites"] < p.min_sites:
            v.append(Violation("G.min_sites", pid, "block", f"{p.name} needs at least {p.min_sites} sites", ALTERNATIVES.get(pid, [])))
        if p.gstin:
            gs = profile["gstin_status"]
            if gs == "unverified":
                v.append(Violation("G.gstin_pending", pid, "conditional", f"{p.name} needs an active GSTIN; verified at KYC"))
            elif gs != "active":
                v.append(Violation("G.gstin", pid, "block", f"{p.name} cannot be sold without a valid, active GSTIN (status: {gs})", ALTERNATIVES.get(pid, [])))
        if p.requires_one_of and not any(x in items for x in p.requires_one_of):
            v.append(Violation("G.requires_one_of", pid, "block", f"{p.name} needs one of {'|'.join(p.requires_one_of)} in the same bundle", list(p.requires_one_of)))
        if p.requires_one_of and any(x in items for x in p.requires_one_of):
            if not any(x in items and not _gate_fail(cat[x], profile) for x in p.requires_one_of):
                v.append(Violation("G.prereq_eligible", pid, "block", f"the prerequisite for {p.name} is itself not eligible"))
        if segment_code(profile) not in p.targets:
            v.append(Violation("T.target_segments", pid, "advise", f"{p.name} is not usually sold to this segment"))
    if not any(x in items for x in PRIMARY_ACCESS):
        v.append(Violation("B.one_primary_access", None, "warn", "bundle has no primary internet access (P01-P06)"))
    for rid, grp in EXCLUSIVE:
        if len(grp & items.keys()) > 1:
            v.append(Violation(rid, None, "warn", f"pick one of {sorted(grp)}"))
    if {"P05", "P06"} & items.keys() and {"P01", "P02", "P03", "P04"} & items.keys():
        v.append(Violation("X.leased_plus_fixed", None, "warn", "leased line and broadband in one bundle"))
    return v

def _gate_fail(p: Product, prof) -> bool:
    return (prof["city_tier"] not in p.tiers or prof["employees"] < p.min_emp or prof["num_sites"] < p.min_sites
            or (p.gstin and prof["gstin_status"] not in ("active", "unverified")))

def segment_code(profile): return profile["segment"]

def _mid(p: Product) -> Decimal: return (Decimal(p.pmin) + Decimal(p.pmax)) / 2

def build_quote(cat, profile: dict, items: dict[str, int], price_point: str = "list", catalogue_version: str = "2026-10-04") -> dict:
    violations = evaluate(cat, profile, items)
    blocking = [x for x in violations if x.severity == "block"]
    lines, mmin, mmax, mlist, setup = [], 0, 0, Decimal(0), 0
    for pid, q in sorted(items.items()):
        if pid not in cat: continue
        p = cat[pid]
        unit_list = _mid(p)
        lines.append({"product_id": pid, "name": p.name, "unit": p.unit, "qty": q,
                      "unit_price_range_inr": [p.pmin, p.pmax], "unit_list_inr": str(unit_list),
                      "line_monthly_list_inr": str(unit_list * q), "setup_inr": p.setup * q,
                      "min_contract_months": p.min_contract, "install_days": p.install_days})
        mmin += p.pmin * q; mmax += p.pmax * q; mlist += unit_list * q; setup += p.setup * q
    contract = max((cat[x].min_contract for x in items if x in cat), default=0)
    floor_ok = DISCOUNT_FLOOR_OK(profile, contract)
    if price_point == "floor" and not floor_ok:
        violations.append(Violation("P.floor_not_allowed", None, "block", "floor price needs a 24-month contract or 8+ sites"))
        blocking = [x for x in violations if x.severity == "block"]
    monthly = Decimal(mmin) if (price_point == "floor" and floor_ok) else mlist.quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert mmin <= monthly <= mmax, "B.monthly_range invariant broken"
    eta = max((cat[x].install_days for x in items if x in cat), default=0)
    body = {"catalogue_version": catalogue_version, "profile": profile, "lines": lines,
            "monthly_inr": str(monthly), "monthly_range_inr": [mmin, mmax], "setup_total_inr": setup,
            "contract_months": contract, "activation_eta_days": eta,
            "per_item_eta_days": {l["product_id"]: l["install_days"] for l in lines},
            "price_basis": "excl. GST - tax treatment to be confirmed", "floor_price_allowed": floor_ok,
            "status": "blocked" if blocking else ("conditional" if any(x.severity == "conditional" for x in violations) else "ok"),
            "violations": [x.__dict__ for x in violations]}
    body["quote_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    body["quote_id"] = "Q-" + uuid.uuid4().hex[:10].upper()
    return body

if __name__ == "__main__":
    import sys
    cat = load_catalogue(sys.argv[1])
    micro = {"segment": "micro", "city_tier": 2, "employees": 3, "num_sites": 1, "gstin_status": "none"}
    for name, prof, it in [
        ("M1", micro, {"P01": 1, "P07": 2}),
        ("M2 full", micro, {"P01": 1, "P07": 2, "P19": 1, "P22": 1, "P23": 2}),
        ("PO1 core", {"segment": "prof", "city_tier": 2, "employees": 7, "num_sites": 1, "gstin_status": "none"}, {"P02": 1, "P16": 7, "P07": 2}),
        ("MS1 S=8 core", {"segment": "multi", "city_tier": 2, "employees": 71, "num_sites": 8, "gstin_status": "active"}, {"P01": 8, "P09": 8, "P08": 4, "P19": 8}),
        ("SM2 core", {"segment": "mfg", "city_tier": 2, "employees": 85, "num_sites": 1, "gstin_status": "active"}, {"P05": 1, "P08": 4, "P16": 11, "P21": 1}),
        ("BAD P03 micro", micro, {"P03": 1, "P07": 1}),
        ("BAD P05+P11", {"segment": "mfg", "city_tier": 1, "employees": 40, "num_sites": 1, "gstin_status": "active"}, {"P05": 1, "P11": 1}),
        ("BAD P10 2 sites", {"segment": "multi", "city_tier": 1, "employees": 40, "num_sites": 2, "gstin_status": "active"}, {"P02": 2, "P10": 2}),
        ("BAD P23 no access", micro, {"P23": 2, "P07": 1}),
        ("BAD P15 no gstin", micro, {"P01": 1, "P15": 1}),
    ]:
        q = build_quote(cat, prof, it)
        print(name, q["status"], q["monthly_inr"], q["monthly_range_inr"], q["setup_total_inr"], q["contract_months"], q["activation_eta_days"],
              [(x["rule"], x["product"]) for x in q["violations"] if x["severity"] in ("block", "warn")])
