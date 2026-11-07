import time
import pytest
from udyam import store, orders, recommender, data_loader, privacy


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"), raising=False)
    store.reset_connection()
    store.seed_partners(["Pune"])
    store.mark_ready()


def _order():
    prof = {"segment": "micro", "business_type": "salon", "employees": 4, "num_sites": 1, "city": "Pune", "gstin_status": "active"}
    name, items, _, quote, _ = recommender.pick(data_loader.catalogue(), data_loader.catalogue_raw(), prof, data_loader.city_tiers(), [], [])
    quote = recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), prof, items, data_loader.city_tiers())
    o = orders.create_order("LV-TEST", quote, "Test Salon", "Pune")
    privacy.create_consent(o["order_id"], "LV-TEST")
    return o


def test_pass_starts_fulfilment_and_assigns_an_engineer():
    o = _order()
    assert o["status"] == "awaiting_kyc"
    o = orders.apply_kyc(o["order_id"], "PASS", [], {})
    assert o["status"] == "in_progress"
    assert o["engineer"] is not None


def test_review_waits_for_a_person_then_continues():
    o = _order()
    o = orders.apply_kyc(o["order_id"], "REVIEW", [{"code": "R4", "severity": "REVIEW", "message": "check"}], {})
    assert o["status"] == "kyc_review"
    o = orders.resolve_review(o["order_id"], "approve", "ok", "verification team")
    assert o["status"] == "in_progress"


def test_reject_asks_for_a_new_upload():
    o = _order()
    o = orders.apply_kyc(o["order_id"], "REJECT", [{"code": "R1", "severity": "HARD", "message": "bad"}], {})
    assert o["status"] == "kyc_rejected"


def test_digital_lines_go_live_without_a_person(monkeypatch):
    monkeypatch.setattr(orders, "DIGITAL_ACTIVATION_SECONDS", 0)
    o = orders.apply_kyc(_order()["order_id"], "PASS", [], {})
    time.sleep(0.05)
    o = orders.get(o["order_id"])
    assert any(l["kind"] == "digital" and l["state"] == "live" for l in o["lines"])
    assert any(l["kind"] == "field" and l["state"] != "live" for l in o["lines"])


def test_customer_view_hides_internal_rule_codes():
    o = _order()
    o = orders.apply_kyc(o["order_id"], "REVIEW", [{"code": "R4", "severity": "REVIEW", "message": "x"}], {"customer": [{"text": "plain"}]})
    assert "raw_findings" not in o["kyc"]
    assert "raw_findings" in orders.get(o["order_id"], admin=True)["kyc"]


def test_nothing_goes_live_before_verification():
    o = _order()
    with pytest.raises(ValueError):
        orders.admin_set_status(o["order_id"], "mark_live")
    with pytest.raises(ValueError):
        orders.admin_set_status(o["order_id"], "approve")
    with pytest.raises(ValueError):
        orders.advance_line(o["order_id"], o["lines"][0]["product_id"])


def test_an_order_never_moves_backwards():
    o = orders.apply_kyc(_order()["order_id"], "PASS", [], {})
    assert o["status"] == "in_progress"
    with pytest.raises(ValueError):
        orders._save(o["order_id"], status="awaiting_kyc")
    with pytest.raises(ValueError):
        orders.apply_kyc(o["order_id"], "REJECT", [], {})


def test_documents_need_consent():
    prof = {"segment": "micro", "business_type": "salon", "employees": 4, "num_sites": 1, "city": "Pune", "gstin_status": "active"}
    _, items, _, _, _ = recommender.pick(data_loader.catalogue(), data_loader.catalogue_raw(), prof, data_loader.city_tiers(), [], [])
    quote = recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), prof, items, data_loader.city_tiers())
    o = orders.create_order("LV-NOC", quote, "No Consent Salon", "Pune")
    with pytest.raises(ValueError):
        orders.apply_kyc(o["order_id"], "PASS", [], {})


def test_engineer_is_from_the_customers_city():
    store.seed_partners(["Pune", "Kolkata"])
    o = orders.apply_kyc(_order()["order_id"], "PASS", [], {})
    assert o["engineer"]["city"] == "Pune"
