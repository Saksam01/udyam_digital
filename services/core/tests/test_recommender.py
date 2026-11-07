from decimal import Decimal
from udyam import data_loader, recommender


def _pick(business_type, segment, employees=6, sites=1, tags=None):
    prof = {"segment": segment, "business_type": business_type, "employees": employees, "num_sites": sites,
            "city": "Pune", "gstin_status": "active", "need_tags": tags or []}
    return recommender.pick(data_loader.catalogue(), data_loader.catalogue_raw(), prof, data_loader.city_tiers(), [], tags)


def test_each_business_type_gets_its_own_bundle():
    cases = [("kirana", "micro"), ("salon", "micro"), ("clinic", "prof"), ("software", "prof"), ("restaurant", "multi"), ("autoparts", "mfg")]
    names, product_sets = set(), set()
    for bt, seg in cases:
        name, items, *_ = _pick(bt, seg, sites=3 if seg == "multi" else 1)
        names.add(name)
        product_sets.add(frozenset(items))
    assert len(names) == len(cases)
    assert len(product_sets) == len(cases)


def test_salon_is_not_offered_the_kirana_pack():
    salon = _pick("salon", "micro")[0]
    kirana = _pick("kirana", "micro")[0]
    assert salon != kirana
    assert "Salon" in salon


def test_email_seats_never_exceed_headcount():
    for bt, seg, emp in [("clinic", "prof", 1), ("software", "prof", 4), ("ca", "prof", 2)]:
        _, items, *_ = _pick(bt, seg, employees=emp)
        assert items.get("P16", 0) <= emp


def test_gst_is_added_on_top_and_adds_up():
    q = _pick("salon", "micro")[3]
    tax = q["tax"]
    base = Decimal(tax["monthly_ex_gst"])
    assert base == Decimal(q["monthly_inr"])
    assert Decimal(tax["monthly_gst"]) == (base * Decimal("0.18")).quantize(Decimal("0.01"))
    assert Decimal(tax["monthly_incl_gst"]) == base + Decimal(tax["monthly_gst"])
    assert tax["itc_eligible"] is True


def test_no_input_credit_without_a_gst_number():
    prof = {"segment": "micro", "business_type": "salon", "employees": 3, "num_sites": 1, "city": "Pune", "gstin_status": "none"}
    q = recommender.pick(data_loader.catalogue(), data_loader.catalogue_raw(), prof, data_loader.city_tiers(), [], [])[3]
    assert q["tax"]["itc_eligible"] is False


def test_asked_for_extras_are_added_when_eligible():
    _, items, *_ = _pick("salon", "micro", tags=["cctv"])
    assert "P23" in items
