import os
import numpy as np
import pytest
from udyam import data_loader, kyc_engine, kyc_extract, kyc_service, orders, privacy, recommender, store


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "t.db"), raising=False)
    monkeypatch.setattr(privacy, "VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setenv("KYC_VAULT_KEY", "q1b2s7ql0yJ0lC2Vxk7mH5n4mT5p8b0Hc3s1v6Gm9dE=")
    store.reset_connection()
    store.seed_partners(["Pune"])
    store.mark_ready()


def _order(name="Harmony Dental Care"):
    prof = {"segment": "prof", "business_type": "dental", "employees": 5, "num_sites": 1, "city": "Pune", "gstin_status": "active"}
    _, items, _, _, _ = recommender.pick(data_loader.catalogue(), data_loader.catalogue_raw(), prof, data_loader.city_tiers(), [], [])
    quote = recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), prof, items, data_loader.city_tiers())
    return orders.create_order("LV-PRIV", quote, name, "Pune")


def test_documents_of_another_business_are_rejected():
    assert kyc_service.verify_case("K02", "Clofe Dental")["verdict"] == "REJECT"
    assert kyc_service.verify_case("K02", "Harmony Dental")["verdict"] == "PASS"
    assert kyc_service.verify_case("K02", "harmony dental care clinic")["verdict"] == "PASS"


def test_unity_vs_trinity_is_not_a_match_even_at_ninety_percent():
    m = kyc_engine.match_name("Unity Bake House Pvt Ltd", "Trinity Bake House Pvt Ltd")
    assert m["score"] >= 0.85 and m["band"] != "PASS"


def test_every_failed_rule_carries_evidence():
    res = data_loader.assess_case("K07")
    assert res["verdict"] == "REJECT"
    for f in res["findings"]:
        if f["code"] in ("R6", "R10", "R24"):
            e = f["evidence"]
            assert e["extracted"] and e["reference"] and e["score"] is not None
    assert any(t["result"] == "pass" for t in res["trace"])


def test_aadhaar_and_pan_are_masked():
    assert kyc_extract.mask_ids("ID 2345 6789 0123") == "ID XXXX XXXX 0123"
    assert kyc_extract.mask_ids("234567890123") == "XXXX XXXX 0123"
    assert kyc_extract.mask_ids("PAN ABCPS1234K") == "PAN ABXXXXXXXK"


def test_aadhaar_digits_are_blacked_out_on_the_page():
    gray = np.full((100, 400), 255, np.uint8)
    lines = [{"text": "2345 6789 0123", "box": [10, 10, 300, 30],
              "words": [("2345", [10, 10, 80, 30]), ("6789", [110, 10, 80, 30]), ("0123", [210, 10, 80, 30])]}]
    out, hits = kyc_extract.redact_image(gray, lines)
    assert hits == 2
    assert out[25, 50] == 0 and out[25, 150] == 0 and out[25, 250] == 255


def test_consent_artifact_is_tamper_evident_and_withdrawable():
    o = _order()
    c = privacy.create_consent(o["order_id"], o["lead_id"])
    assert c["purpose"].startswith("DoT telecom KYC") and c["data_retention_days"] == 180
    assert privacy.get_consent(c["consent_id"])["integrity_ok"]
    store.x("UPDATE consents SET artifact=replace(artifact, '180', '999') WHERE consent_id=?", (c["consent_id"],))
    assert not privacy.get_consent(c["consent_id"])["integrity_ok"]


def test_review_pages_are_encrypted_and_deleted_after_the_decision():
    o = _order()
    c = privacy.create_consent(o["order_id"], o["lead_id"])
    pages = {"signatory_id": {"png": b"\x89PNG fake page", "size": [10, 10], "boxes": {}, "doctype": "sig"}}
    orders.apply_kyc(o["order_id"], "REVIEW", [], {"consent": c["consent_id"]}, pages=pages)
    raw = open(os.path.join(privacy.VAULT_DIR, o["order_id"], "signatory_id.bin"), "rb").read()
    assert b"fake page" not in raw
    assert privacy.get_page(o["order_id"], "signatory_id") == b"\x89PNG fake page"
    orders.resolve_review(o["order_id"], "approve", "ok")
    assert privacy.get_page(o["order_id"], "signatory_id") is None


def test_withdrawal_erases_details_and_reopens_kyc():
    o = _order()
    c = privacy.create_consent(o["order_id"], o["lead_id"])
    orders.apply_kyc(o["order_id"], "REVIEW", [], {"summary": {"business": "X"}},
                     pages={"gst_certificate": {"png": b"p", "size": [1, 1], "boxes": {}, "doctype": "gst"}})
    privacy.withdraw(c["consent_id"])
    got = orders.get(o["order_id"], verifier=True)
    assert got["status"] == "awaiting_kyc" and got["kyc"]["erased"]
    assert privacy.get_page(o["order_id"], "gst_certificate") is None


def test_a_won_lead_is_not_shown_as_a_probability():
    from udyam import crm
    assert crm._display_likelihood({"status": "won", "stage": "Activated", "p_activate": 0.66}) == 1.0
    assert crm._display_likelihood({"status": "lost", "stage": "Quote accepted", "p_activate": 0.4}) == 0.0


def test_address_proof_must_be_in_the_service_city():
    assert kyc_service.verify_case("K02", "Harmony Dental Care", {"city": "Kolkata", "sites": 1})["verdict"] == "PASS"
    assert kyc_service.verify_case("K02", "Harmony Dental Care", {"city": "Mumbai", "sites": 1})["verdict"] == "REJECT"
    assert kyc_service.verify_case("K02", "Harmony Dental Care", {"city": "Mumbai", "sites": 3})["verdict"] == "REVIEW"
    assert kyc_engine.city_in("Bengaluru", "12 MG Road, Bangalore, Karnataka")[0]
