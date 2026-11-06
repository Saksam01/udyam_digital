"""The 12 fixtures must match the KYC answer key."""

import pytest
from udyam import data_loader

EXPECTED = {
    "K01": "REJECT", "K02": "PASS", "K03": "PASS", "K04": "REVIEW",
    "K05": "REVIEW", "K06": "REJECT", "K07": "REJECT", "K08": "PASS",
    "K09": "PASS", "K10": "REVIEW", "K11": "REJECT", "K12": "PASS",
}


@pytest.mark.parametrize("case_id,verdict", EXPECTED.items())
def test_kyc_verdict(case_id, verdict):
    assert data_loader.assess_case(case_id)["verdict"] == verdict
