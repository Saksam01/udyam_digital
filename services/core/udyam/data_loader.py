"""Loads and caches the catalogue, registries, tiers and KYC fixtures."""

from __future__ import annotations
import csv, json, os, functools
from udyam.quote_engine import load_catalogue
from udyam.kyc_engine import Registry, assess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.normpath(os.path.join(HERE, "..", "data")))

def _p(name: str) -> str:
    return os.path.join(DATA_DIR, name)

# K04's GST certificate is deliberately too blurred to read.
BLURRED = {"K04": {"gst_certificate": 1.0}}


@functools.lru_cache(maxsize=1)
def catalogue():
    return load_catalogue(_p("product_catalogue.csv"))


@functools.lru_cache(maxsize=1)
def catalogue_raw() -> dict:
    """Full catalogue rows (category, description, prices) keyed by product_id."""
    rows = {}
    with open(_p("product_catalogue.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["product_id"]] = r
    return rows


@functools.lru_cache(maxsize=1)
def city_tiers() -> dict[str, int]:
    tiers: dict[str, int] = {}
    with open(_p("smb_leads.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            city = (r.get("city") or "").strip()
            tier = r.get("city_tier")
            if city and tier and tier.isdigit():
                tiers[city.title()] = int(tier)
    return tiers


@functools.lru_cache(maxsize=1)
def registry() -> Registry:
    return Registry(_p("mock_gstin_registry.csv"), _p("mock_udyam_registry.csv"))


@functools.lru_cache(maxsize=1)
def fixtures() -> dict:
    with open(_p("kyc_fixtures.json"), encoding="utf-8") as f:
        return json.load(f)


@functools.lru_cache(maxsize=1)
def _leads_by_gstin() -> dict:
    out = {}
    with open(_p("smb_leads.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("gstin"):
                out[r["gstin"]] = r
    return out


def lead_for(gstin: str, trade_name: str | None = None, address: str | None = None):
    lead = _leads_by_gstin().get(gstin)
    if lead:
        return lead
    if trade_name:  # fall back to a name + city match
        for r in _leads_by_gstin().values():
            if r.get("business_name") == trade_name and (not address or r.get("city", "") in address):
                return r
    return None


def kyc_case_ids() -> list[str]:
    return sorted(fixtures().keys())


def kyc_case_summary(case_id: str) -> dict:
    fx = fixtures()[case_id]
    g = fx["gst"]
    return {"case_id": case_id, "business": g.get("trade_name"),
            "constitution": g.get("constitution"), "city_state": g.get("address", "").split(",")[-2:]}


def assess_case(case_id: str) -> dict:
    fx = fixtures().get(case_id)
    if not fx:
        raise KeyError(case_id)
    gst = dict(fx["gst"]); gst["gstin"] = gst["gstin"].rstrip("?")
    lead = lead_for(gst["gstin"], gst.get("trade_name"), gst.get("address"))
    app = {"quality": BLURRED.get(case_id, {}), "gst": gst,
           "udyam": fx.get("udyam"), "sig": fx["sig"], "bill": fx["bill"]}
    out = assess(app, registry(), lead)
    out["case_id"] = case_id
    out["business"] = gst.get("trade_name")
    return out
