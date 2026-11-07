from __future__ import annotations
import hashlib, json, os, re, shutil, time
from datetime import datetime, timezone
from udyam import store

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
VAULT_DIR = os.getenv("KYC_VAULT_DIR", os.path.join(DATA_DIR, "kyc_vault"))
VAULT_MAX_DAYS = int(os.getenv("KYC_VAULT_MAX_DAYS", "30"))
RECORD_RETENTION_DAYS = int(os.getenv("KYC_RECORD_RETENTION_DAYS", "180"))

PURPOSE = "DoT telecom KYC verification and service provisioning"
DATA_CATEGORIES = ["GST certificate", "Udyam certificate", "Signatory ID (name, ID number, validity)", "Address proof (utility bill)"]
NOT_USED_FOR = ["marketing", "sharing with marketing partners", "credit scoring", "any purpose other than the one stated"]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_consent(order_id: str, lead_id: str | None, lang: str = "en") -> dict:
    """An immutable consent artifact."""
    now = time.time()
    cid = "DPDP-" + hashlib.sha256(f"{order_id}|{now}|{os.urandom(8).hex()}".encode()).hexdigest()[:10].upper()
    artifact = {
        "consent_id": cid,
        "order_id": order_id,
        "timestamp_utc": _iso(now),
        "data_principal": "Business owner / authorised signatory",
        "data_fiduciary": "Accel Telecom Ltd (Accel Business)",
        "purpose": PURPOSE,
        "legal_basis": "Consent under section 6, Digital Personal Data Protection Act 2023",
        "data_categories": DATA_CATEGORIES,
        "not_used_for": NOT_USED_FOR,
        "processing": ["OCR on Accel servers in India", "Mock GSTN and Udyam registry lookup", "Rule checks; a person checks only unclear cases"],
        "aadhaar_masking": "First 8 digits removed from text and page images before anything is stored",
        "raw_document_retention": f"Not stored after an automatic decision. Unclear cases: kept encrypted until a reviewer decides, at most {VAULT_MAX_DAYS} days",
        "data_retention_days": RECORD_RETENTION_DAYS,
        "language_shown": lang,
        "withdrawal_endpoint": "/api/v1/consent/withdraw",
        "grievance_contact": "privacy@accel.example (Grievance Officer)",
    }
    blob = json.dumps(artifact, sort_keys=True, ensure_ascii=False)
    sha = hashlib.sha256(blob.encode()).hexdigest()
    store.x("INSERT INTO consents VALUES (?,?,?,?,?,?,?,?)", (cid, order_id, lead_id, now, blob, sha, "active", None))
    store.log("consent", f"Consent recorded for {PURPOSE} ({cid})", lead_id, order_id, "customer")
    return {**artifact, "artifact_sha256": sha, "status": "active"}


def get_consent(consent_id: str) -> dict | None:
    r = store.one("SELECT * FROM consents WHERE consent_id=?", (consent_id,))
    if not r:
        return None
    art = json.loads(r["artifact"])
    ok = hashlib.sha256(r["artifact"].encode()).hexdigest() == r["artifact_sha256"]
    return {**art, "artifact_sha256": r["artifact_sha256"], "integrity_ok": ok, "status": r["status"],
            "withdrawn_at_utc": _iso(r["withdrawn_at"]) if r["withdrawn_at"] else None}


def consent_for_order(order_id: str) -> dict | None:
    r = store.one("SELECT consent_id FROM consents WHERE order_id=? ORDER BY created_at DESC LIMIT 1", (order_id,))
    return get_consent(r["consent_id"]) if r else None


def active_consent(consent_id: str, order_id: str) -> bool:
    r = store.one("SELECT status, order_id FROM consents WHERE consent_id=?", (consent_id,))
    return bool(r and r["status"] == "active" and r["order_id"] == order_id)


def withdraw(consent_id: str) -> dict:
    from udyam import orders
    r = store.one("SELECT * FROM consents WHERE consent_id=?", (consent_id,))
    if not r:
        raise KeyError(consent_id)
    if r["status"] == "withdrawn":
        return get_consent(consent_id)
    now = time.time()
    store.x("UPDATE consents SET status='withdrawn', withdrawn_at=? WHERE consent_id=?", (now, consent_id))
    deleted = purge(r["order_id"], "consent withdrawn")
    orders.erase_kyc(r["order_id"])
    store.log("consent_withdrawn", f"Consent {consent_id} withdrawn. {deleted} stored page(s) deleted and KYC details erased", r["lead_id"], r["order_id"], "customer")
    return get_consent(consent_id)


def _fernet():
    from cryptography.fernet import Fernet
    key = os.getenv("KYC_VAULT_KEY")
    if not key:
        path = os.path.join(DATA_DIR, ".vault_key")
        if not os.path.exists(path):
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(Fernet.generate_key())
        key = open(path, "rb").read().decode().strip()
    return Fernet(key.encode() if isinstance(key, str) else key)


def _safe(s: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", s or ""):
        raise ValueError("bad id")
    return s


# only REVIEW cases get stored, and only the cleaned + masked page
def put_pages(order_id: str, pages: dict[str, dict]) -> int:
    """pages: slot -> {"png": bytes, "size": [w, h], "boxes": {...}}."""
    d = os.path.join(VAULT_DIR, _safe(order_id))
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    f = _fernet()
    n = 0
    meta = {"stored_at": time.time(), "slots": {}}
    for slot, pg in pages.items():
        if not pg.get("png"):
            continue
        with open(os.path.join(d, f"{_safe(slot)}.bin"), "wb") as fh:
            fh.write(f.encrypt(pg["png"]))
        meta["slots"][slot] = {"size": pg.get("size"), "boxes": pg.get("boxes", {}), "doctype": pg.get("doctype")}
        n += 1
    with open(os.path.join(d, "meta.bin"), "wb") as fh:
        fh.write(f.encrypt(json.dumps(meta).encode()))
    return n


def get_page(order_id: str, slot: str) -> bytes | None:
    path = os.path.join(VAULT_DIR, _safe(order_id), f"{_safe(slot)}.bin")
    if not os.path.exists(path):
        return None
    return _fernet().decrypt(open(path, "rb").read())


def vault_meta(order_id: str) -> dict | None:
    path = os.path.join(VAULT_DIR, _safe(order_id), "meta.bin")
    if not os.path.exists(path):
        return None
    meta = json.loads(_fernet().decrypt(open(path, "rb").read()))
    meta["purge_after"] = meta["stored_at"] + VAULT_MAX_DAYS * 86400
    return meta


def purge(order_id: str, reason: str) -> int:
    d = os.path.join(VAULT_DIR, _safe(order_id))
    if not os.path.isdir(d):
        return 0
    n = len([x for x in os.listdir(d) if x.endswith(".bin") and x != "meta.bin"])
    shutil.rmtree(d, ignore_errors=True)
    if n:
        store.log("vault_purged", f"{n} stored document page(s) deleted ({reason})", None, order_id, "system")
    return n


def sweep() -> int:
    """Deletes anything past its retention limit."""
    if not os.path.isdir(VAULT_DIR):
        return 0
    n = 0
    for oid in os.listdir(VAULT_DIR):
        try:
            meta = vault_meta(oid)
        except Exception:
            meta = None
        if meta is None or time.time() > meta["purge_after"]:
            n += purge(oid, "retention limit reached")
    return n


def storage_report() -> dict:
    """Where data lives, for the console and the privacy note."""
    held = os.listdir(VAULT_DIR) if os.path.isdir(VAULT_DIR) else []
    return {
        "database": os.path.abspath(store.DB_PATH), "engine": "SQLite (WAL), on disk, survives restarts",
        "vault_dir": os.path.abspath(VAULT_DIR), "vault_encryption": "Fernet (AES-128-CBC + HMAC-SHA256), key from KYC_VAULT_KEY or data/.vault_key",
        "orders_with_documents_held": len(held), "vault_max_days": VAULT_MAX_DAYS, "record_retention_days": RECORD_RETENTION_DAYS,
        "consents": store.one("SELECT COUNT(*) AS n FROM consents")["n"],
        "consents_withdrawn": store.one("SELECT COUNT(*) AS n FROM consents WHERE status='withdrawn'")["n"],
    }
