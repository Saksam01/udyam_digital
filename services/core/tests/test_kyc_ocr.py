import os
import pytest
from udyam import kyc_extract, kyc_service, data_loader

EXPECTED = {
    "K01": "REJECT", "K02": "PASS", "K03": "PASS", "K04": "REVIEW",
    "K05": "REVIEW", "K06": "REJECT", "K07": "REJECT", "K08": "PASS",
    "K09": "PASS", "K10": "REVIEW", "K11": "REJECT", "K12": "PASS",
}
DOCS = os.path.join(data_loader.DATA_DIR, "kyc_documents")


def _files(case_id):
    out = {}
    for slot in kyc_extract.DOC_SLOT.values():
        path = os.path.join(DOCS, f"{case_id}_{slot}.png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                out[slot] = f.read()
    return out


@pytest.mark.skipif(not kyc_extract.available(), reason="tesseract not installed")
def test_ocr_verdicts_match_the_answer_key():
    wrong = {}
    for case_id, verdict in EXPECTED.items():
        res = kyc_service.verify_upload(_files(case_id))
        got = res.get("verdict") if res["status"] == "verdict" else res["status"]
        if got != verdict:
            wrong[case_id] = got
    assert not wrong


def test_missing_required_document_is_asked_for_not_judged():
    files = _files("K02")
    files.pop("address_proof", None)
    res = kyc_service.verify_upload(files)
    assert res["status"] == "incomplete"


def test_customers_never_see_rule_codes_in_plain_findings():
    for f in kyc_service.friendly([{"code": "R18", "severity": "REVIEW", "message": "x", "customer_action": None}]):
        assert "R18" not in f["text"] and "mock" not in f["text"].lower()
