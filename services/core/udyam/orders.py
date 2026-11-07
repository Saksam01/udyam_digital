from __future__ import annotations
import os, secrets, time, uuid
from datetime import datetime, timedelta
from udyam import store

DIGITAL_ACTIVATION_SECONDS = float(os.getenv("DIGITAL_ACTIVATION_SECONDS", "20"))

HEADLINE = {
    "awaiting_kyc": "Verify your business to confirm your order.",
    "kyc_review": "Your documents are with our verification team. We will update this page as soon as they are checked.",
    "kyc_rejected": "We could not verify your documents. Please upload them again.",
    "approved": "Your order is approved. We are setting up your services.",
    "in_progress": "Your order is approved. We are setting up your services.",
    "live": "All your services are live.",
    "cancelled": "This order was cancelled. Contact Accel Business if you think this is a mistake.",
}

ALL_STATUSES = ("awaiting_kyc", "kyc_review", "kyc_rejected", "approved", "in_progress", "live", "cancelled")

# allowed status moves. only consent withdrawal sends an order back to awaiting_kyc
TRANSITIONS = {
    "awaiting_kyc": {"kyc_review", "kyc_rejected", "approved", "cancelled"},
    "kyc_rejected": {"kyc_review", "kyc_rejected", "approved", "cancelled", "awaiting_kyc"},
    "kyc_review": {"approved", "kyc_rejected", "cancelled", "awaiting_kyc"},
    "approved": {"in_progress", "cancelled"},
    "in_progress": {"live", "cancelled"},
    "live": set(),
    "cancelled": set(),
}
LEAD_ORDER = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC review", "KYC complete", "Activated"]


def _now() -> float:
    return time.time()


def _visit_ts(install_days: int) -> float:
    d = datetime.now() + timedelta(days=max(1, install_days - 1))
    return d.replace(hour=11, minute=0, second=0, microsecond=0).timestamp()


def _lead_update(lead_id: str, **fields):
    if not lead_id or not fields:
        return
    cur = store.one("SELECT stage FROM leads WHERE lead_id=?", (lead_id,))
    if cur and "stage" in fields:
        have = cur["stage"] if cur["stage"] in LEAD_ORDER else "Lead"
        if have == "Activated":
            fields.pop("status", None)
        if LEAD_ORDER.index(fields["stage"]) < LEAD_ORDER.index(have):
            fields.pop("stage")
    if fields.get("status") in ("open", "review", "won"):
        fields["drop_reason"] = None
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    store.x(f"UPDATE leads SET {cols} WHERE lead_id=?", (*fields.values(), _now(), lead_id))
    if "stage" in fields or "status" in fields:
        from udyam import crm
        crm.rescore(lead_id)


def create_order(lead_id: str, quote: dict, business: str | None, city: str | None) -> dict:
    oid = "ACC-" + uuid.uuid4().hex[:8].upper()
    lines = [{"product_id": l["product_id"], "label": l.get("label") or l["name"], "spec": l.get("spec") or l["name"],
              "qty": l["qty"], "kind": l.get("kind", "field"), "install_days": l["install_days"], "state": "queued",
              "monthly": l["line_monthly_list_inr"]} for l in quote["lines"]]
    now = _now()
    store.x("INSERT INTO orders(order_id, lead_id, created_at, updated_at, status, quote, lines, kyc, partner_id, business, city) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (oid, lead_id, now, now, "awaiting_kyc", store.dumps(quote), store.dumps(lines), None, None, business, city))
    store.x("UPDATE orders SET access_key=? WHERE order_id=?", (secrets.token_urlsafe(18), oid))
    prev = (store.loads((store.one("SELECT bundle FROM leads WHERE lead_id=?", (lead_id,)) or {}).get("bundle"), {}) or {})
    kept = {(l["label"], l["spec"]) for l in lines}
    was = {(l["label"], l["spec"]) for l in prev.get("lines", [])}
    bundle = {"name": quote.get("bundle_name"), "monthly_ex": quote["tax"]["monthly_ex_gst"], "monthly_incl": quote["tax"]["monthly_incl_gst"],
              "setup": quote["setup_total_inr"], "contract": quote["contract_months"],
              "lines": [{"label": l["label"], "spec": l["spec"], "qty": l["qty"], "monthly": l["monthly"]} for l in lines],
              "recommended_monthly": prev.get("monthly_ex"),
              "dropped": [{"label": l["label"], "monthly": l["monthly"]} for l in prev.get("lines", []) if (l["label"], l["spec"]) not in kept],
              "added": [l["label"] for l in lines if (l["label"], l["spec"]) not in was] if was else []}
    _lead_update(lead_id, stage="Quote accepted", status="open", bundle=store.dumps(bundle))
    store.log("quote_accepted", f"Accepted {quote.get('bundle_name') or 'bundle'} at ₹{quote['tax']['monthly_ex_gst']}/month + GST", lead_id, oid, "customer")
    out = get(oid)
    out["access_key"] = access_key(oid)
    return out


def access_key(order_id: str) -> str | None:
    r = store.one("SELECT access_key FROM orders WHERE order_id=?", (order_id,))
    return r["access_key"] if r else None


def request_assist(order_id: str) -> dict:
    """The customer asks for a local channel partner to help with paperwork."""
    o = _row(order_id)
    if not o:
        raise KeyError(order_id)
    part = store.partner_for(o.get("city"), "Channel partner")
    if part:
        _lead_update(o["lead_id"], partner_id=part["partner_id"])
        store.log("assist", f"Customer asked for help. {part['name']} (channel partner) will call to assist with the paperwork", o["lead_id"], order_id, "customer")
    return get(order_id)


def _row(order_id: str) -> dict | None:
    return store.one("SELECT * FROM orders WHERE order_id=?", (order_id,))


def _save(order_id: str, **fields):
    if "status" in fields:
        row = store.one("SELECT status FROM orders WHERE order_id=?", (order_id,))
        if row and fields["status"] != row["status"] and fields["status"] not in TRANSITIONS.get(row["status"], set()):
            raise ValueError(f"an order cannot go from {row['status']} to {fields['status']}")
    cols = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
    vals = [store.dumps(v) if k in ("lines", "kyc", "quote") else v for k, v in fields.items()]
    store.x(f"UPDATE orders SET {cols} WHERE order_id=?", (*vals, _now(), order_id))


def _start_fulfilment(o: dict, actor: str):
    lines = store.loads(o["lines"], [])
    eng = store.partner_for(o.get("city"), "Field engineer")
    now = _now()
    has_field = False
    for l in lines:
        if l["state"] != "queued":
            continue
        if l["kind"] == "digital":
            l["state"] = "in_progress"
            l["due"] = now + DIGITAL_ACTIVATION_SECONDS
        else:
            has_field = True
            l["state"] = "scheduled"
            l["visit_ts"] = _visit_ts(l["install_days"])
    _save(o["order_id"], status="in_progress", lines=lines, partner_id=eng["partner_id"] if (eng and has_field) else None)
    _lead_update(o["lead_id"], stage="KYC complete", status="open")
    store.log("approved", "Order approved. Provisioning started.", o["lead_id"], o["order_id"], actor)
    if has_field and eng:
        store.log("visit_scheduled", f"Field visit scheduled with {eng['name']}", o["lead_id"], o["order_id"], "system")


def record_consent(order_id: str, purpose: str = "KYC and service activation") -> str:
    import hashlib
    o = _row(order_id)
    if not o:
        raise KeyError(order_id)
    cid = "DPDP-" + hashlib.sha256(f"{order_id}|{purpose}|{_now()}".encode()).hexdigest()[:10].upper()
    store.log("consent", f"Data consent recorded for {purpose} ({cid})", o["lead_id"], order_id, "customer")
    return cid


def _verified_name(order_id: str, lead_id: str, summary: dict):
    name = (summary or {}).get("business")
    if name:
        _save(order_id, business=name)
        _lead_update(lead_id, business=name)


def apply_kyc(order_id: str, verdict: str, findings: list[dict], details: dict | None = None, actor: str = "customer",
              pages: dict | None = None) -> dict:
    """pages: cleaned, Aadhaar-redacted page images."""
    from udyam import privacy
    o = _row(order_id)
    if not o:
        raise KeyError(order_id)
    c = privacy.consent_for_order(order_id)
    if not c or c["status"] != "active":
        raise ValueError("documents cannot be checked without the customer's consent")
    if o["status"] not in ("awaiting_kyc", "kyc_rejected"):
        raise ValueError(f"documents are not expected while the order is {o['status']}")
    details = details or {}
    kyc = {"verdict": verdict, "findings": findings, "customer": details.get("customer", []), "checklist": details.get("checklist", []),
           "summary": details.get("summary", {}), "consent": details.get("consent"), "at": _now(),
           "trace": details.get("trace", []), "thresholds": details.get("thresholds"), "declared": details.get("declared"),
           "documents": details.get("documents", {}), "masking": details.get("masking"), "source": details.get("source", "upload")}
    privacy.purge(order_id, "new documents received")
    if verdict == "PASS":
        _save(order_id, kyc=kyc, status="approved")
        _verified_name(order_id, o["lead_id"], kyc["summary"])
        _start_fulfilment(_row(order_id), actor)
    elif verdict == "REVIEW":
        kept = privacy.put_pages(order_id, pages) if pages else 0
        kyc["pages_held"] = kept
        _save(order_id, kyc=kyc, status="kyc_review")
        _lead_update(o["lead_id"], stage="KYC review", status="review")
        store.log("kyc_review", "Documents sent to the verification team for a manual check", o["lead_id"], order_id, "system")
    else:
        _save(order_id, kyc=kyc, status="kyc_rejected")
        _lead_update(o["lead_id"], stage="Quote accepted", status="open")
        store.log("kyc_rejected", "Documents could not be verified, customer asked to re-upload", o["lead_id"], order_id, "system")
    return get(order_id)


def resolve_review(order_id: str, decision: str, note: str = "", actor: str = "admin") -> dict:
    o = _row(order_id)
    if not o or o["status"] != "kyc_review":
        raise ValueError("order is not waiting for review")
    from udyam import privacy
    kyc = store.loads(o["kyc"], {})
    kyc["reviewed_by"] = actor
    kyc["review_note"] = note
    privacy.purge(order_id, f"reviewer decided: {decision}")
    if decision == "approve":
        _save(order_id, kyc=kyc, status="approved")
        _verified_name(order_id, o["lead_id"], kyc.get("summary"))
        store.log("review_approved", "Verification team approved the documents" + (f": {note}" if note else ""), o["lead_id"], order_id, actor)
        _start_fulfilment(_row(order_id), actor)
    else:
        _save(order_id, kyc=kyc, status="kyc_rejected")
        _lead_update(o["lead_id"], stage="Quote accepted", status="open")
        store.log("review_rejected", "Verification team asked for fresh documents" + (f": {note}" if note else ""), o["lead_id"], order_id, actor)
    return get(order_id)


ADMIN_ACTIONS = ("approve", "reject", "mark_live", "cancel")


def admin_set_status(order_id: str, action: str, note: str = "", actor: str = "admin") -> dict:
    from udyam import privacy
    o = _row(order_id)
    if not o:
        raise KeyError(order_id)
    st = o["status"]
    suffix = f": {note}" if note else ""
    if action in ("approve", "reject"):
        if st != "kyc_review":
            raise ValueError("only documents waiting for a manual check can be approved or rejected")
        return resolve_review(order_id, action, note, actor)
    if action == "mark_live":
        if st != "in_progress":
            raise ValueError("services can only go live after verification and dispatch")
        lines = store.loads(o["lines"], [])
        now = _now()
        for l in lines:
            if l["state"] != "live":
                l["state"], l["live_ts"] = "live", now
        _save(order_id, lines=lines)
        store.log("all_live", f"All services marked live by {actor}{suffix}", o["lead_id"], order_id, actor)
        _finish_if_done(_row(order_id), lines)
    elif action == "cancel":
        if st in ("live", "cancelled"):
            raise ValueError(f"order is already {st}")
        privacy.purge(order_id, f"cancelled by {actor}")
        _save(order_id, status="cancelled")
        _lead_update(o["lead_id"], status="lost", drop_reason=note or "Cancelled by Accel")
        store.log("cancelled", f"Order cancelled by {actor}{suffix}", o["lead_id"], order_id, actor)
    else:
        raise ValueError("unknown action")
    return get(order_id, admin=True)


def list_orders(status: str | None = None, q: str | None = None, limit: int = 100) -> list[dict]:
    where, args = [], []
    if status:
        where.append("o.status=?")
        args.append(status)
    if q:
        where.append("(o.business LIKE ? OR o.order_id LIKE ? OR o.city LIKE ? OR o.lead_id LIKE ?)")
        args += [f"%{q}%"] * 4
    sql = "SELECT o.order_id FROM orders o" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY o.updated_at DESC LIMIT ?"
    return [get(r["order_id"], admin=True) for r in store.q(sql, (*args, limit))]


def _finish_if_done(o: dict, lines: list[dict]):
    if lines and all(l["state"] == "live" for l in lines) and o["status"] != "live":
        _save(o["order_id"], status="live")
        _lead_update(o["lead_id"], stage="Activated", status="won", drop_reason=None)
        store.log("live", "All services are live", o["lead_id"], o["order_id"], "system")


def erase_kyc(order_id: str):
    o = _row(order_id)
    if not o:
        return
    kyc = store.loads(o["kyc"], {}) or {}
    kept = {"verdict": kyc.get("verdict"), "at": kyc.get("at"), "erased": True, "erased_at": _now()}
    status = "awaiting_kyc" if o["status"] in ("awaiting_kyc", "kyc_review", "kyc_rejected") else o["status"]
    _save(order_id, kyc=kept, status=status)


def tick_all():
    for r in store.q("SELECT order_id FROM orders WHERE status IN ('approved','in_progress')"):
        tick(r["order_id"])


def tick(order_id: str):
    o = _row(order_id)
    if not o or o["status"] not in ("in_progress", "approved"):
        return
    lines = store.loads(o["lines"], [])
    changed = False
    now = _now()
    for l in lines:
        if l["kind"] == "digital" and l["state"] == "in_progress" and now >= l.get("due", 0):
            l["state"] = "live"
            l["live_ts"] = now
            changed = True
            store.log("line_live", f"{l['label']} is live", o["lead_id"], order_id, "system")
    if changed:
        _save(order_id, lines=lines)
        _finish_if_done(_row(order_id), lines)


def advance_line(order_id: str, product_id: str, actor: str = "admin") -> dict:
    o = _row(order_id)
    if not o:
        raise KeyError(order_id)
    if o["status"] != "in_progress":
        raise ValueError("work can only start after the documents are verified")
    lines = store.loads(o["lines"], [])
    for l in lines:
        if l["product_id"] != product_id:
            continue
        if l["state"] == "scheduled":
            l["state"] = "in_progress"
            store.log("line_started", f"Engineer started work on {l['label']}", o["lead_id"], order_id, actor)
        elif l["state"] in ("in_progress", "queued"):
            l["state"] = "live"
            l["live_ts"] = _now()
            store.log("line_live", f"{l['label']} is live", o["lead_id"], order_id, actor)
        break
    _save(order_id, lines=lines)
    _finish_if_done(_row(order_id), lines)
    return get(order_id)


STATE_TEXT = {"queued": "Waiting for verification", "scheduled": "Visit scheduled", "in_progress": "Being set up", "live": "Live"}


def get(order_id: str, admin: bool = False, verifier: bool = False) -> dict | None:
    tick(order_id)
    o = _row(order_id)
    if not o:
        return None
    quote = store.loads(o["quote"], {})
    lines = store.loads(o["lines"], [])
    kyc = store.loads(o["kyc"], {})
    eng = store.partner(o.get("partner_id"))
    city = store.canon_city(o.get("city"))
    if eng and city and eng["city"] != city:
        eng = store.partner_for(city, "Field engineer")
        store.x("UPDATE orders SET partner_id=? WHERE order_id=?", (eng["partner_id"], order_id))
    lead = store.one("SELECT partner_id FROM leads WHERE lead_id=?", (o["lead_id"],)) or {}
    asst = store.partner(lead.get("partner_id"))
    if asst and city and asst["city"] != city:
        asst = store.partner_for(city, asst["kind"])
        store.x("UPDATE leads SET partner_id=? WHERE lead_id=?", (asst["partner_id"], o["lead_id"]))
    if asst and asst["kind"] != "Channel partner":
        asst = None
    events = store.q("SELECT ts, kind, text, actor FROM events WHERE order_id=? ORDER BY id DESC LIMIT 30", (order_id,))
    if not (admin or verifier):
        events = [e for e in events if e["kind"] not in ("consent",)]
    out_lines = []
    for l in lines:
        item = {k: l.get(k) for k in ("product_id", "label", "spec", "qty", "kind", "state", "install_days", "visit_ts", "live_ts")}
        item["status_text"] = STATE_TEXT.get(l["state"], l["state"])
        out_lines.append(item)
    out_lines.sort(key=lambda l: ({"live": 0, "in_progress": 1, "scheduled": 2, "queued": 3}[l["state"]], l["install_days"]))
    return {
        "order_id": order_id, "lead_id": o["lead_id"], "status": o["status"], "headline": HEADLINE.get(o["status"], ""),
        "business": o["business"], "city": o.get("city"), "created_at": o["created_at"], "updated_at": o["updated_at"],
        "bundle_name": quote.get("bundle_name"), "tax": quote.get("tax"), "setup_total_inr": quote.get("setup_total_inr"),
        "contract_months": quote.get("contract_months"), "activation_eta_days": quote.get("activation_eta_days"),
        "lines": out_lines,
        "kyc": ({"verdict": kyc.get("verdict"), "findings": kyc.get("customer", []), "checklist": kyc.get("checklist", []),
                 "summary": kyc.get("summary", {}), "erased": kyc.get("erased", False),
                 **({"raw_findings": [{k: v for k, v in f.items() if k != "evidence"} for f in kyc.get("findings", [])],
                     "review_note": kyc.get("review_note"), "pages_held": kyc.get("pages_held", 0), "declared": kyc.get("declared")}
                    if (admin or verifier) else {}),
                 **({"trace": kyc.get("trace", []), "thresholds": kyc.get("thresholds"), "documents": kyc.get("documents", {}),
                     "masking": kyc.get("masking"), "source": kyc.get("source")} if verifier else {})}
                if kyc else None),
        "engineer": {"name": eng["name"], "phone": eng["phone"], "role": eng["kind"], "city": eng["city"]} if eng else None,
        "assist": {"name": asst["name"], "phone": asst["phone"], "role": asst["kind"], "city": asst["city"]} if asst else None,
        "events": events, "live_count": sum(1 for l in lines if l["state"] == "live"), "total_count": len(lines),
    }
