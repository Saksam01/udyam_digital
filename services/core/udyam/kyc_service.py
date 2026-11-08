from __future__ import annotations
from datetime import date
from udyam import data_loader, kyc_engine, kyc_extract as KX, llm

FRIENDLY = {
    "R0": ("A photo is too blurry to read.", "Retake it in good light, holding the phone steady."),
    "R1": ("We could not read the GSTIN on your certificate.", "Upload a clearer photo of your GST certificate."),
    "R2": ("The GSTIN does not pass its built-in check, so a character may be wrong.", "Check the number against your certificate."),
    "R3": ("The GSTIN state does not match the address on the certificate.", None),
    "R4": ("We could not find this GSTIN in the GST registry.", "Check the number or upload your latest certificate."),
    "R5": ("Your GSTIN is not active in the GST registry.", "Services that need GST cannot be activated until it is active."),
    "R6": ("The business name on your certificate differs from the GST record.", None),
    "R7": ("The address on your certificate differs from the GST record.", None),
    "R10": ("Your certificate shows two different business names.", "Upload the correct certificate."),
    "R11": ("Your Udyam certificate is missing.", "Upload it, or continue and we will confirm from the registry."),
    "R12": ("Your Udyam certificate has no registration number.", "Upload the full certificate."),
    "R13": ("The Udyam number format looks wrong.", "Check the number on your certificate."),
    "R14": ("The Udyam number does not match the state on the certificate.", None),
    "R15": ("We could not find this Udyam number in the registry.", "Check the number or upload your latest certificate."),
    "R16": ("The Udyam enterprise name differs from the registry.", None),
    "R17": ("The city on your Udyam certificate differs from the registry.", None),
    "R20": ("The Udyam name differs from your GST trade name.", None),
    "R22": ("Your signatory ID has expired.", "Upload a valid ID."),
    "R23": ("The signatory ID names a different business.", None),
    "R24": ("The ID holder is not the proprietor on the GST certificate.", "Upload the proprietor's ID, or an authorisation letter."),
    "R25": ("The ID holder is not the representative we have on file.", "Upload an authorisation letter from the business."),
    "R27": ("Your address proof is older than 90 days.", "Upload a bill from the last 90 days."),
    "R27b": ("The address proof is dated in the future.", "Upload the correct bill."),
    "R28": ("The name on your bill differs from the business name.", None),
    "R29": ("The address on your bill differs from the certificate.", None),
    "R31": ("These documents are for a different business than the name you gave.", "Upload your own business's documents, or correct the business name."),
    "R32": ("Your address proof is for a different city than the one you chose.", "Upload an address proof for the premises where you want the services."),
}

CHECKS = [
    ("gstin", "GSTIN is valid and active", {"R1", "R2", "R3", "R4", "R5"}),
    ("business", "Business name matches across documents", {"R6", "R10", "R20", "R23", "R28", "R31"}),
    ("signatory", "Signatory is valid and authorised", {"R22", "R24", "R25"}),
    ("address", "Address proof is recent and matches", {"R7", "R27", "R27b", "R29", "R32"}),
    ("udyam", "Udyam registration matches", {"R11", "R12", "R13", "R14", "R15", "R16", "R17"}),
]
RANK = {"HARD": 3, "REVIEW": 2, "INFO": 1}


def friendly(findings: list[dict]) -> list[dict]:
    out = []
    for f in findings:
        if f["severity"] == "INFO":
            continue
        text, action = FRIENDLY.get(f["code"], (f["message"], f.get("customer_action")))
        if f["code"] == "R5":
            text = f["message"].replace("GSTIN status is", "Your GSTIN is") + " in the GST registry."
        out.append({"code": f["code"], "kind": "fix" if f["severity"] == "HARD" else "check", "text": text,
                    "action": action or f.get("customer_action")})
    return out


def checklist(findings: list[dict], has_udyam: bool) -> list[dict]:
    items = []
    for cid, label, codes in CHECKS:
        if cid == "udyam" and not has_udyam and not any(f["code"] in codes for f in findings):
            continue
        worst = max((RANK[f["severity"]] for f in findings if f["code"] in codes), default=0)
        items.append({"id": cid, "label": label, "state": "fail" if worst == 3 else ("check" if worst == 2 else "ok")})
    return items


def _summary(app: dict) -> dict:
    g = app.get("gst") or {}
    return {"business": g.get("trade_name") or None, "legal_name": g.get("legal_name") or None,
            "gstin": g.get("gstin") or None, "constitution": g.get("constitution") or None}


def _assemble(docs: dict, blurred: set[str]) -> dict:
    gst = docs.get("gst", {}).get("fields", {})
    g = {"gstin": gst.get("gstin", ""), "legal_name": gst.get("legal_name", ""), "trade_name": gst.get("trade_name", ""),
         "constitution": gst.get("constitution", ""), "address": gst.get("address", "")}
    ud = docs.get("udyam", {}).get("fields")
    u = None
    if ud is not None:
        u = {"udyam_number": ud.get("udyam_number", ""), "enterprise_name": ud.get("enterprise_name", ""), "city": ud.get("city", ""),
             "state": ud.get("state", ""), "date_of_registration": ud.get("date_of_registration", "")}
    sg = docs.get("sig", {}).get("fields", {})
    bl = docs.get("bill", {}).get("fields", {})
    quality = {KX.DOC_SLOT[t]: max(d["quality"], KX.BLUR_MIN) for t, d in docs.items()}
    for t in blurred:
        quality[KX.DOC_SLOT[t]] = 1.0
    return {"quality": quality, "gst": g, "udyam": u,
            "sig": {"name": sg.get("name", ""), "business": sg.get("business", ""), "valid_till": sg.get("valid_till") or "1970-01-01"},
            "bill": {"billed_to": bl.get("billed_to", ""), "address": bl.get("address", ""), "bill_date": bl.get("bill_date") or "1970-01-01"}}


def _vision_fallback(files: dict[str, bytes], docs: dict, problems: list) -> None:
    if not llm.available():
        return
    have = set(docs)
    for p in list(problems):
        slot = p["slot"]
        dt = next((t for t, s in KX.DOC_SLOT.items() if s == slot), None)
        if not dt or dt in have or p.get("blurred"):
            continue
        fields = llm.extract_document(files[slot], dt)
        if fields:
            docs[dt] = {"ok": True, "doctype": dt, "fields": fields, "quality": 1000.0, "slot": slot}
            problems.remove(p)


def verify_upload(files: dict[str, bytes], declared: str | None = None, place: dict | None = None) -> dict:
    """files: slot -> bytes."""
    reg = data_loader.registry()
    if not KX.available():
        docs, problems = {}, [{"slot": s, "reason": "no_reader"} for s in files]
        _vision_fallback(files, docs, problems)
        if not docs:
            return {"status": "unavailable", "message": "We cannot read documents at the moment. Please try again shortly, or ask your Accel partner to help."}
        out = {"docs": docs, "problems": problems}
    else:
        out = KX.process_many(files, set(reg.gst.keys()))
        docs, problems = out["docs"], out["problems"]
        _vision_fallback(files, docs, problems)

    blurred = set()
    for p in list(problems):
        dt = next((t for t, s in KX.DOC_SLOT.items() if s == p["slot"]), None)
        q = p.get("quality")
        if dt and p.get("reason") == "unrecognised" and q is not None and q < KX.BLUR_MIN and dt not in docs:
            blurred.add(dt)
            p["blurred"] = True
    for t, d in docs.items():
        miss = [f for f in KX.required_fields(t) if not (d["fields"].get(f) or "").strip()]
        if t == "gst" and not d["fields"].get("gstin"):
            miss = ["gstin"] if "gstin" not in miss else miss
        if miss:
            problems.append({"slot": KX.DOC_SLOT[t], "reason": "missing_fields", "fields": miss})

    needs = []
    for t in blurred - {"gst"}:
        needs.append({"doc": t, "slot": KX.DOC_SLOT[t], "kind": "blurry", "text": f"Your {KX.DOC_NAME[t]} is too blurry to read. Please retake it in good light, holding the phone steady."})
    sent_but_unread = {p["slot"] for p in problems}
    for t in KX.REQUIRED:
        if t not in docs and t not in blurred and KX.DOC_SLOT[t] not in sent_but_unread:
            needs.append({"doc": t, "slot": KX.DOC_SLOT[t], "kind": "missing", "text": f"Please upload your {KX.DOC_NAME[t]}."})
    for p in problems:
        if p.get("blurred"):
            continue
        t = next((t for t, s in KX.DOC_SLOT.items() if s == p["slot"]), None)
        if t and t in docs and p["reason"] != "missing_fields":
            continue
        if p["reason"] == "unreadable_file":
            name = KX.DOC_NAME.get(t, "document") if t else "document"
            needs.append({"doc": t, "slot": p["slot"], "kind": "format", "text": f"We could not open the file for your {name}. Please upload it as a JPG, PNG or PDF."})
            continue
        if p["reason"] in ("unrecognised", "no_reader", "missing_fields"):
            name = KX.DOC_NAME.get(t, "document") if t else "document"
            needs.append({"doc": t, "slot": p["slot"], "kind": "unreadable", "text": f"We could not read your {name}. Please upload a clear, full-page photo."})
    if needs and "gst" in blurred:
        needs.insert(0, {"doc": "gst", "slot": KX.DOC_SLOT["gst"], "kind": "blurry",
                         "text": f"Your {KX.DOC_NAME['gst']} is too blurry to read. Please retake it in good light, holding the phone steady."})
    seen, uniq = set(), []
    for n in needs:
        if n["text"] not in seen:
            seen.add(n["text"])
            uniq.append(n)
    if uniq:
        return {"status": "incomplete", "needs": uniq}

    app = _assemble(docs, blurred)
    app["declared"] = declared
    app["place"] = place
    for k in ("valid_till",):
        try:
            date.fromisoformat(app["sig"][k])
            date.fromisoformat(app["bill"]["bill_date"])
        except ValueError:
            return {"status": "incomplete", "needs": [{"doc": "sig", "slot": "signatory_id", "kind": "dates", "text": "We could not read the dates on your documents. Please upload clearer photos."}]}
    gst = app["gst"]
    lead = data_loader.lead_for(gst["gstin"], gst.get("trade_name"), gst.get("address")) if gst["gstin"] else None
    res = kyc_engine.assess(app, reg, lead)
    res["business"] = gst.get("trade_name") or None
    out = _package(res, app)
    pages = {d["slot"]: {"png": d.get("page"), "size": d.get("page_size"), "boxes": d.get("boxes", {}), "doctype": t}
             for t, d in docs.items() if d.get("page")}
    _locate(out["trace"], pages)
    out["documents"] = {slot: {"doctype": pg["doctype"], "size": pg["size"]} for slot, pg in pages.items()}
    out["masking"] = {"fields": sum((d.get("masked") or {}).get("fields", 0) for d in docs.values()),
                      "image_regions": sum((d.get("masked") or {}).get("image_regions", 0) for d in docs.values())}
    out["_pages"] = pages
    return out


def _package(res: dict, app: dict) -> dict:
    return {"status": "verdict", "verdict": res["verdict"], "raw_findings": res["findings"], "findings": friendly(res["findings"]),
            "checklist": checklist(res["findings"], app.get("udyam") is not None), "summary": _summary(app), "mode": res.get("mode"),
            "trace": res.get("trace", []), "thresholds": res.get("thresholds"), "declared": app.get("declared")}


FIELD_KEY = {"legal name": "legal_name", "legal name (business part)": "legal_name", "GSTIN": "gstin", "address": "address",
             "business name": "trade_name", "registration status": "gstin", "state": "address", "Udyam number": "udyam_number",
             "enterprise name": "enterprise_name", "city": "city", "date of registration": "date_of_registration",
             "valid till": "valid_till", "for business": "business", "signatory name": "name", "bill date": "bill_date",
             "billed to": "billed_to", "supply address": "address"}
DOC_OF_SLOT = {v: k for k, v in KX.DOC_SLOT.items()}


def _locate(trace: list[dict], pages: dict[str, dict]) -> None:
    by_doc = {pg["doctype"]: (slot, pg) for slot, pg in pages.items()}
    for t in trace:
        e = t.get("evidence")
        if not e:
            continue
        doc = e.get("doc")
        doc = DOC_OF_SLOT.get(doc, doc)
        hit = by_doc.get(doc)
        if not hit:
            continue
        slot, pg = hit
        e["slot"] = slot
        box = (pg.get("boxes") or {}).get(FIELD_KEY.get(e.get("field"), ""))
        if box:
            e["box"] = box
            e["page_size"] = pg.get("size")


SLOTS = ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof")


def case_document_path(case_id: str, slot: str) -> str | None:
    import os, re
    if not re.fullmatch(r"K\d{2}", case_id or "") or slot not in SLOTS:
        return None
    path = os.path.join(data_loader.DATA_DIR, "kyc_documents", f"{case_id}_{slot}.png")
    return path if os.path.exists(path) else None


def case_documents(case_id: str) -> list[str]:
    return [s for s in SLOTS if case_document_path(case_id, s)]


SAMPLE_PAGES: dict[str, dict] = {}


def sample_page(case_id: str, slot: str) -> bytes | None:
    return (SAMPLE_PAGES.get(case_id) or {}).get(slot, {}).get("png")


def verify_case_ocr(case_id: str, declared: str | None = None, place: dict | None = None) -> dict:
    files = {}
    for slot in SLOTS:
        p = case_document_path(case_id, slot)
        if p:
            with open(p, "rb") as f:
                files[slot] = f.read()
    if not files:
        raise KeyError(case_id)
    res = verify_upload(files, declared, place)
    if res.get("_pages"):
        SAMPLE_PAGES[case_id] = res["_pages"]
    return res


def verify_case(case_id: str, declared: str | None = None, place: dict | None = None) -> dict:
    fx = data_loader.fixtures()[case_id]
    gst = dict(fx["gst"])
    gst["gstin"] = gst["gstin"].rstrip("?")
    res = data_loader.assess_case(case_id, declared, place)
    app = {"gst": gst, "udyam": fx.get("udyam"), "declared": declared}
    out = _package(res, app)
    for t in out["trace"]:
        e = t.get("evidence")
        if e:
            e["slot"] = KX.DOC_SLOT.get(DOC_OF_SLOT.get(e.get("doc"), e.get("doc")), e.get("doc"))
    return out
