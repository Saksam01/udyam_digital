"""Smart KYC: identifier, name, registry and freshness checks, then a verdict."""

from __future__ import annotations
import csv, os, re, unicodedata, datetime as dt
from dataclasses import dataclass
from difflib import SequenceMatcher

MODE = os.getenv("ID_VALIDATION_MODE", "production")
if os.getenv("APP_ENV") == "production" and MODE == "mock":
    raise RuntimeError("ID_VALIDATION_MODE=mock is not allowed in production")
AS_OF = dt.date.fromisoformat(os.getenv("AS_OF_DATE", "2026-07-15"))
MAX_ADDR_PROOF_DAYS, BLUR_MIN = 90, 100
PASS, REVIEW = 0.95, 0.80
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GST_STATE = {"03": "Punjab", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "19": "West Bengal",
             "23": "Madhya Pradesh", "24": "Gujarat", "27": "Maharashtra", "29": "Karnataka", "32": "Kerala",
             "33": "Tamil Nadu", "36": "Telangana", "37": "Andhra Pradesh"}
UDYAM_STATE = {"MH": "Maharashtra", "KA": "Karnataka", "GJ": "Gujarat", "TN": "Tamil Nadu", "DL": "Delhi",
               "MP": "Madhya Pradesh", "TS": "Telangana", "WB": "West Bengal", "KL": "Kerala", "PB": "Punjab",
               "UP": "Uttar Pradesh", "RJ": "Rajasthan", "BR": "Bihar", "AP": "Andhra Pradesh"}
RULES = {"production": {"pan4": set("ABCFGHJLPT"), "district_00_ok": False, "state_alias": {}},
         "mock":       {"pan4": set("ABCFGHJLPT") | {"X"}, "district_00_ok": True, "state_alias": {"KR": "Karnataka"}}}[MODE]
GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{3})([A-Z])([A-Z])(\d{4})([A-Z])([1-9A-Z])Z([0-9A-Z])$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")

# identifiers
def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = CHARSET.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARSET[(36 - total % 36) % 36]

def validate_gstin(raw: str) -> dict:
    g = re.sub(r"\s", "", (raw or "").upper()); m = GSTIN_RE.match(g)
    if not m: return {"gstin": g, "format_ok": False}
    pan4 = m.group(3)
    return {"gstin": g, "format_ok": pan4 in RULES["pan4"], "state": GST_STATE.get(m.group(1)), "pan": g[2:12],
            "entity_type": "SYNTHETIC" if pan4 == "X" else pan4, "checksum_ok": gstin_check_char(g[:14]) == g[14],
            "relaxed_rules": ["pan_4th_char_X"] if pan4 == "X" else []}

def validate_udyam(raw: str) -> dict:
    u = (raw or "").strip().upper(); m = UDYAM_RE.match(u)
    if not m: return {"udyam": u, "format_ok": False}
    st, dist = m.group(1), m.group(2)
    state = UDYAM_STATE.get(st) or RULES["state_alias"].get(st)
    ok = state is not None and (dist != "00" or RULES["district_00_ok"])
    return {"udyam": u, "format_ok": ok, "state": state,
            "relaxed_rules": [r for r, c in (("district_00", dist == "00"), ("state_KR", st == "KR")) if c]}

# names
SUFFIX = [(r"\bprivate\s+limited\b", "pvt ltd"), (r"\bpvt\.?\s*ltd\.?", "pvt ltd"), (r"\bp\.?\s*ltd\b", "pvt ltd"),
          (r"\blimited liability partnership\b", "llp"), (r"\bl\.\s*l\.\s*p\.?", "llp"), (r"\blimited\b", "ltd"),
          (r"\bcompany\b", "co"), (r"&", " and ")]
BUSINESS_PREFIX = r"^\s*(m/s\.?|messrs\.?)\s+"
PERSON_HONORIFIC = r"\b(mr|mrs|ms|miss|dr|shri|sri|shree|smt|kumari)\b\.?"
GENERIC = {"the", "and", "pvt", "ltd", "llp", "co"}

def _base(s): return unicodedata.normalize("NFKC", s or "").lower()
def _clean(s): return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()
def norm_business(s, drop_suffix=False):
    s = re.sub(BUSINESS_PREFIX, "", _base(s))
    for pat, rep in SUFFIX: s = re.sub(pat, rep, s)
    if drop_suffix: s = re.sub(r"\b(pvt ltd|ltd|llp|co)\b", " ", s)
    return _clean(s)
def norm_person(s): return _clean(re.sub(PERSON_HONORIFIC, " ", _base(s)))

def levenshtein(a, b):
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def similarity(a: str, b: str) -> float:
    lev = 1 - levenshtein(a, b) / max(len(a), len(b), 1)
    return round(max(lev, SequenceMatcher(None, a, b).ratio()), 3)

def distinctive(s): return next((t for t in s.split() if t not in GENERIC), "")

def match_name(a: str, b: str, kind: str = "business") -> dict:
    na, nb = (norm_person(a), norm_person(b)) if kind == "person" else (norm_business(a), norm_business(b))
    score = similarity(na, nb); tok_ok = distinctive(na) == distinctive(nb)
    band = "PASS" if score >= PASS and tok_ok else ("REVIEW" if score >= REVIEW else "FAIL")
    return {"score": score, "distinctive_token_match": tok_ok, "band": band}

def match_legal_name(a: str, b: str) -> dict:
    """Proprietorship legal names 'Owner (Prop. Business)': match person and business parts separately."""
    (pa, ba), (pb, bb) = split_prop(a), split_prop(b)
    if not (ba and bb): return match_name(a, b)
    mp, mb = match_name(pa, pb, "person"), match_name(ba, bb)
    worst = min((mp, mb), key=lambda m: ["FAIL", "REVIEW", "PASS"].index(m["band"]))
    return {**worst, "person": mp, "business": mb}

def split_prop(legal_name):
    m = re.match(r"^(.*?)\s*\(\s*Prop\.?\s*(.*?)\)\s*$", legal_name or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)

# registries (look up by primary key only)
class Registry:
    def __init__(self, gst_csv, udyam_csv):
        self.gst = {r["gstin"]: r for r in csv.DictReader(open(gst_csv, encoding="utf-8"))}
        self.udyam = {r["udyam_number"]: r for r in csv.DictReader(open(udyam_csv, encoding="utf-8"))}

# verdict
@dataclass
class Finding:
    code: str; severity: str; message: str; customer_action: str | None = None
SEV = {"HARD": 3, "REVIEW": 2, "INFO": 1}

def assess(app: dict, reg: Registry, lead: dict | None = None) -> dict:
    """app = {'quality': {doc: laplacian_var}, 'gst': {...}, 'udyam': {...}|None, 'sig': {...}, 'bill': {...}} (OCR output, registry-repaired)"""
    f: list[Finding] = []; add = lambda *a: f.append(Finding(*a))
    for doc, lv in app.get("quality", {}).items():
        if lv < BLUR_MIN: add("R0", "REVIEW", f"{doc} too blurred (LapVar {lv:.0f})", f"Please re-take the photo of your {doc.replace('_', ' ')}")
    g = app["gst"]; v = validate_gstin(g["gstin"]); r = reg.gst.get(v["gstin"])
    gst_unreadable = app.get("quality", {}).get("gst_certificate", BLUR_MIN) < BLUR_MIN
    if gst_unreadable:
        add("R1", "REVIEW", "GSTIN not legible - identifier checks deferred", "Re-upload GST certificate"); r = None
    elif not v["format_ok"]: add("R1", "HARD", "GSTIN format invalid")
    elif not v["checksum_ok"]: add("R2", "HARD", "GSTIN checksum invalid - possible typo or tampering", "Check the GSTIN on your certificate")
    if not gst_unreadable and v.get("state") and v["state"] not in g["address"]: add("R3", "HARD", "GSTIN state code differs from address state")
    if not gst_unreadable and v["format_ok"] and r is None: add("R4", "HARD", "GSTIN not found in GST registry")
    if r:
        if r["status"] != "Active": add("R5", "HARD", f"GSTIN status is {r['status']}", "GST-dependent products cannot be activated")
        m = match_legal_name(g["legal_name"], r["legal_name"])
        if m["band"] != "PASS": add("R6", "HARD" if m["band"] == "FAIL" else "REVIEW", f"legal name vs registry {m['score']} ({m['band']})")
        if match_name(g["address"], r["principal_place_of_business"])["score"] < PASS: add("R7", "REVIEW", "address differs from registry")
    owner, biz = split_prop(g["legal_name"])
    if biz and not gst_unreadable and match_name(biz, g["trade_name"])["band"] != "PASS":
        add("R10", "HARD", f"certificate internally inconsistent: '{biz}' vs trade name '{g['trade_name']}'")
    u = app.get("udyam")
    if u is None:
        if lead and lead.get("udyam_number"): add("R11", "REVIEW", "Udyam certificate missing although a registration exists", "Upload Udyam certificate or confirm registry prefill")
    elif not u.get("udyam_number"):
        add("R12", "HARD" if (lead and lead.get("has_udyam") == "N") else "REVIEW", "Udyam certificate has no registration number")
    else:
        uv = validate_udyam(u["udyam_number"]); ur = reg.udyam.get(uv["udyam"])
        if not uv["format_ok"]: add("R13", "HARD", "Udyam number format invalid")
        elif uv["state"] != u["state"]: add("R14", "HARD", "Udyam state code differs from certificate state")
        if ur is None: add("R15", "HARD", "Udyam number not in registry")
        else:
            if match_name(u["enterprise_name"], ur["enterprise_name"])["band"] != "PASS": add("R16", "REVIEW", "Udyam name differs from registry")
            if ur["city"] != u["city"]: add("R17", "REVIEW", "Udyam city differs from registry")
            if u.get("date_of_registration") != ur["date_of_registration"]: add("R18", "INFO", "Udyam date differs from registry (systemic in mock data)")
        if match_name(u["enterprise_name"], g["trade_name"])["band"] != "PASS": add("R20", "REVIEW", "Udyam name differs from GST trade name")
    s = app["sig"]
    if dt.date.fromisoformat(s["valid_till"]) < AS_OF: add("R22", "HARD", "signatory ID expired", "Upload a valid ID")
    if match_name(s["business"], g["trade_name"])["band"] != "PASS": add("R23", "REVIEW", "signatory ID business name mismatch")
    if g["constitution"] == "Proprietorship":
        if match_name(s["name"], owner or "", "person")["band"] != "PASS": add("R24", "HARD", "signatory is not the proprietor")
    elif lead and match_name(s["name"], lead["contact_name"], "person")["band"] != "PASS":
        add("R25", "REVIEW", "signatory is not the known representative", "Upload board resolution / LLP authorisation letter")
    b = app["bill"]; age = (AS_OF - dt.date.fromisoformat(b["bill_date"])).days
    if age > MAX_ADDR_PROOF_DAYS: add("R27", "HARD", f"address proof is {age} days old (max {MAX_ADDR_PROOF_DAYS})", "Upload a bill from the last 90 days")
    if age < 0: add("R27b", "HARD", "address proof is future-dated")
    if match_name(b["billed_to"], g["trade_name"])["band"] != "PASS": add("R28", "REVIEW", "bill name differs from GST trade name")
    if match_name(b["address"], g["address"])["score"] < PASS: add("R29", "REVIEW", "bill address differs from GST address")
    worst = max((SEV[x.severity] for x in f), default=0)
    verdict = {3: "REJECT", 2: "REVIEW", 1: "PASS", 0: "PASS"}[worst]
    return {"verdict": verdict, "findings": [x.__dict__ for x in f], "mode": MODE,
            "relaxed_rules": sorted(set(v.get("relaxed_rules", []))), "as_of": AS_OF.isoformat()}

if __name__ == "__main__":
    import sys
    reg = Registry(sys.argv[1], sys.argv[2])
    ok = sum(validate_gstin(x)["checksum_ok"] for x in reg.gst); print("registry checksums ok:", ok, "/", len(reg.gst))
    print("K06 printed:", validate_gstin("08YKZXS8189L1Z0"))
    print("K07 legal:", match_name("Neha Banerjee (Prop. Shri Physio Clinic)", "Neha Banerjee (Prop. Neelgiri Physio Clinic)"))
    print("K07 internal:", match_name("Shri Physio Clinic", "Neelgiri Physio Clinic"))
    print("Unity/Trinity:", match_name("Unity Bake House Pvt Ltd", "Trinity Bake House Pvt Ltd"))
    print("M/s variant:", match_name("M/s Trinity Bake House Private Limited", "Trinity Bake House Pvt Ltd"))
    print("typo:", match_name("Star Electronic", "Star Electronics"))
    print("person:", match_name("Shri Joseph Rao", "Joseph Rao", "person"))
    print("udyam KR:", validate_udyam(next(k for k in reg.udyam if "-KR-" in k)))
    print("K01 status:", reg.gst["37IHKXV5167L1ZS"]["status"])
