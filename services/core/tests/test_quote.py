from udyam import data_loader
from udyam.quote_engine import build_quote

CAT = data_loader.catalogue()
MICRO = {"segment": "micro", "city_tier": 2, "employees": 3, "num_sites": 1, "gstin_status": "none"}


def test_m1_price_is_exact():
    q = build_quote(CAT, MICRO, {"P01": 1, "P07": 2})
    assert q["status"] == "ok"
    assert q["monthly_inr"] == "1797.00"
    assert q["monthly_range_inr"] == [1597, 1997]
    assert q["contract_months"] == 12


def test_price_never_leaves_the_range():
    q = build_quote(CAT, MICRO, {"P01": 1, "P07": 2, "P19": 1})
    lo, hi = q["monthly_range_inr"]
    assert lo <= float(q["monthly_inr"]) <= hi


def test_tier1_product_blocked_for_micro():
    q = build_quote(CAT, MICRO, {"P03": 1, "P07": 1})
    assert q["status"] == "blocked"
    rules = {v["rule"] for v in q["violations"]}
    assert "G.tier" in rules


def test_gstin_product_blocked_without_gstin():
    q = build_quote(CAT, MICRO, {"P01": 1, "P15": 1})
    assert q["status"] == "blocked"
    assert any(v["rule"] == "G.gstin" for v in q["violations"])


def test_dependency_message_names_the_products():
    from udyam import recommender, data_loader
    prof = {"segment": "micro", "business_type": "kirana", "employees": 3, "num_sites": 1, "city": "Pune", "gstin_status": "none"}
    q = recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), prof, {"P23": 1}, data_loader.city_tiers())
    assert q["status"] == "blocked"
    msg = next(v["message"] for v in q["violations"] if v["severity"] == "block")
    assert "Biz Fibre 100" in msg and "P01" not in msg
