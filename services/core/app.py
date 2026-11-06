"""Core API: quotes, Smart KYC, advisor and voice. Run with uvicorn app:app."""

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

from udyam import data_loader, advisor, voice, recommender
from udyam.quote_engine import build_quote

app = FastAPI(title="Udyam Digital, Core API", version="0.1.0",
              description="Deterministic quotes, Smart KYC and a guard-railed advisor for the Airtel SYNC 2026 prototype.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SESSIONS: dict[str, dict] = {}


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


class KycRequest(BaseModel):
    case_id: str = Field(..., description="One of K01..K12")


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "accel-admin")


def _admin_token() -> str:
    import hashlib
    return hashlib.sha256(f"udyam-admin|{ADMIN_PASSWORD}".encode()).hexdigest()[:32]


class AdminLogin(BaseModel):
    password: str


@app.post("/api/v1/admin/login")
def admin_login(req: AdminLogin):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(401, "wrong password")
    return {"token": _admin_token()}


@app.get("/api/v1/admin/leads")
def admin_leads(authorization: str = Header(default="")):
    if authorization.replace("Bearer ", "").strip() != _admin_token():
        raise HTTPException(401, "unauthorized")
    from udyam import propensity
    data_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    return propensity.rank_unclosed(data_dir)[:40]


@app.get("/health")
def health():
    return {"ok": True, "mode": os.environ["ID_VALIDATION_MODE"], "as_of": os.environ["AS_OF_DATE"],
            "products": len(data_loader.catalogue())}


@app.get("/api/v1/catalogue")
def catalogue():
    """Catalogue metadata only, names, gates, dependencies. Prices come from /quotes."""
    cat = data_loader.catalogue()
    return [{"product_id": p.id, "name": p.name, "unit": p.unit, "requires_gstin": p.gstin,
             "min_employees": p.min_emp, "min_sites": p.min_sites, "city_tiers": sorted(p.tiers),
             "requires_one_of": list(p.requires_one_of), "install_days": p.install_days,
             "target_segments": sorted(p.targets)} for p in (cat[k] for k in sorted(cat))]


@app.post("/api/v1/quotes")
def quotes(req: QuoteRequest):
    cat = data_loader.catalogue()
    prof = req.profile.model_dump()
    if prof.get("city_tier") in (1, 2):
        pass
    elif prof.get("city"):
        prof["city_tier"] = data_loader.city_tiers().get(prof["city"].strip().title(), 2)
    else:
        prof["city_tier"] = 2
    eng = {"segment": prof["segment"], "city_tier": prof["city_tier"],
           "employees": max(1, min(prof["employees"], 500)), "num_sites": max(1, min(prof["num_sites"], 50)),
           "gstin_status": (prof.get("gstin_status") or "none").lower()}
    items = {i.product_id: max(1, i.qty) for i in req.items}
    return build_quote(cat, eng, items, req.price_point)


@app.post("/api/v1/advisor/messages")
def advisor_messages(req: AdvisorRequest):
    s = SESSIONS.setdefault(req.session_id, {"lang": req.lang})
    s["lang"] = req.lang
    if req.profile is not None:
        s["profile"] = req.profile.model_dump()
    return advisor.run_turn(s, req.text)


@app.get("/api/v1/kyc/cases")
def kyc_cases():
    return [data_loader.kyc_case_summary(cid) for cid in data_loader.kyc_case_ids()]


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
    return recommender.suitable_products(cat, raw, req.profile.model_dump(), data_loader.city_tiers(), req.categories, req.needs)


class TtsRequest(BaseModel):
    text: str
    lang: str = "en-IN"


@app.get("/api/v1/voice/status")
def voice_status():
    return voice.status()


@app.post("/api/v1/kyc/extract")
async def kyc_extract(gst_certificate: UploadFile = File(...)):
    """Read an uploaded GST certificate, extract the GSTIN and validate it against the mock registry."""
    from udyam import ocr_pipeline, kyc_engine
    if not ocr_pipeline.available():
        return {"ocr_available": False,
                "message": "Live OCR is not installed on this server. The sample applicants below run the full validation."}
    import tempfile
    data = await gst_certificate.read()
    reg = data_loader.registry()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(data)
        path = tf.name
    try:
        ext = ocr_pipeline.extract_gst_certificate(path, set(reg.gst.keys()))
    except Exception as e:
        return {"ocr_available": True, "message": f"Could not read the document: {e}"}
    finally:
        os.unlink(path)
    gstin = ext.get("gstin")
    if not gstin:
        return {"ocr_available": True, "message": "Could not read a GSTIN. Please re-take the photo in better light."}
    v = kyc_engine.validate_gstin(gstin)
    r = reg.gst.get(gstin)
    return {"ocr_available": True,
            "extracted": {"gstin": gstin, "source": ext.get("gstin_source")},
            "validation": {"format_ok": v.get("format_ok"), "checksum_ok": v.get("checksum_ok"),
                           "state": v.get("state"), "in_registry": r is not None,
                           "registry_status": r.get("status") if r else None,
                           "legal_name": r.get("legal_name") if r else None}}


@app.post("/api/v1/voice/tts")
def voice_tts(req: TtsRequest):
    if not voice.enabled():
        raise HTTPException(503, "voice not configured")
    try:
        data = voice.tts(req.text, req.lang)
    except Exception as e:
        raise HTTPException(502, f"tts failed: {e}")
    return {"audio_base64": _b64.b64encode(data).decode(), "mime": "audio/wav"}


@app.post("/api/v1/voice/stt")
async def voice_stt(audio: UploadFile = File(...), lang: str = Form("unknown")):
    if not voice.enabled():
        raise HTTPException(503, "voice not configured")
    data = await audio.read()
    try:
        return {"transcript": voice.stt(data, audio.filename or "audio.webm", lang)}
    except Exception as e:
        raise HTTPException(502, f"stt failed: {e}")
