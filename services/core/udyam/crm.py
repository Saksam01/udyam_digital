from __future__ import annotations
import hashlib, time
from udyam import store, propensity, profiles, recommender, data_loader

SEG_CODE = {v: k for k, v in propensity.SEGMENT_NAME.items()}
KEY_FOR_TYPE = {t: s.key for s in profiles.SPECS.values() for t in s.data_types}
STAGE_RANK = {s: i for i, s in enumerate(propensity.STAGES)}
OPEN_STATUSES = ("open", "review")

ACTION_RESULT = {
    "whatsapp_quote": "WhatsApp quote queued for sending",
    "verify_contact": "Contact check assigned to {partner}",
    "remote_onboarding": "Video onboarding invite queued",
    "partner_visit": "Site visit assigned to {partner}",
    "switch_offer": "Switch-over offer queued",
    "bundle_upsell": "Mobile and fibre bundle offer queued",
    "revised_quote": "Revised quote queued",
    "priority_dispatch": "Priority dispatch raised with {partner}",
    "resolve_docs": "Document request queued on WhatsApp",
    "assisted_kyc": "Assisted KYC booked with {partner}",
    "callback": "Call-back scheduled",
    "schedule_signatory": "E-sign slot requested from the signatory",
    "alt_access": "5G AirFiber alternative queued",
    "payment_retry": "Payment link queued",
    "nurture": "Added to the nurture campaign",
    "notify_partner": "Lead shared with {partner} (channel partner) on WhatsApp",
}
NEEDS_PARTNER = {"verify_contact", "partner_visit", "priority_dispatch", "assisted_kyc", "notify_partner"}


def _bundle_for_seed(cat, raw, ct, lead: dict) -> dict | None:
    if lead["stage"] not in ("Needs assessed", "Quote accepted", "KYC complete"):
        return None
    key = KEY_FOR_TYPE.get(lead["business_type"])
    seg = SEG_CODE.get(lead["segment"], "micro")
    gs = {"Active": "active", "Cancelled": "cancelled", "Suspended": "suspended"}.get(lead["gst_status"], "none")
    prof = {"business_type": key, "segment": seg, "employees": lead["employees"], "num_sites": lead["sites"],
            "city": lead["city"], "gstin_status": gs}
    name, items, _, quote, _ = recommender.pick(cat, raw, prof, ct, [], None, lead["interest"])
    return {"name": name, "monthly_ex": quote["tax"]["monthly_ex_gst"], "monthly_incl": quote["tax"]["monthly_incl_gst"],
            "setup": quote["setup_total_inr"], "contract": quote["contract_months"],
            "lines": [{"label": l["label"], "spec": l["spec"], "qty": l["qty"], "monthly": l["line_monthly_list_inr"]} for l in quote["lines"]]}


def ensure_seed():
    """Load the historical pipeline once."""
    try:
        data_dir = data_loader.DATA_DIR
        if store.one("SELECT 1 AS n FROM leads WHERE origin='seed' LIMIT 1"):
            store.seed_partners([r["city"] for r in store.q("SELECT DISTINCT city FROM leads")])
            store.fix_partner_cities()
            _seed_won()
            lead_list("open", limit=300)
            return
        rows = propensity.seed_leads(data_dir)
        store.seed_partners([r["city"] for r in rows])
        cat, raw, ct = data_loader.catalogue(), data_loader.catalogue_raw(), data_loader.city_tiers()
        base = time.time()
        with store._lock:
            c = store.db()
            c.execute("BEGIN")
            for i, r in enumerate(rows):
                bundle = _bundle_for_seed(cat, raw, ct, r)
                created = base - (i % 45) * 86400 - (i % 11) * 3600
                c.execute("INSERT OR REPLACE INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    r["lead_id"], "seed", created, created, r["business"], r["business_type"], KEY_FOR_TYPE.get(r["business_type"]),
                    r["segment"], r["city"], r["state"], r["language"], r["source"], r["stage"], "open", r["drop_reason"],
                    r["employees"], r["sites"], r["gstin"], r["gst_status"], r["contact"], None, r["spend"],
                    store.dumps(r["interest"]), r["p_activate"], store.dumps(r["signals"]), store.dumps(r["action"]), None,
                    store.dumps(bundle) if bundle else None, None, None))
            c.execute("COMMIT")
        _seed_won()
        lead_list("open", limit=300)
    finally:
        store.mark_ready()


def _seed_won():
    if store.one("SELECT 1 AS n FROM leads WHERE origin='seed' AND status='won' LIMIT 1"):
        return
    cat, raw = data_loader.catalogue(), data_loader.catalogue_raw()
    base = time.time()
    with store._lock:
        c = store.db()
        c.execute("BEGIN")
        for i, r in enumerate(propensity.won_leads(data_loader.DATA_DIR)):
            lines = [{"label": recommender.profiles.LABEL.get(pid, pid), "spec": cat[pid].name if pid in cat else pid, "qty": q,
                      "monthly": str(round((cat[pid].pmin + cat[pid].pmax) / 2 * q, 2)) if pid in cat else "0"} for pid, q in r["items"]]
            bundle = {"name": "Bundle bought", "monthly_ex": str(r["monthly"]), "monthly_incl": str(round(r["monthly"] * 1.18, 2)),
                      "setup": r["setup"], "contract": r["contract"], "lines": lines}
            created = base - (i % 45) * 86400 - (i % 7) * 3600
            c.execute("INSERT OR IGNORE INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                r["lead_id"], "seed", created, created, r["business"], r["business_type"], KEY_FOR_TYPE.get(r["business_type"]),
                r["segment"], r["city"], r["state"], r["language"], r["source"], "Activated", "won", None,
                r["employees"], r["sites"], r["gstin"], r["gst_status"], r["contact"], None, r["spend"],
                "[]", 1.0, store.dumps(r["signals"]), None, None, store.dumps(bundle), None, None))
        c.execute("COMMIT")


def upsert_live_lead(session_id: str, profile: dict, quote: dict, lang: str = "en", business: str | None = None,
                     contact: str | None = None) -> str:
    key = session_id + ("|" + " ".join(business.lower().split()) if business else "")
    lead_id = "LV-" + hashlib.sha1(key.encode()).hexdigest()[:8].upper()
    spec = profiles.spec_for(profile.get("business_type"), profile.get("segment"))
    existing = store.one("SELECT stage, business, contact FROM leads WHERE lead_id=?", (lead_id,))
    stage = existing["stage"] if existing and STAGE_RANK.get(existing["stage"], 0) > STAGE_RANK["Needs assessed"] else "Needs assessed"
    p, signals = propensity.score_profile(data_loader.DATA_DIR, {**profile, "lang": lang}, spec, stage)
    bundle = {"name": quote.get("bundle_name"), "monthly_ex": quote["tax"]["monthly_ex_gst"], "monthly_incl": quote["tax"]["monthly_incl_gst"],
              "setup": quote["setup_total_inr"], "contract": quote["contract_months"],
              "lines": [{"label": l["label"], "spec": l["spec"], "qty": l["qty"], "monthly": l["line_monthly_list_inr"]} for l in quote["lines"]]}
    gs = (profile.get("gstin_status") or "none").lower()
    gst_label = {"active": "Active", "unverified": "Active", "cancelled": "Cancelled", "suspended": "Suspended"}.get(gs, "none")
    name = business or (existing or {}).get("business") or f"New {spec.name} lead"
    action = {"id": "whatsapp_quote", "label": "Send 1-click WhatsApp quote"} if stage == "Needs assessed" else None
    now = time.time()
    if existing:
        store.x("UPDATE leads SET updated_at=?, business=?, business_type=?, bt_key=?, segment=?, city=?, language=?, stage=?, employees=?, sites=?, "
                "gst_status=?, p_activate=?, signals=?, action=?, bundle=? WHERE lead_id=?",
                (now, name, spec.name, spec.key, propensity.SEGMENT_NAME.get(spec.segment), store.canon_city(profile.get("city")), propensity.LANG_NAME.get(lang, "English"),
                 stage, profile.get("employees"), profile.get("num_sites"), gst_label, p, store.dumps(signals),
                 store.dumps(action) if action else None, store.dumps(bundle), lead_id))
    else:
        store.x("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            lead_id, "live", now, now, name, spec.name, spec.key, propensity.SEGMENT_NAME.get(spec.segment),
            store.canon_city(profile.get("city")), None, propensity.LANG_NAME.get(lang, "English"), "Advisor app", stage, "open", None,
            profile.get("employees"), profile.get("num_sites"), None, gst_label, contact, None, None, "[]", p,
            store.dumps(signals), store.dumps(action) if action else None, None, store.dumps(bundle), None, session_id))
        store.log("lead_created", f"New {spec.name} lead from the advisor in {(profile.get('city') or 'unknown city').title()}", lead_id, None, "customer")
    _localise(lead_id)
    store.log("recommended", f"Advisor recommended {quote.get('bundle_name')} at ₹{quote['tax']['monthly_ex_gst']}/month + GST", lead_id, None, "system")
    return lead_id


def _localise(lead_id: str):
    r = store.one("""SELECT l.city, p.city AS pc, p.kind FROM leads l JOIN partners p ON p.partner_id=l.partner_id
                     WHERE l.lead_id=?""", (lead_id,))
    if r and store.canon_city(r["city"]) and store.canon_city(r["city"]) != r["pc"]:
        np = store.partner_for(r["city"], r["kind"])
        store.x("UPDATE leads SET partner_id=? WHERE lead_id=?", (np["partner_id"] if np else None, lead_id))


def set_business(lead_id: str, business: str | None, contact: str | None = None, gstin: str | None = None):
    if lead_id and business:
        store.x("UPDATE leads SET business=?, contact=COALESCE(?, contact), gstin=COALESCE(?, gstin), updated_at=? WHERE lead_id=?",
                (business, contact, gstin, time.time(), lead_id))


def _display_likelihood(r: dict) -> float:
    if r.get("status") == "won" or r.get("stage") == "Activated":
        return 1.0
    if r.get("status") == "lost":
        return 0.0
    return r["p_activate"]


_SCORE_CACHE: dict = {}


def score_detail(r: dict, card: bool = True) -> dict:
    key = (r["lead_id"], r.get("stage"), r.get("status"), r.get("city"), r.get("language"), r.get("gst_status"),
           r.get("employees"), r.get("sites"), r.get("bt_key"), r.get("segment"))
    if key not in _SCORE_CACHE:
        if len(_SCORE_CACHE) > 20000:
            _SCORE_CACHE.clear()
        _SCORE_CACHE[key] = _score_detail(r)
    out = dict(_SCORE_CACHE[key])
    if card:
        out["card"] = propensity.model_card(data_loader.DATA_DIR)
    return out


def _score_detail(r: dict, card: bool = False) -> dict:
    stage = r.get("stage") or "Lead"
    out: dict = {"card": propensity.model_card(data_loader.DATA_DIR)} if card else {}
    if r.get("status") == "won" or stage == "Activated":
        out["final"] = "won"
        return out
    if r.get("status") == "lost":
        out["final"] = "lost"
        return out
    if r.get("origin") == "seed":
        ex = propensity.explain_seed(data_loader.DATA_DIR, r["lead_id"], stage)
    else:
        spec = profiles.spec_for(r.get("bt_key"), SEG_CODE.get(r.get("segment") or "", "micro"))
        lang = {v: k for k, v in propensity.LANG_NAME.items()}.get(r.get("language") or "English", "en")
        gs = {"Active": "active", "Cancelled": "cancelled", "Suspended": "suspended"}.get(r.get("gst_status") or "", "none")
        ex = {}
        propensity.score_profile(data_loader.DATA_DIR, {"city": r.get("city"), "employees": r.get("employees"), "num_sites": r.get("sites"),
                                                        "gstin_status": gs, "lang": lang}, spec, stage if stage in propensity.STAGES else "Needs assessed", ex)
    out.update(ex or {})
    return out


def rescore(lead_id: str):
    r = store.one("SELECT * FROM leads WHERE lead_id=?", (lead_id,))
    if not r:
        return
    sc = score_detail(r, card=False)
    p = sc.get("likelihood", _display_likelihood(r))
    store.x("UPDATE leads SET p_activate=? WHERE lead_id=?", (p, lead_id))


def _public(r: dict) -> dict:
    score = score_detail(r, card=False)
    bundle = store.loads(r.get("bundle"))
    done = store.loads(r.get("action_done"))
    part = store.partner(r.get("partner_id"))
    interest = [recommender.profiles.LABEL.get(p, p) for p in store.loads(r.get("interest"), [])]
    return {
        "lead_id": r["lead_id"], "live": r["origin"] == "live", "business": r["business"], "business_type": r["business_type"],
        "segment": r["segment"], "city": r["city"], "language": r["language"], "source": r["source"], "stage": r["stage"],
        "status": r["status"], "drop_reason": r["drop_reason"] if r["status"] == "lost" or (r["origin"] == "seed" and r["status"] != "won") else None,
        "likelihood": score["likelihood"] if "likelihood" in score else _display_likelihood(r), "score": score,
        "signals": store.loads(r["signals"], []), "action": store.loads(r["action"]), "action_done": done,
        "bundle": bundle, "interest": interest, "contact": r.get("contact"), "updated_at": r["updated_at"],
        "partner": {"name": part["name"], "phone": part["phone"], "kind": part["kind"]} if part else None,
        "employees": r["employees"], "sites": r["sites"], "gst_status": r["gst_status"],
        "setup": _setup(r["lead_id"]) if r["origin"] == "live" else None,
    }


def _setup(lead_id: str) -> dict | None:
    o = store.one("SELECT status, lines FROM orders WHERE lead_id=? AND status IN ('approved','in_progress','live') ORDER BY created_at DESC LIMIT 1", (lead_id,))
    if not o:
        return None
    lines = store.loads(o["lines"], [])
    return {"status": o["status"], "live": sum(1 for l in lines if l.get("state") == "live"), "total": len(lines)}


def _order_public(o: dict) -> dict:
    from udyam import orders
    full = orders.get(o["order_id"], admin=True)
    full["lead"] = None
    return full


LEAD_STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC review", "KYC complete", "Activated"]
LEAD_STATUSES = ("open", "review", "won", "lost")


def _mask(v: str | None, keep: int = 4) -> str | None:
    if not v:
        return v
    return "•" * max(0, len(v) - keep) + v[-keep:]


def lead_detail(lead_id: str) -> dict:
    from udyam import orders
    r = store.one("SELECT * FROM leads WHERE lead_id=?", (lead_id,))
    if not r:
        raise KeyError(lead_id)
    out = _public(r)
    out.update({
        "score": score_detail(r),
        "origin": r["origin"], "created_at": r["created_at"], "state": r.get("state"), "gstin": _mask(r.get("gstin")),
        "phone": r.get("phone"), "spend": r.get("spend"),
        "orders": [orders.get(o["order_id"], admin=True) for o in store.q("SELECT order_id FROM orders WHERE lead_id=? ORDER BY created_at DESC", (lead_id,))],
        "events": store.q("SELECT ts, kind, text, actor, order_id FROM events WHERE lead_id=? ORDER BY id DESC LIMIT 50", (lead_id,)),
    })
    return out


def update_lead(lead_id: str, stage: str | None = None, status: str | None = None, drop_reason: str | None = None,
                note: str | None = None, actor: str = "sales") -> dict:
    r = store.one("SELECT stage, status FROM leads WHERE lead_id=?", (lead_id,))
    if not r:
        raise KeyError(lead_id)
    fields: dict = {}
    changes = []
    if stage and stage != r["stage"]:
        if stage not in LEAD_STAGES:
            raise ValueError("unknown stage")
        if stage in ("KYC review", "KYC complete", "Activated"):
            raise ValueError("this stage is set by the order itself, after verification")
        if r["stage"] in LEAD_STAGES and LEAD_STAGES.index(stage) < LEAD_STAGES.index(r["stage"]):
            raise ValueError("a lead cannot move back a stage; mark it lost with a reason instead")
        fields["stage"] = stage
        changes.append(f"stage {r['stage']} → {stage}")
        if stage == "Activated" and not status:
            status = "won"
    if status and status != r["status"]:
        if status not in LEAD_STATUSES:
            raise ValueError("unknown status")
        fields["status"] = status
        changes.append(f"status {r['status']} → {status}")
    if drop_reason is not None and status == "lost":
        fields["drop_reason"] = drop_reason or None
    if not fields and not note:
        return lead_detail(lead_id)
    if fields:
        cols = ", ".join(f"{k}=?" for k in fields) + ", updated_at=?"
        store.x(f"UPDATE leads SET {cols} WHERE lead_id=?", (*fields.values(), time.time(), lead_id))
        rescore(lead_id)
    text = (", ".join(changes) if changes else "Note added") + (f" ({note})" if note else "")
    store.log("lead_update", f"{actor.capitalize()} updated the lead: {text}", lead_id, None, actor)
    return lead_detail(lead_id)


def lead_list(status: str = "open", live_only: bool = False, q: str | None = None, limit: int = 100) -> dict:
    where, args = [], []
    if status == "open":
        where.append("status IN ('open','review')")
    elif status in LEAD_STATUSES:
        where.append("status=?")
        args.append(status)
    if live_only:
        where.append("origin='live'")
    if q:
        where.append("(business LIKE ? OR city LIKE ? OR business_type LIKE ? OR lead_id LIKE ?)")
        args += [f"%{q}%"] * 4
    cond = " WHERE " + " AND ".join(where) if where else ""
    rows = store.q(f"SELECT * FROM leads{cond} ORDER BY p_activate DESC, updated_at DESC LIMIT ?", (*args, limit))
    return {"leads": [_public(r) for r in rows], "matched": store.one(f"SELECT COUNT(*) AS n FROM leads{cond}", tuple(args))["n"]}


def overview(limit: int = 60, stage: str | None = None, q: str | None = None, live_only: bool = False, status: str = "open") -> dict:
    where, args = [], []
    if status == "open":
        where.append("status IN ('open','review')")
    elif status in LEAD_STATUSES:
        where.append("status=?")
        args.append(status)
    if stage:
        where.append("stage=?")
        args.append(stage)
    if live_only:
        where.append("origin='live'")
    if q:
        where.append("(business LIKE ? OR city LIKE ? OR business_type LIKE ? OR lead_id LIKE ?)")
        args += [f"%{q}%"] * 4
    cond = " WHERE " + " AND ".join(where) if where else ""
    leads = store.q(f"SELECT * FROM leads{cond} ORDER BY p_activate DESC LIMIT ?", (*args, limit))
    matched = store.one(f"SELECT COUNT(*) AS n FROM leads{cond}", tuple(args))["n"]
    live_first = store.q("SELECT * FROM leads WHERE origin='live' ORDER BY updated_at DESC LIMIT 15")
    review = store.q("SELECT o.order_id FROM orders o WHERE o.status='kyc_review' ORDER BY o.updated_at")
    active = store.q("SELECT order_id FROM orders WHERE status IN ('approved','in_progress') ORDER BY updated_at DESC LIMIT 20")
    done = store.q("SELECT order_id FROM orders WHERE status='live' ORDER BY updated_at DESC LIMIT 5")
    awaiting = store.q("SELECT order_id FROM orders WHERE status IN ('awaiting_kyc','kyc_rejected') ORDER BY updated_at DESC LIMIT 10")
    call_next = store.q("SELECT * FROM leads WHERE status IN ('open','review') AND stage NOT IN ('Activated') ORDER BY p_activate DESC LIMIT 5")
    today = time.time() - 86400
    kpi = {
        "open_leads": store.one("SELECT COUNT(*) AS n FROM leads WHERE status IN ('open','review')")["n"],
        "live_today": store.one("SELECT COUNT(*) AS n FROM leads WHERE origin='live' AND created_at>?", (today,))["n"],
        "awaiting_review": len(review),
        "in_fulfilment": len(active),
        "activated": store.one("SELECT COUNT(*) AS n FROM orders WHERE status='live'")["n"],
        "quotes_open_value": store.one("SELECT COALESCE(SUM(json_extract(bundle,'$.monthly_ex')),0) AS v FROM leads WHERE status IN ('open','review') AND bundle IS NOT NULL AND stage IN ('Quote accepted','KYC complete','KYC review')")["v"],
    }
    events = store.q("SELECT e.ts, e.kind, e.text, e.actor, l.business FROM events e LEFT JOIN leads l ON l.lead_id=e.lead_id ORDER BY e.id DESC LIMIT 15")
    return {
        "ready": store.ready(), "kpi": kpi, "call_next": [_public(r) for r in call_next], "leads": [_public(r) for r in leads],
        "leads_matched": matched,
        "live_leads": [_public(r) for r in live_first],
        "review_queue": [_order_public(o) for o in review], "fulfilment": [_order_public(o) for o in active + done],
        "awaiting_customer": [_order_public(o) for o in awaiting], "activity": events,
        "model_card": propensity.model_card(data_loader.DATA_DIR),
    }


def do_action(lead_id: str, action_id: str, actor: str = "sales") -> dict:
    r = store.one("SELECT * FROM leads WHERE lead_id=?", (lead_id,))
    if not r:
        raise KeyError(lead_id)
    part = None
    if action_id in NEEDS_PARTNER:
        kind = "Field engineer" if action_id in ("priority_dispatch", "partner_visit") else "Channel partner"
        part = store.partner_for(r["city"], kind)
        if part:
            store.x("UPDATE leads SET partner_id=? WHERE lead_id=?", (part["partner_id"], lead_id))
    text = ACTION_RESULT.get(action_id, "Action recorded").format(partner=part["name"] if part else "")
    store.x("UPDATE leads SET action_done=?, updated_at=? WHERE lead_id=?",
            (store.dumps({"id": action_id, "text": text, "at": time.time()}), time.time(), lead_id))
    store.log("action", text, lead_id, None, actor)
    return _public(store.one("SELECT * FROM leads WHERE lead_id=?", (lead_id,)))
