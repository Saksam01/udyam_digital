from __future__ import annotations
import os, re, shutil, subprocess, tempfile, difflib
from concurrent.futures import ThreadPoolExecutor
from datetime import date

try:
    import cv2
    import numpy as np
    _CV2 = True
except Exception:
    _CV2 = False

from udyam.gstin_repair import repair as repair_gstin

BLUR_MIN = 100
NORMAL_WIDTH = 1240

FIELDS = {
    "gst": [("gstin", "gstin"), ("legal_name", "legal name"), ("trade_name", "trade name"), ("constitution", "constitution"),
            ("address", "address of principal"), ("date_of_liability", "date of liability"), ("type", "type of registration")],
    "udyam": [("udyam_number", "udyam reg number"), ("enterprise_name", "enterprise name"), ("major_activity", "major activity"),
              ("city", "city"), ("state", "state"), ("date_of_registration", "date of registration")],
    "bill": [("consumer_no", "consumer no"), ("billed_to", "billed to"), ("address", "supply address"), ("bill_date", "bill date"),
             ("units", "units consumed"), ("amount", "amount due inr")],
    "sig": [("name", "name"), ("designation", "designation"), ("business", "for business"), ("id_no", "id no"), ("valid_till", "valid till")],
}
WRAP = {"gst": {"address"}, "bill": {"address"}}
STRIP_FRAGMENTS = ("place of business",)
NOISE = re.compile(r"specimen|synthetic|valid document|hackathon|fictional|test data", re.I)
TITLES = {"gst": ("gst registration", "gst certificate", "goods and services tax"),
          "udyam": ("udyam registration", "udyam certificate", "msme"),
          "sig": ("signatory", "authorised signatory", "authorized signatory"),
          "bill": ("electricity bill", "utility bill", "water bill", "bill", "consumer no")}
DOC_SLOT = {"gst": "gst_certificate", "udyam": "udyam_certificate", "sig": "signatory_id", "bill": "address_proof"}
DOC_NAME = {"gst": "GST certificate", "udyam": "Udyam certificate", "sig": "signatory ID", "bill": "address proof"}
REQUIRED = ("gst", "sig", "bill")


def _tess() -> str | None:
    cmd = os.getenv("TESSERACT_CMD")
    if cmd and os.path.exists(cmd):
        return cmd
    found = shutil.which("tesseract")
    if found:
        return found
    for base in (os.getenv("ProgramFiles"), os.getenv("ProgramFiles(x86)"), os.getenv("LOCALAPPDATA")):
        if base:
            for sub in ("Tesseract-OCR", os.path.join("Programs", "Tesseract-OCR")):
                path = os.path.join(base, sub, "tesseract.exe")
                if os.path.exists(path):
                    return path
    return None


def available() -> bool:
    return bool(_CV2 and _tess())


def _decode(data: bytes):
    if not _CV2:
        return None
    if data[:4] == b"%PDF":
        try:
            import fitz
            doc = fitz.open(stream=data, filetype="pdf")
            pix = doc[0].get_pixmap(dpi=200)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR if pix.n == 3 else cv2.COLOR_RGBA2BGR)
        except Exception:
            return None
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return img


def _resize(bgr):
    h, w = bgr.shape[:2]
    if w == NORMAL_WIDTH:
        return bgr
    scale = NORMAL_WIDTH / w
    return cv2.resize(bgr, (NORMAL_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)


def quality(gray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _remove_watermark(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    out = bgr.copy()
    out[(hsv[..., 1] > 40) & (hsv[..., 2] > 120)] = 255
    gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    return cv2.divide(gray, cv2.GaussianBlur(gray, (0, 0), 30), scale=255)


def _skew(gray) -> float:
    lines = cv2.HoughLinesP(cv2.Canny(gray, 50, 150), 1, np.pi / 720, 150, minLineLength=300, maxLineGap=10)
    angs = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in (lines.reshape(-1, 4) if lines is not None else [])]
    near = [a for a in angs if abs(a) < 15]
    return float(np.median(near)) if near else 0.0


def _best_angle(gray) -> float:
    h, w = gray.shape
    scale = 600.0 / w
    small = cv2.resize(gray, (600, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    ink = (small < 170).astype(np.float32)
    if ink.sum() < 50:
        return 0.0

    def score(a):
        M = cv2.getRotationMatrix2D((ink.shape[1] / 2, ink.shape[0] / 2), a, 1.0)
        r = cv2.warpAffine(ink, M, (ink.shape[1], ink.shape[0]))
        prof = r.sum(axis=1)
        return float(((prof[1:] - prof[:-1]) ** 2).sum())

    coarse = max(np.arange(-15, 15.01, 1.0), key=score)
    fine = max(np.arange(coarse - 1, coarse + 1.01, 0.25), key=score)
    return float(fine)


def _rotate(gray, deg: float):
    if abs(deg) < 0.05:
        return gray
    if deg in (90, 180, 270):
        return np.ascontiguousarray(np.rot90(gray, k={90: 1, 180: 2, 270: 3}[int(deg)]))
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(gray, M, (w, h), borderValue=255)


def _tesseract(gray, psm: int = 6) -> str:
    return _tesseract_lines(gray, psm)[0]


def _tesseract_lines(gray, psm: int = 6) -> tuple[str, list[dict]]:
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        cv2.imwrite(path, gray)
        out = subprocess.run([_tess() or "tesseract", path, "-", "-l", "eng", "--psm", str(psm), "tsv"],
                             capture_output=True, text=True, timeout=60).stdout
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    groups: dict[tuple, dict] = {}
    order: list[tuple] = []
    for row in out.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5":
            continue
        word = c[11].strip()
        if not word:
            continue
        key = (c[2], c[3], c[4])
        x, y, w, h = int(c[6]), int(c[7]), int(c[8]), int(c[9])
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"words": [], "boxes": []}
            order.append(key)
        g["words"].append(word)
        g["boxes"].append([x, y, w, h])
    lines = []
    for key in order:
        g = groups[key]
        xs = [b[0] for b in g["boxes"]]; ys = [b[1] for b in g["boxes"]]
        x2 = [b[0] + b[2] for b in g["boxes"]]; y2 = [b[1] + b[3] for b in g["boxes"]]
        lines.append({"text": " ".join(g["words"]), "box": [min(xs), min(ys), max(x2) - min(xs), max(y2) - min(ys)],
                      "words": list(zip(g["words"], g["boxes"]))})
    return "\n".join(l["text"] for l in lines), lines


AADHAAR = re.compile(r"(?<!\d)(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
PAN = re.compile(r"\b([A-Z]{2})([A-Z]{3}\d{4})([A-Z])\b")


def mask_ids(text: str | None) -> str | None:
    if not text:
        return text
    text = AADHAAR.sub(lambda m: f"XXXX XXXX {m.group(3)}", text)
    return PAN.sub(lambda m: f"{m.group(1)}XXXXXXX{m.group(3)}", text)


def redact_image(gray, lines: list[dict]):
    out = gray.copy()
    hits = 0
    for ln in lines:
        words = ln.get("words", [])
        digits = [(i, w, b) for i, (w, b) in enumerate(words) if re.fullmatch(r"\d{4}|\d{8}|\d{12}", re.sub(r"\D", "", w) or "x")]
        joined = "".join(re.sub(r"\D", "", w) for _, w, _ in digits)
        if not AADHAAR.search(" ".join(w for _, w, _ in digits)) and len(joined) < 12:
            continue
        need = 8
        for _, w, (x, y, bw, bh) in digits:
            d = len(re.sub(r"\D", "", w))
            if need <= 0:
                break
            frac = min(1.0, need / max(d, 1))
            cv2.rectangle(out, (x - 2, y - 2), (x + int(bw * frac) + 2, y + bh + 2), 0, -1)
            need -= d
            hits += 1
    return out, hits


def _words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def _label_hit(line: str, spec: list) -> tuple[str, str] | None:
    raw_words = line.split()
    best = None
    for field, label in spec:
        n = len(label.split())
        if len(raw_words) < n:
            continue
        head = " ".join(_words(" ".join(raw_words[:n])))
        r = difflib.SequenceMatcher(None, head, label).ratio()
        if r >= 0.82 and (best is None or r > best[0]):
            best = (r, field, " ".join(raw_words[n:]))
    return (best[1], best[2]) if best else None


_VOCAB: set | None = None


def _vocab() -> set:
    global _VOCAB
    if _VOCAB is None:
        words = set()
        try:
            from udyam import data_loader
            for r in data_loader.registry().gst.values():
                words.update(w.lower() for w in re.findall(r"[A-Za-z]+", r.get("principal_place_of_business", "")))
            words.update(w.lower() for c in data_loader.city_tiers() for w in c.split())
        except Exception:
            pass
        _VOCAB = words
    return _VOCAB


def _join(prev: str, nxt: str) -> str:
    if not prev:
        return nxt
    last = re.sub(r"[^A-Za-z0-9]", "", prev.split()[-1])
    first_tok = nxt.split()[0] if nxt.split() else ""
    first = re.match(r"[A-Za-z]+", first_tok)
    first = first.group(0) if first else ""
    glued = False
    if re.search(r"\d$", prev) and re.match(r"\d", nxt) and len(prev.split()[-1]) < 6:
        glued = True
    elif first and last.isalpha():
        joined = (last + first).lower()
        if joined in _vocab() and last.lower() not in _vocab():
            glued = True
        elif joined in _vocab() and first.lower() not in _vocab():
            glued = True
        elif nxt[:1].islower() and last.lower() not in _vocab() and len(prev) >= 40:
            glued = True
    out = prev + nxt if glued else prev + " " + nxt
    return re.sub(r"\s*-\s*(?=\d{6}\b)", " - ", out).strip()


def label_score(text: str) -> int:
    n = 0
    for spec in FIELDS.values():
        for line in text.splitlines():
            if _label_hit(line.strip(), spec):
                n += 1
    return n


def classify(text: str) -> str | None:
    head = " ".join(text.lower().split("\n")[:6])
    for t, keys in TITLES.items():
        if t == "bill":
            continue
        if any(k in head for k in keys):
            return t
    if any(k in head for k in TITLES["bill"]):
        return "bill"
    scores = {t: sum(1 for ln in text.splitlines() if _label_hit(ln.strip(), spec)) for t, spec in FIELDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else None


def read_image(data: bytes) -> dict:
    """OCR one upload."""
    bgr = _decode(data)
    if bgr is None:
        return {"ok": False, "reason": "unreadable_file"}
    bgr = _resize(bgr)
    q = quality(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    clean = _remove_watermark(bgr)
    est = _best_angle(clean)
    angles = [0.0] if abs(est) < 0.3 else [est, 0.0]
    angles += [a for a in (90, 270, 180) if a not in angles]
    best = {"text": "", "score": -1, "angle": 0.0, "lines": [], "img": clean}
    for ang in angles:
        img = _rotate(clean, ang)
        txt, lines = _tesseract_lines(img)
        sc = label_score(txt)
        if sc > best["score"]:
            best = {"text": txt, "score": sc, "angle": ang, "lines": lines, "img": img}
        if sc >= 3:
            break
    return {"ok": True, "text": best["text"], "angle": best["angle"], "quality": q, "label_score": best["score"],
            "lines": best["lines"], "image": best["img"]}


def _date(s: str | None) -> str | None:
    if not s:
        return None
    t = s.upper().replace("O", "0").replace("I", "1").replace("L", "1")
    m = re.search(r"(\d{4})\D?(\d{2})\D?(\d{2})", t)
    if not m:
        m2 = re.search(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", t)
        if m2:
            y, mo, d = m2.group(3), m2.group(2), m2.group(1)
        else:
            return None
    else:
        y, mo, d = m.groups()
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return None


def _udyam_no(s: str | None) -> str:
    if not s:
        return ""
    m = re.search(r"UDYAM[\s-]*([A-Z]{2})[\s-]*(\d{2})[\s-]*(\d{7})", s.upper().replace("O", "0") if False else s.upper())
    return f"UDYAM-{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def _repair_gstin_any(cand: str, registry_keys):
    from udyam.kyc_rules import validate_gstin
    raw = re.sub(r"[^0-9A-Z]", "", cand.upper())
    fixed, edits = repair_gstin(raw, registry_keys)
    if edits is not None:
        return fixed, edits
    tries = []
    if len(raw) == 16:
        tries = [raw[:i] + raw[i + 1:] for i in range(16)]
    elif len(raw) == 14:
        tries = [raw[:i] + c + raw[i:] for i in range(15) for c in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    hits = [t for t in tries if validate_gstin(t)["checksum_ok"] and (registry_keys is None or t in registry_keys)]
    if len(hits) >= 1:
        return hits[0], 1
    return fixed, None


def parse(doctype: str, text: str, registry_keys=None, lines: list[dict] | None = None) -> dict:
    spec = FIELDS[doctype]
    values: dict[str, str] = {}
    where: dict[str, list[int]] = {}
    current = None
    extra = 0
    for idx, line in enumerate(ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        hit = _label_hit(line, spec)
        if hit:
            current, rest = hit
            for frag in STRIP_FRAGMENTS:
                rest = re.sub(frag, "", rest, flags=re.I).strip() if doctype in WRAP and current in WRAP[doctype] else rest
            values[current] = rest.strip()
            where[current] = [idx]
            extra = 0
            continue
        if current is None or NOISE.search(line):
            continue
        for frag in STRIP_FRAGMENTS:
            if line.lower().startswith(frag):
                line = line[len(frag):].strip()
        wrap = doctype in WRAP and current in WRAP[doctype]
        if (wrap and extra < 2) or not values.get(current):
            values[current] = _join(values.get(current, ""), line)
            where.setdefault(current, []).append(idx)
            extra += 1
    out = {k: v.strip(" |_") for k, v in values.items()}
    if lines:
        boxes = {}
        for k, idxs in where.items():
            bs = [lines[i]["box"] for i in idxs if i < len(lines)]
            if bs:
                x1 = min(b[0] for b in bs); y1 = min(b[1] for b in bs)
                boxes[k] = [x1, y1, max(b[0] + b[2] for b in bs) - x1, max(b[1] + b[3] for b in bs) - y1]
        out["_boxes"] = boxes
    if doctype == "gst":
        raw = out.get("gstin", "") or ""
        m = re.search(r"[0-9A-Z]{2}[0-9A-Z ]{12,16}", raw.upper())
        cand = m.group(0) if m else raw
        if not re.fullmatch(r"[0-9A-Z]{15}", re.sub(r"\s", "", cand.upper())):
            m = re.search(r"\b\d{2}[A-Z0-9]{13}\b", text.upper())
            cand = m.group(0) if m else cand
        fixed, edits = _repair_gstin_any(cand, registry_keys) if cand else ("", None)
        out["gstin_read"] = re.sub(r"\s", "", cand.upper()) if cand else ""
        out["gstin"] = fixed
        out["gstin_repaired"] = bool(edits)
        out["date_of_liability"] = _date(out.get("date_of_liability")) or ""
    elif doctype == "udyam":
        out["udyam_number"] = _udyam_no(out.get("udyam_number") or "") or _udyam_no(text)
        out["date_of_registration"] = _date(out.get("date_of_registration")) or ""
    elif doctype == "bill":
        out["bill_date"] = _date(out.get("bill_date")) or ""
        out["consumer_no"] = re.sub(r"\D", "", out.get("consumer_no", ""))
    elif doctype == "sig":
        out["valid_till"] = _date(out.get("valid_till")) or ""
    return out


def required_fields(doctype: str) -> list[str]:
    return {"gst": ["gstin", "legal_name", "trade_name", "address"], "udyam": ["enterprise_name"],
            "sig": ["name", "business", "valid_till"], "bill": ["billed_to", "address", "bill_date"]}[doctype]


def process_one(data: bytes, registry_keys=None) -> dict:
    """OCR plus parsing for a single upload."""
    r = read_image(data)
    if not r.get("ok"):
        return {"ok": False, "reason": r.get("reason", "unreadable_file")}
    doctype = classify(r["text"])
    if not doctype:
        return {"ok": False, "reason": "unrecognised", "quality": r["quality"]}
    fields = parse(doctype, r["text"], registry_keys, r["lines"])
    boxes = fields.pop("_boxes", {})
    masked = 0
    for k in list(fields):
        if k in ("gstin", "gstin_read", "udyam_number") or not isinstance(fields[k], str):
            continue
        m = mask_ids(fields[k])
        if m != fields[k]:
            fields[k] = m
            masked += 1
    img, hits = redact_image(r["image"], r["lines"])
    ok, png = cv2.imencode(".png", img)
    return {"ok": True, "doctype": doctype, "fields": fields, "quality": r["quality"], "boxes": boxes,
            "page": png.tobytes() if ok else None, "page_size": [int(img.shape[1]), int(img.shape[0])],
            "masked": {"fields": masked, "image_regions": hits}}


def process_many(files: dict[str, bytes], registry_keys=None) -> dict:
    """files: slot name -> bytes."""
    docs, problems = {}, []
    with ThreadPoolExecutor(max_workers=max(1, int(os.getenv("OCR_WORKERS", "4")))) as ex:
        futs = {slot: ex.submit(process_one, data, registry_keys) for slot, data in files.items() if data}
        results = {slot: f.result() for slot, f in futs.items()}
    for slot, res in results.items():
        if not res.get("ok"):
            problems.append({"slot": slot, "reason": res.get("reason"), "quality": res.get("quality")})
            continue
        dt = res["doctype"]
        if dt in docs and docs[dt]["quality"] >= res["quality"]:
            continue
        docs[dt] = {**res, "slot": slot}
    return {"docs": docs, "problems": problems}
