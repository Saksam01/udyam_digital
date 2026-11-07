import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

os.environ.setdefault("ID_VALIDATION_MODE", "mock")
os.environ.setdefault("AS_OF_DATE", "2026-07-15")

from typing import Optional
import base64 as _b64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import threading
from udyam import data_loader, advisor, voice, recommender, store, crm, orders, kyc_service, privacy
import asyncio, json as _json, re as _re, time as _time
from fastapi import Request
from fastapi.responses import StreamingResponse, Response
from udyam.quote_engine import build_quote

app = FastAPI(title="Udyam Digital, Core API", version="0.1.0",
              description="Deterministic quotes, Smart KYC and a guard-railed advisor for the Airtel SYNC 2026 prototype.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SESSIONS: dict[str, dict] = {}


def _ticker():
    n = 0
    while True:
        try:
            if store.ready():
                orders.tick_all()
            if n % 300 == 0:
                privacy.sweep()
        except Exception as e:
            print("ticker:", e)
        n += 1
        _time.sleep(2)


@app.on_event("startup")
def _boot():
    threading.Thread(target=crm.ensure_seed, daemon=True).start()
    threading.Thread(target=_ticker, daemon=True).start()


class Profile(BaseModel):
    segment: str = Field(..., description="micro | prof | multi | mfg")
    business_type: Optional[str] = None
    employees: int = 1
    num_sites: int = 1
    city: Optional[str] = None
    city_tier: Optional[int] = None
    gstin_status: str = "none"
    current_tools: Optional[str] = None
    needs: list[str] = []
    categories: list[str] = []
    need_tags: list[str] = []


class QuoteItem(BaseModel):
    product_id: str
    qty: int = 1


class QuoteRequest(BaseModel):
    profile: Profile
    items: list[QuoteItem]
    price_point: str = "list"


class AdvisorRequest(BaseModel):
    session_id: str = "demo"
    text: str = ""
    profile: Optional[Profile] = None
    lang: str = "en"
    business: Optional[str] = None


class KycRequest(BaseModel):
    case_id: str = Field(..., description="One of K01..K12")
    ocr: bool = Field(False, description="Read the real specimen images with OCR instead of the pre-extracted fixtures")
    consent_id: Optional[str] = None


# sales and verifier are separate logins, docs are verifier only
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "accel-admin")
VERIFIER_PASSWORD = os.getenv("VERIFIER_PASSWORD", "accel-verify")


def _token(role: str) -> str:
    import hashlib
    pw = ADMIN_PASSWORD if role == "sales" else VERIFIER_PASSWORD
    return hashlib.sha256(f"udyam-{role}|{pw}".encode()).hexdigest()[:32]


class AdminLogin(BaseModel):
    password: str


@app.post("/api/v1/admin/login")
def admin_login(req: AdminLogin):
    if req.password == ADMIN_PASSWORD:
        return {"token": _token("sales"), "role": "sales"}
    if req.password == VERIFIER_PASSWORD:
        return {"token": _token("verifier"), "role": "verifier"}
    raise HTTPException(401, "wrong password")


def _role(authorization: str = "", t: str = "") -> str | None:
    tok = (authorization.replace("Bearer ", "").strip() or t or "").strip()
    for role in ("sales", "verifier"):
        if tok and tok == _token(role):
            return role
    return None


def _auth(authorization: str, roles: tuple = ("sales", "verifier"), t: str = "") -> str:
    role = _role(authorization, t)
    if role is None:
        raise HTTPException(401, "unauthorized")
    if role not in roles:
        raise HTTPException(403, "this needs the verification desk login" if "verifier" in roles else "not allowed for this role")
    return role


@app.get("/api/v1/admin/overview")
def admin_overview(authorization: str = Header(default=""), stage: str = "", q: str = "", live_only: bool = False, limit: int = 60,
                   status: str = "open"):
    _auth(authorization)
    return crm.overview(min(max(limit, 1), 200), stage or None, q or None, live_only, status)


@app.get("/api/v1/admin/leads")
def admin_leads(authorization: str = Header(default=""), status: str = "open", live_only: bool = False, q: str = "", limit: int = 100):
    _auth(authorization, ("sales",))
    return crm.lead_list(status, live_only, q or None, min(max(limit, 1), 300))


@app.get("/api/v1/admin/leads/{lead_id}")
def admin_lead(lead_id: str, authorization: str = Header(default="")):
    _auth(authorization)
    try:
        return crm.lead_detail(lead_id)
    except KeyError:
        raise HTTPException(404, "unknown lead")


class LeadUpdate(BaseModel):
    stage: Optional[str] = None
    status: Optional[str] = None
    drop_reason: Optional[str] = None
    note: Optional[str] = None


@app.post("/api/v1/admin/leads/{lead_id}/update")
def admin_lead_update(lead_id: str, req: LeadUpdate, authorization: str = Header(default="")):
    _auth(authorization)
    try:
        return crm.update_lead(lead_id, req.stage, req.status, req.drop_reason, req.note)
    except KeyError:
        raise HTTPException(404, "unknown lead")
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/v1/admin/orders")
def admin_orders(authorization: str = Header(default=""), status: str = "", q: str = "", limit: int = 100):
    _auth(authorization)
    return orders.list_orders(status or None, q or None, min(max(limit, 1), 300))


class OrderStatusRequest(BaseModel):
    action: str
    note: str = ""


KYC_DECISIONS = ("approve", "reject")


@app.post("/api/v1/admin/orders/{order_id}/status")
def admin_order_status(order_id: str, req: OrderStatusRequest, authorization: str = Header(default="")):
    """Approve, reject, send to review, mark live, cancel or reopen any order."""
    role = _auth(authorization)
    if req.action not in orders.ADMIN_ACTIONS:
        raise HTTPException(422, f"action must be one of {', '.join(orders.ADMIN_ACTIONS)}")
    if req.action in KYC_DECISIONS and role != "verifier":
        raise HTTPException(403, "KYC decisions are made by the verification desk")
    if req.action not in KYC_DECISIONS and role != "sales":
        raise HTTPException(403, "fulfilment changes are made from the sales console")
    try:
        return orders.admin_set_status(order_id, req.action, req.note.strip(), "verification desk" if role == "verifier" else "sales team")
    except KeyError:
        raise HTTPException(404, "unknown order")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/v1/admin/kyc/samples")
def admin_kyc_samples(authorization: str = Header(default="")):
    _auth(authorization, ("verifier",))
    out = []
    for cid in data_loader.kyc_case_ids():
        res = data_loader.assess_case(cid)
        out.append({**data_loader.kyc_case_summary(cid), "verdict": res["verdict"], "findings": res["findings"],
                    "trace": res.get("trace", []), "thresholds": res.get("thresholds"), "documents": kyc_service.case_documents(cid)})
    return out


@app.post("/api/v1/admin/kyc/samples/{case_id}/ocr")
def admin_kyc_sample_ocr(case_id: str, authorization: str = Header(default="")):
    _auth(authorization, ("verifier",))
    t0 = _time.perf_counter()
    try:
        res = kyc_service.verify_case_ocr(case_id)
    except KeyError:
        raise HTTPException(404, f"unknown case {case_id}")
    res = {k: v for k, v in res.items() if not k.startswith("_")}
    return {**res, "case_id": case_id, "seconds": round(_time.perf_counter() - t0, 2)}


@app.get("/api/v1/admin/kyc/samples/{case_id}/pages/{slot}")
def admin_kyc_sample_page(case_id: str, slot: str, t: str = "", authorization: str = Header(default="")):
    _auth(authorization, ("verifier",), t)
    png = kyc_service.sample_page(case_id, slot)
    if not png:
        raise HTTPException(404, "run OCR on this applicant first")
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/v1/verify/queue")
def verify_queue(authorization: str = Header(default="")):
    _auth(authorization, ("verifier",))
    rows = store.q("SELECT order_id FROM orders WHERE status='kyc_review' ORDER BY updated_at")
    out = []
    for r in rows:
        o = orders.get(r["order_id"], verifier=True)
        try:
            o["vault"] = privacy.vault_meta(r["order_id"])
        except Exception:
            o["vault"] = None
        o["consent"] = privacy.consent_for_order(r["order_id"])
        out.append(o)
    return out


@app.get("/api/v1/verify/orders/{order_id}/pages/{slot}")
def verify_page(order_id: str, slot: str, t: str = "", authorization: str = Header(default="")):
    """A held document page, decrypted for the reviewer only."""
    _auth(authorization, ("verifier",), t)
    try:
        png = privacy.get_page(order_id, slot)
    except ValueError:
        raise HTTPException(400, "bad id")
    if not png:
        raise HTTPException(404, "not held (already deleted after a decision, or never stored)")
    store.log("vault_viewed", f"Verification desk opened the {slot.replace('_', ' ')}", None, order_id, "verification desk")
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/v1/admin/storage")
def admin_storage(authorization: str = Header(default="")):
    _auth(authorization)
    return privacy.storage_report()


@app.get("/api/v1/admin/stream")
async def admin_stream(request: Request, t: str = ""):
    """Server-Sent Events for the console."""
    _auth("", t=t)
    return StreamingResponse(_sse(request, lambda e: True), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _owner(order_id: str, key: str):
    import hmac
    real = orders.access_key(order_id)
    if real is None:
        raise HTTPException(404, "unknown order")
    if not key or not hmac.compare_digest(real, key):
        raise HTTPException(403, "this order belongs to someone else")


@app.get("/api/v1/orders/{order_id}/stream")
async def order_stream(order_id: str, request: Request, k: str = ""):
    _owner(order_id, k)
    row = store.one("SELECT lead_id FROM orders WHERE order_id=?", (order_id,))
    lead = row["lead_id"]
    return StreamingResponse(_sse(request, lambda e: e["order_id"] == order_id or (lead and e["lead_id"] == lead)),
                             media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _sse(request: Request, wanted):
    last = store.seq()
    yield "retry: 500\n\n"
    yield f"event: hello\ndata: {_json.dumps({'seq': last})}\n\n"
    started = _time.time()
    beat = _time.time()
    while _time.time() - started < 20:
        if await request.is_disconnected():
            break
        cur = store.seq()
        if cur != last:
            evs = [e for e in store.changes_since(last) if wanted(e)]
            last = cur
            if evs:
                yield f"event: change\ndata: {_json.dumps(evs)}\n\n"
                beat = _time.time()
        elif _time.time() - beat > 15:
            yield ": ping\n\n"
            beat = _time.time()
        await asyncio.sleep(0.25)


@app.get("/api/v1/ocr/status")
def ocr_status():
    from udyam import kyc_extract
    return {"available": kyc_extract.available(), "tesseract": kyc_extract._tess()}


class ActionRequest(BaseModel):
    action: str


@app.post("/api/v1/admin/leads/{lead_id}/action")
def admin_action(lead_id: str, req: ActionRequest, authorization: str = Header(default="")):
    _auth(authorization)
    try:
        return crm.do_action(lead_id, req.action)
    except KeyError:
        raise HTTPException(404, "unknown lead")


class AdvanceRequest(BaseModel):
    product_id: str


@app.post("/api/v1/admin/orders/{order_id}/advance")
def admin_advance(order_id: str, req: AdvanceRequest, authorization: str = Header(default="")):
    _auth(authorization)
    try:
        return orders.advance_line(order_id, req.product_id, "field team")
    except KeyError:
        raise HTTPException(404, "unknown order")
    except ValueError as e:
        raise HTTPException(409, str(e))


class ReviewRequest(BaseModel):
    decision: str
    note: str = ""


@app.post("/api/v1/admin/orders/{order_id}/review")
def admin_review(order_id: str, req: ReviewRequest, authorization: str = Header(default="")):
    _auth(authorization, ("verifier",))
    if req.decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be approve or reject")
    try:
        return orders.resolve_review(order_id, req.decision, req.note, "verification desk")
    except ValueError as e:
        raise HTTPException(409, str(e))


class OrderRequest(BaseModel):
    lead_id: Optional[str] = None
    profile: Profile
    items: list[QuoteItem]
    business: Optional[str] = None
    contact: Optional[str] = None
    session_id: str = "demo"
    lang: str = "en"


@app.post("/api/v1/orders")
def create_order(req: OrderRequest):
    items = {i.product_id: max(1, i.qty) for i in req.items}
    prof = req.profile.model_dump()
    quote = recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), prof, items, data_loader.city_tiers())
    if quote["status"] == "blocked":
        why = "; ".join(v["message"] for v in quote["violations"] if v["severity"] == "block")
        raise HTTPException(409, f"This plan breaks a catalogue rule: {why}")
    if req.business:
        req.business = _re.sub(r"\s+", " ", req.business).strip()
        if _re.search(r"[^\x00-\x7F]", req.business) or not _re.search(r"[A-Za-z]", req.business):
            raise HTTPException(422, "Please write the business name in English letters, as on your GST certificate")
    lead_id = req.lead_id or crm.upsert_live_lead(req.session_id, prof, quote, req.lang, req.business, req.contact)
    if req.business or req.contact:
        crm.set_business(lead_id, req.business, req.contact)
    return orders.create_order(lead_id, quote, req.business, store.canon_city(prof.get("city")))


@app.get("/api/v1/orders/{order_id}")
def get_order(order_id: str, x_order_key: str = Header(default="")):
    _owner(order_id, x_order_key)
    o = orders.get(order_id)
    if not o:
        raise HTTPException(404, "unknown order")
    return o


@app.post("/api/v1/orders/{order_id}/assist")
def order_assist(order_id: str, x_order_key: str = Header(default="")):
    _owner(order_id, x_order_key)
    """Customer asks for a local partner to help with documents or the visit."""
    try:
        return orders.request_assist(order_id)
    except KeyError:
        raise HTTPException(404, "unknown order")


def _kyc_response(order_id: str, res: dict, consent: str | None = None, source: str = "upload") -> dict:
    pages = res.pop("_pages", None)
    if res["status"] != "verdict":
        return {**res, "order": orders.get(order_id)}
    current = orders.get(order_id)
    if current["status"] not in ("awaiting_kyc", "kyc_rejected"):
        return {**res, "order": current}
    details = {"customer": res["findings"], "checklist": res["checklist"], "summary": res["summary"], "consent": consent,
               "trace": res.get("trace", []), "thresholds": res.get("thresholds"), "declared": res.get("declared"),
               "documents": res.get("documents", {}), "masking": res.get("masking"), "source": source}
    order = orders.apply_kyc(order_id, res["verdict"], res["raw_findings"], details, pages=pages)
    return {"status": "verdict", "verdict": res["verdict"], "findings": res["findings"], "checklist": res["checklist"],
            "summary": res["summary"], "order": order, "consent_id": consent}


def _consent_or_400(order_id: str, consent_id: str | None) -> str:
    if not consent_id or not privacy.active_consent(consent_id, order_id):
        raise HTTPException(400, "consent is required before documents can be read")
    return consent_id


def _declared(order_id: str) -> str | None:
    row = store.one("SELECT business FROM orders WHERE order_id=?", (order_id,))
    name = (row or {}).get("business") or ""
    return name if name and not name.startswith("New ") else None


@app.post("/api/v1/orders/{order_id}/consent")
def order_consent(order_id: str, lang: str = "en", x_order_key: str = Header(default="")):
    _owner(order_id, x_order_key)
    """Creates the DPDP consent artifact. Upload stays locked in the app until this exists."""
    o = orders.get(order_id)
    if not o:
        raise HTTPException(404, "unknown order")
    return privacy.create_consent(order_id, o["lead_id"], lang)


@app.get("/api/v1/consent/{consent_id}")
def consent_get(consent_id: str, x_order_key: str = Header(default="")):
    c = privacy.get_consent(consent_id)
    if not c:
        raise HTTPException(404, "unknown consent")
    _owner(c["order_id"], x_order_key)
    return c


class WithdrawRequest(BaseModel):
    consent_id: str


@app.post("/api/v1/consent/withdraw")
def consent_withdraw(req: WithdrawRequest, x_order_key: str = Header(default="")):
    c = privacy.get_consent(req.consent_id)
    if not c:
        raise HTTPException(404, "unknown consent")
    _owner(c["order_id"], x_order_key)
    try:
        return privacy.withdraw(req.consent_id)
    except KeyError:
        raise HTTPException(404, "unknown consent")


@app.post("/api/v1/orders/{order_id}/kyc/case")
def order_kyc_case(order_id: str, req: KycRequest, x_order_key: str = Header(default="")):
    _owner(order_id, x_order_key)
    _demo_only()
    cid = _consent_or_400(order_id, req.consent_id)
    declared = _declared(order_id)
    try:
        from udyam import kyc_extract
        ocr = req.ocr and kyc_extract.available()
        res = kyc_service.verify_case_ocr(req.case_id, declared) if ocr else kyc_service.verify_case(req.case_id, declared)
    except KeyError:
        raise HTTPException(404, f"unknown case {req.case_id}")
    return _kyc_response(order_id, res, cid, f"sample {req.case_id}" + (" (OCR)" if ocr else ""))


@app.post("/api/v1/orders/{order_id}/kyc")
def order_kyc(order_id: str,
              consent_id: str = Form(""),
              x_order_key: str = Header(default=""),
              gst_certificate: Optional[UploadFile] = File(None),
              udyam_certificate: Optional[UploadFile] = File(None),
              signatory_id: Optional[UploadFile] = File(None),
              address_proof: Optional[UploadFile] = File(None)):
    _owner(order_id, x_order_key)
    if not orders.get(order_id):
        raise HTTPException(404, "unknown order")
    consent = _consent_or_400(order_id, consent_id)
    files = {}
    for slot, up in (("gst_certificate", gst_certificate), ("udyam_certificate", udyam_certificate),
                     ("signatory_id", signatory_id), ("address_proof", address_proof)):
        if up is not None:
            data = up.file.read()
            if data:
                files[slot] = data
    if not files:
        raise HTTPException(400, "no documents received")
    res = kyc_service.verify_upload(files, _declared(order_id))
    return _kyc_response(order_id, res, consent)


@app.get("/health")
def health():
    return {"ok": True, "mode": os.environ["ID_VALIDATION_MODE"], "as_of": os.environ["AS_OF_DATE"],
            "products": len(data_loader.catalogue())}


@app.get("/api/v1/catalogue")
def catalogue():
    """Catalogue metadata only, names, gates, dependencies."""
    cat = data_loader.catalogue()
    return [{"product_id": p.id, "name": p.name, "unit": p.unit, "requires_gstin": p.gstin,
             "min_employees": p.min_emp, "min_sites": p.min_sites, "city_tiers": sorted(p.tiers),
             "requires_one_of": list(p.requires_one_of), "install_days": p.install_days,
             "target_segments": sorted(p.targets)} for p in (cat[k] for k in sorted(cat))]


@app.post("/api/v1/quotes")
def quotes(req: QuoteRequest):
    items = {i.product_id: max(1, i.qty) for i in req.items}
    return recommender.quote_items(data_loader.catalogue(), data_loader.catalogue_raw(), req.profile.model_dump(), items,
                                   data_loader.city_tiers(), req.price_point)


@app.post("/api/v1/advisor/messages")
def advisor_messages(req: AdvisorRequest):
    s = SESSIONS.setdefault(req.session_id, {"lang": req.lang})
    s["lang"] = req.lang
    if req.profile is not None:
        s["profile"] = req.profile.model_dump()
    reply = advisor.run_turn(s, req.text)
    if reply.get("quote_card") and s.get("profile"):
        reply["profile"] = s["profile"]
        reply["lead_id"] = crm.upsert_live_lead(req.session_id, s["profile"], reply["quote_card"], req.lang, req.business)
    return reply


DEMO = os.getenv("DEMO_MODE", "0" if os.getenv("APP_ENV") == "production" else "1") == "1"


def _demo_only():
    if not DEMO:
        raise HTTPException(404, "not available")


@app.get("/api/v1/demo")
def demo_status():
    return {"samples": DEMO}


@app.get("/api/v1/kyc/cases")
def kyc_cases():
    _demo_only()
    return [{**data_loader.kyc_case_summary(cid), "documents": kyc_service.case_documents(cid)} for cid in data_loader.kyc_case_ids()]


@app.get("/api/v1/kyc/cases/{case_id}/docs/{slot}")
def kyc_case_doc(case_id: str, slot: str, t: str = ""):
    """Specimen image for one of the 12 sample applicants."""
    if not DEMO:
        _auth("", ("verifier",), t)
    from fastapi.responses import FileResponse
    path = kyc_service.case_document_path(case_id, slot)
    if not path:
        raise HTTPException(404, "no such document")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.post("/api/v1/kyc/assess")
def kyc_assess(req: KycRequest):
    try:
        return data_loader.assess_case(req.case_id)
    except KeyError:
        raise HTTPException(404, f"unknown case {req.case_id}")


@app.get("/api/v1/kyc/assess-all")
def kyc_assess_all():
    return [data_loader.assess_case(cid) for cid in data_loader.kyc_case_ids()]


class SuitableRequest(BaseModel):
    profile: Profile
    categories: list[str] = []
    needs: list[str] = []


@app.post("/api/v1/catalogue/suitable")
def catalogue_suitable(req: SuitableRequest):
    cat = data_loader.catalogue()
    raw = data_loader.catalogue_raw()
    return recommender.suitable_products(cat, raw, req.profile.model_dump(), data_loader.city_tiers(), req.categories, req.needs, req.profile.need_tags)


class TtsRequest(BaseModel):
    text: str
    lang: str = "en-IN"


@app.get("/api/v1/voice/status")
def voice_status():
    return voice.status()


@app.post("/api/v1/voice/tts")
def voice_tts(req: TtsRequest):
    if not voice.enabled():
        raise HTTPException(503, "voice not configured")
    try:
        data = voice.tts(req.text, req.lang)
    except Exception as e:
        raise HTTPException(502, f"tts failed: {e}")
    return {"audio_base64": _b64.b64encode(data).decode(), "mime": "audio/wav"}


class WarmRequest(BaseModel):
    texts: list[str]
    lang: str


@app.post("/api/v1/voice/warm")
def voice_warm(req: WarmRequest):
    """Pre-synthesises upcoming prompts so they play instantly."""
    if voice.enabled():
        voice.warm([(t, req.lang) for t in req.texts if t.strip()])
    return {"queued": len(req.texts)}


@app.post("/api/v1/voice/stt")
async def voice_stt(audio: UploadFile = File(...), lang: str = Form("unknown")):
    if not voice.enabled():
        raise HTTPException(503, "voice not configured")
    data = await audio.read()
    try:
        return {"transcript": voice.stt(data, audio.filename or "audio.webm", lang)}
    except Exception as e:
        raise HTTPException(502, f"stt failed: {e}")
