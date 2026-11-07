import re, unicodedata
from difflib import SequenceMatcher

CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STATE_CODES = {"01":"Jammu and Kashmir","02":"Himachal Pradesh","03":"Punjab","04":"Chandigarh","05":"Uttarakhand",
 "06":"Haryana","07":"Delhi","08":"Rajasthan","09":"Uttar Pradesh","10":"Bihar","19":"West Bengal","21":"Odisha",
 "23":"Madhya Pradesh","24":"Gujarat","27":"Maharashtra","29":"Karnataka","30":"Goa","32":"Kerala","33":"Tamil Nadu",
 "36":"Telangana","37":"Andhra Pradesh"}
UDYAM_STATE = {"MH":"Maharashtra","KA":"Karnataka","KR":"Karnataka","GJ":"Gujarat","TN":"Tamil Nadu","DL":"Delhi","MP":"Madhya Pradesh",
 "TS":"Telangana","TG":"Telangana","WB":"West Bengal","KL":"Kerala","PB":"Punjab","UP":"Uttar Pradesh","RJ":"Rajasthan",
 "BR":"Bihar","AP":"Andhra Pradesh"}
GSTIN_RE = re.compile(r"^(\d{2})([A-Z]{5}\d{4}[A-Z])([1-9A-Z])Z([0-9A-Z])$")
PAN_RE   = re.compile(r"^[A-Z]{3}[ABCFGHLJPTX][A-Z]\d{4}[A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")

def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = CHARSET.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return CHARSET[(36 - total % 36) % 36]

def validate_gstin(g: str) -> dict:
    g = (g or "").strip().upper()
    out = {"gstin": g, "format_ok": False, "checksum_ok": False, "state_code": None, "state": None, "pan": None}
    m = GSTIN_RE.match(g)
    if not m: return out
    out.update(format_ok=True, state_code=m.group(1), state=STATE_CODES.get(m.group(1)), pan=m.group(2),
               pan_format_ok=bool(PAN_RE.match(m.group(2))), entity_no=m.group(3))
    out["expected_check"] = gstin_check_char(g[:14])
    out["checksum_ok"] = out["expected_check"] == g[14]
    return out

def validate_udyam(u: str) -> dict:
    u = (u or "").strip().upper()
    m = UDYAM_RE.match(u)
    if not m: return {"udyam": u, "format_ok": False}
    return {"udyam": u, "format_ok": True, "state_code": m.group(1), "state": UDYAM_STATE.get(m.group(1)),
            "district": m.group(2), "district_is_00": m.group(2) == "00"}

HONORIFICS = r"\b(m/s|messrs|mr|mrs|ms|miss|dr|shri|sri|smt|kumari|prop|proprietor)\b\.?"
SUFFIX_MAP = [(r"\bprivate\s+limited\b", "pvt ltd"), (r"\bpvt\.?\s*ltd\.?\b", "pvt ltd"), (r"\bp\.?\s*ltd\b", "pvt ltd"),
              (r"\blimited\b", "ltd"), (r"\blimited liability partnership\b", "llp"), (r"\bl\.l\.p\.?\b", "llp"),
              (r"\bcompany\b", "co"), (r"\band\b", "&")]
def normalise_name(s: str, drop_legal_suffix=False) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"\(.*?\)", lambda m: " " + m.group(0)[1:-1] + " ", s)
    for pat, rep in SUFFIX_MAP: s = re.sub(pat, rep, s)
    s = re.sub(HONORIFICS, " ", s)
    s = s.replace("&", " and ")
    if drop_legal_suffix: s = re.sub(r"\b(pvt ltd|ltd|llp|co)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]

def name_similarity(a: str, b: str, drop_legal_suffix=False) -> dict:
    na, nb = normalise_name(a, drop_legal_suffix), normalise_name(b, drop_legal_suffix)
    if not na and not nb: return {"lev": 1.0, "difflib": 1.0, "token_set": 1.0, "score": 1.0}
    lev = 1 - levenshtein(na, nb) / max(len(na), len(nb))
    dl = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    ts = len(ta & tb) / len(ta | tb) if ta | tb else 1.0
    return {"a": na, "b": nb, "lev": round(lev, 3), "difflib": round(dl, 3), "token_set": round(ts, 3),
            "score": round(max(lev, dl), 3)}

def split_prop_name(legal_name: str):
    """'Neha Kaur (Prop."""
    m = re.match(r"^(.*?)\s*\(\s*Prop\.?\s*(.*?)\)\s*$", legal_name or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)

def name_band(score: float) -> str:
    return "PASS" if score >= 0.90 else ("REVIEW" if score >= 0.75 else "FAIL")
