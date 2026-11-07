from __future__ import annotations
import csv, os, re, unicodedata, datetime as dt
from dataclasses import dataclass
from difflib import SequenceMatcher

MODE = os.getenv("ID_VALIDATION_MODE", "production")
if os.getenv("APP_ENV") == "production" and MODE == "mock":
    raise RuntimeError("ID_VALIDATION_MODE=mock is not allowed in production")
AS_OF = dt.date.fromisoformat(os.getenv("AS_OF_DATE", "2026-07-15"))
MAX_ADDR_PROOF_DAYS, BLUR_MIN = 90, 100
# name match bands: >= PASS ok, REVIEW..PASS goes to a person, below that fails
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
            "entity_type": "ALT_SERIES" if pan4 == "X" else pan4, "checksum_ok": gstin_check_char(g[:14]) == g[14],
            "relaxed_rules": ["pan_4th_char_X"] if pan4 == "X" else []}

def validate_udyam(raw: str) -> dict:
    u = (raw or "").strip().upper(); m = UDYAM_RE.match(u)
    if not m: return {"udyam": u, "format_ok": False}
    st, dist = m.group(1), m.group(2)
    state = UDYAM_STATE.get(st) or RULES["state_alias"].get(st)
    ok = state is not None and (dist != "00" or RULES["district_00_ok"])
    return {"udyam": u, "format_ok": ok, "state": state,
            "relaxed_rules": [r for r, c in (("district_00", dist == "00"), ("state_KR", st == "KR")) if c]}

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

def token_sort(a: str, b: str) -> float:
    return SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio()

def token_set(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    common = " ".join(sorted(ta & tb))
    ra, rb = (common + " " + " ".join(sorted(ta - tb))).strip(), (common + " " + " ".join(sorted(tb - ta))).strip()
    if not common:
        return SequenceMatcher(None, ra, rb).ratio()
    return max(SequenceMatcher(None, common, ra).ratio(), SequenceMatcher(None, common, rb).ratio(), SequenceMatcher(None, ra, rb).ratio())

def similarity(a: str, b: str) -> float:
    lev = 1 - levenshtein(a, b) / max(len(a), len(b), 1)
    return round(max(lev, SequenceMatcher(None, a, b).ratio(), token_sort(a, b)), 3)

def distinctive(s): return next((t for t in s.split() if t not in GENERIC), "")

def match_name(a: str, b: str, kind: str = "business") -> dict:
    na, nb = (norm_person(a), norm_person(b)) if kind == "person" else (norm_business(a), norm_business(b))
    score = similarity(na, nb); tok_ok = distinctive(na) == distinctive(nb)
    band = "PASS" if score >= PASS and tok_ok else ("REVIEW" if score >= REVIEW else "FAIL")
    return {"score": score, "distinctive_token_match": tok_ok, "band": band}

def match_legal_name(a: str, b: str) -> dict:
    """Proprietorship legal names 'Owner (Prop."""
    (pa, ba), (pb, bb) = split_prop(a), split_prop(b)
    if not (ba and bb): return match_name(a, b)
    mp, mb = match_name(pa, pb, "person"), match_name(ba, bb)
    worst = min((mp, mb), key=lambda m: ["FAIL", "REVIEW", "PASS"].index(m["band"]))
    return {**worst, "person": mp, "business": mb}

def split_prop(legal_name):
    m = re.match(r"^(.*?)\s*\(\s*Prop\.?\s*(.*?)\)\s*$", legal_name or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)

class Registry:
    def __init__(self, gst_csv, udyam_csv):
        self.gst = {r["gstin"]: r for r in csv.DictReader(open(gst_csv, encoding="utf-8"))}
        self.udyam = {r["udyam_number"]: r for r in csv.DictReader(open(udyam_csv, encoding="utf-8"))}

@dataclass
class Finding:
    code: str; severity: str; message: str; customer_action: str | None = None
    evidence: dict | None = None
SEV = {"HARD": 3, "REVIEW": 2, "INFO": 1}

SRC = {"gst": "GST certificate", "udyam": "Udyam certificate", "sig": "Signatory ID", "bill": "Address proof",
       "gst_reg": "GST registry", "udyam_reg": "Udyam registry", "declared": "Name typed in the app", "lead": "Contact on file"}


def match_declared(declared: str, names: list[str]) -> dict:
    """The name the owner typed vs every business name on the documents."""
    best = {"score": 0.0, "band": "FAIL", "against": None, "distinctive_token_match": False}
    nd = norm_business(declared, drop_suffix=True)
    for n in names:
        if not n:
            continue
        nn = norm_business(n, drop_suffix=True)
        tok = distinctive(nd) == distinctive(nn)
        score = round(max(similarity(nd, nn), token_set(nd, nn) if tok else 0.0), 3)
        band = "PASS" if score >= PASS and tok else ("REVIEW" if score >= REVIEW else "FAIL")
        if best["against"] is None or score > best["score"]:
            best = {"score": score, "band": band, "against": n, "distinctive_token_match": tok}
    return best


def assess(app: dict, reg: Registry, lead: dict | None = None) -> dict:
    f: list[Finding] = []
    trace: list[dict] = []

    def ev(doc, field, extracted, ref_src, reference, m=None, threshold=PASS):
        return {"doc": doc, "field": field, "extracted": extracted, "reference_source": ref_src, "reference": reference,
                "score": (m or {}).get("score"), "threshold": threshold if m else None,
                "distinctive_token_match": (m or {}).get("distinctive_token_match")}

    def plain(doc, field, extracted, ref_src, reference):
        return {"doc": doc, "field": field, "extracted": extracted, "reference_source": ref_src, "reference": reference, "score": None, "threshold": None}

    def check(code, doc, label, ok, severity=None, message=None, action=None, evidence=None):
        res = "pass" if ok else {"REVIEW": "review", "INFO": "info"}.get(severity, "fail")
        trace.append({"code": code, "doc": doc, "check": label, "result": res, **({"evidence": evidence} if evidence else {})})
        if not ok:
            f.append(Finding(code, severity, message or label, action, evidence))

    for doc, lv in app.get("quality", {}).items():
        nice = {"gst_certificate": "GST certificate", "udyam_certificate": "Udyam certificate", "signatory_id": "Signatory ID",
                "address_proof": "Address proof"}.get(doc, doc.replace("_", " ").capitalize())
        check("R0", doc, f"{nice} is sharp enough to read", lv >= BLUR_MIN, "REVIEW",
              f"{doc} too blurred (LapVar {lv:.0f})", f"Please re-take the photo of your {doc.replace('_', ' ')}",
              plain(doc, "sharpness", round(lv), "minimum sharpness", BLUR_MIN))
    g = app["gst"]; v = validate_gstin(g["gstin"]); r = reg.gst.get(v["gstin"])
    gst_unreadable = app.get("quality", {}).get("gst_certificate", BLUR_MIN) < BLUR_MIN
    if gst_unreadable:
        check("R1", "gst", "GSTIN is legible", False, "REVIEW", "GSTIN not legible - identifier checks deferred", "Re-upload GST certificate"); r = None
    else:
        gev = plain("gst", "GSTIN", v["gstin"], "GSTIN format", "15 characters with a PAN inside")
        check("R1", "gst", "GSTIN format is valid", v["format_ok"], "HARD", "GSTIN format invalid", None, gev)
        if v["format_ok"]:
            check("R2", "gst", "GSTIN check digit is correct", v["checksum_ok"], "HARD", "GSTIN checksum invalid - possible typo or tampering",
                  "Check the GSTIN on your certificate", {**gev, "reference_source": "mod-36 check digit", "reference": v["gstin"][:14] + gstin_check_char(v["gstin"][:14])})
        if v.get("state"):
            check("R3", "gst", "GSTIN state code matches the address", v["state"] in g["address"], "HARD", "GSTIN state code differs from address state", None,
                  plain("gst", "state", g["address"], f"GSTIN state code {v['gstin'][:2]}", v["state"]))
        if v["format_ok"]:
            check("R4", "gst", "GSTIN exists in the GST registry", r is not None, "HARD", "GSTIN not found in GST registry", None,
                  plain("gst", "GSTIN", v["gstin"], SRC["gst_reg"], v["gstin"] if r else "no record"))
    if r:
        check("R5", "gst", "GSTIN is Active in the registry", r["status"] == "Active", "HARD", f"GSTIN status is {r['status']}",
              "GST-dependent products cannot be activated", plain("gst", "registration status", "Active (required)", SRC["gst_reg"], r["status"]))
        m = match_legal_name(g["legal_name"], r["legal_name"])
        check("R6", "gst", "Legal name matches the GST registry", m["band"] == "PASS", "HARD" if m["band"] == "FAIL" else "REVIEW",
              f"legal name vs registry {m['score']} ({m['band']})", None, ev("gst", "legal name", g["legal_name"], SRC["gst_reg"], r["legal_name"], m))
        ma = match_name(g["address"], r["principal_place_of_business"])
        check("R7", "gst", "Address matches the GST registry", ma["score"] >= PASS, "REVIEW", "address differs from registry", None,
              ev("gst", "address", g["address"], SRC["gst_reg"], r["principal_place_of_business"], ma))
    owner, biz = split_prop(g["legal_name"])
    if biz and not gst_unreadable:
        m = match_name(biz, g["trade_name"])
        check("R10", "gst", "Business in the legal name matches the trade name", m["band"] == "PASS", "HARD",
              f"certificate internally inconsistent: '{biz}' vs trade name '{g['trade_name']}'", None,
              ev("gst", "legal name (business part)", biz, "GST certificate trade name", g["trade_name"], m))
    declared = (app.get("declared") or "").strip()
    if declared and not gst_unreadable:
        names = [g.get("trade_name"), biz, (app.get("udyam") or {}).get("enterprise_name")]
        m = match_declared(declared, [n for n in names if n])
        check("R31", "gst", "Documents belong to the business named in the app", m["band"] == "PASS", "HARD" if m["band"] == "FAIL" else "REVIEW",
              f"documents are for '{m['against']}', not '{declared}' ({m['score']})", "Upload the documents of the business you named, or correct the name",
              ev("gst", "business name", m["against"] or g.get("trade_name"), SRC["declared"], declared, m))
    u = app.get("udyam")
    if u is None:
        if lead and lead.get("udyam_number"):
            check("R11", "udyam", "Udyam certificate provided", False, "REVIEW", "Udyam certificate missing although a registration exists",
                  "Upload Udyam certificate or confirm registry prefill")
    elif not u.get("udyam_number"):
        check("R12", "udyam", "Udyam certificate shows a registration number", False, "HARD" if (lead and lead.get("has_udyam") == "N") else "REVIEW",
              "Udyam certificate has no registration number")
    else:
        uv = validate_udyam(u["udyam_number"]); ur = reg.udyam.get(uv["udyam"])
        uev = plain("udyam", "Udyam number", uv["udyam"], "Udyam format", "UDYAM-SS-DD-NNNNNNN")
        check("R13", "udyam", "Udyam number format is valid", uv["format_ok"], "HARD", "Udyam number format invalid", None, uev)
        if uv["format_ok"]:
            check("R14", "udyam", "Udyam state code matches the certificate", uv["state"] == u["state"], "HARD", "Udyam state code differs from certificate state", None,
                  plain("udyam", "state", u["state"], "Udyam number state code", uv["state"]))
        check("R15", "udyam", "Udyam number exists in the Udyam registry", ur is not None, "HARD", "Udyam number not in registry", None,
              plain("udyam", "Udyam number", uv["udyam"], SRC["udyam_reg"], uv["udyam"] if ur else "no record"))
        if ur:
            m = match_name(u["enterprise_name"], ur["enterprise_name"])
            check("R16", "udyam", "Enterprise name matches the Udyam registry", m["band"] == "PASS", "REVIEW", "Udyam name differs from registry", None,
                  ev("udyam", "enterprise name", u["enterprise_name"], SRC["udyam_reg"], ur["enterprise_name"], m))
            check("R17", "udyam", "City matches the Udyam registry", ur["city"] == u["city"], "REVIEW", "Udyam city differs from registry", None,
                  plain("udyam", "city", u["city"], SRC["udyam_reg"], ur["city"]))
            check("R18", "udyam", "Registration date matches the Udyam registry", u.get("date_of_registration") == ur["date_of_registration"], "INFO",
                  "Udyam registration date differs from the registry record", None,
                  plain("udyam", "date of registration", u.get("date_of_registration"), SRC["udyam_reg"], ur["date_of_registration"]))
        if not gst_unreadable:
            m = match_name(u["enterprise_name"], g["trade_name"])
            check("R20", "udyam", "Udyam name matches the GST trade name", m["band"] == "PASS", "REVIEW", "Udyam name differs from GST trade name", None,
                  ev("udyam", "enterprise name", u["enterprise_name"], SRC["gst"], g["trade_name"], m))
    s = app["sig"]
    check("R22", "sig", "Signatory ID is in date", dt.date.fromisoformat(s["valid_till"]) >= AS_OF, "HARD", "signatory ID expired", "Upload a valid ID",
          plain("sig", "valid till", s["valid_till"], "check date", AS_OF.isoformat()))
    if not gst_unreadable:
        m = match_name(s["business"], g["trade_name"])
        check("R23", "sig", "Signatory ID names the same business", m["band"] == "PASS", "REVIEW", "signatory ID business name mismatch", None,
              ev("sig", "for business", s["business"], SRC["gst"], g["trade_name"], m))
        if g.get("constitution") == "Proprietorship":
            m = match_name(s["name"], owner or "", "person")
            check("R24", "sig", "Signatory is the proprietor named on the GST certificate", m["band"] == "PASS", "HARD", "signatory is not the proprietor", None,
                  ev("sig", "signatory name", s["name"], "GST legal name (proprietor)", owner or "", m))
        elif lead:
            m = match_name(s["name"], lead["contact_name"], "person")
            check("R25", "sig", f"Signatory is the authorised representative of the {(g.get('constitution') or 'business').lower()}", m["band"] == "PASS", "REVIEW",
                  "signatory is not the known representative", "Upload board resolution / LLP authorisation letter",
                  ev("sig", "signatory name", s["name"], "Authorised contact on record", lead["contact_name"], m))
    b = app["bill"]; age = (AS_OF - dt.date.fromisoformat(b["bill_date"])).days
    bev = plain("bill", "bill date", b["bill_date"], "age on the check date", f"{age} days (max {MAX_ADDR_PROOF_DAYS})")
    check("R27", "bill", "Address proof is less than 90 days old", age <= MAX_ADDR_PROOF_DAYS, "HARD", f"address proof is {age} days old (max {MAX_ADDR_PROOF_DAYS})",
          "Upload a bill from the last 90 days", bev)
    if age < 0:
        check("R27b", "bill", "Address proof is not future-dated", False, "HARD", "address proof is future-dated", None, bev)
    if not gst_unreadable:
        m = match_name(b["billed_to"], g["trade_name"])
        check("R28", "bill", "Bill is in the business's name", m["band"] == "PASS", "REVIEW", "bill name differs from GST trade name", None,
              ev("bill", "billed to", b["billed_to"], SRC["gst"], g["trade_name"], m))
        ma = match_name(b["address"], g["address"])
        check("R29", "bill", "Bill address matches the GST address", ma["score"] >= PASS, "REVIEW", "bill address differs from GST address", None,
              ev("bill", "supply address", b["address"], SRC["gst"], g["address"], ma))
    worst = max((SEV[x.severity] for x in f), default=0)
    verdict = {3: "REJECT", 2: "REVIEW", 1: "PASS", 0: "PASS"}[worst]
    return {"verdict": verdict, "findings": [x.__dict__ for x in f], "trace": trace, "mode": MODE,
            "thresholds": {"pass": PASS, "review": REVIEW,
                           "method": "best of Levenshtein, SequenceMatcher and token-sort on normalised names; a pass also needs the distinctive word to agree"},
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
