from __future__ import annotations
import functools, os, sys
import numpy as np
import pandas as pd

LEAKY = ["customer_follow_up_calls", "acquisition_cost_inr", "stage_reached", "drop_reason", "outcome", "bundle_products",
         "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months", "churned_within_6_months", "nps_score",
         "days_lead_to_activation"]
CAT = ["lead_source", "segment", "city_tier", "preferred_language", "annual_turnover_band", "current_internet",
       "current_provider", "business_type", "state", "gst_status", "udyam_type"]
NUM = ["log_emp", "num_sites", "log_spend", "has_gstin", "has_udyam", "gst_age_yrs"]
MIN_FREQ = 20
C_REG = 0.3

SEGMENT_NAME = {"micro": "Micro retail & services", "prof": "Professional offices",
                "multi": "Small multi-site businesses", "mfg": "Small manufacturers"}
LANG_NAME = {"en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "mr": "Marathi",
             "kn": "Kannada", "pa": "Punjabi"}

ACTIONS = {
    "Unreachable after 3 attempts": ("whatsapp_quote", "Send 1-click WhatsApp quote"),
    "Wrong or invalid number": ("verify_contact", "Verify contact through a partner"),
    "Owner had no time for a visit": ("remote_onboarding", "Offer video onboarding"),
    "Visit not scheduled by sales": ("partner_visit", "Assign a partner site visit"),
    "Locked in with current provider": ("switch_offer", "Send switch-over offer"),
    "Only wanted a mobile plan": ("bundle_upsell", "Offer mobile and fibre bundle"),
    "Price too high": ("revised_quote", "Send a revised quote"),
    "Competitor offered cheaper plan": ("revised_quote", "Send a price-match quote"),
    "Quote too complex to understand": ("whatsapp_quote", "Send a simplified quote on WhatsApp"),
    "Quote took too long to arrive": ("whatsapp_quote", "Send an instant quote"),
    "Installation delayed beyond 21 days": ("priority_dispatch", "Assign priority field dispatch"),
    "Missing GST or Udyam document": ("resolve_docs", "Request documents on WhatsApp"),
    "Found paperwork too long": ("assisted_kyc", "Offer assisted KYC by a partner"),
    "Customer cancelled before install": ("callback", "Call back with a retention offer"),
    "Authorised signatory not available": ("schedule_signatory", "Schedule e-sign with the signatory"),
    "Document details did not match": ("resolve_docs", "Fix the document mismatch with a partner"),
    "Site not feasible for fibre": ("alt_access", "Offer 5G AirFiber instead"),
    "First payment failed": ("payment_retry", "Send a payment link"),
    "Not interested on first call": ("nurture", "Add to nurture campaign"),
    "Decided to wait": ("nurture", "Schedule a follow-up in 30 days"),
}
DEFAULT_ACTION = ("callback", "Call back")


def features(L, G, U):
    L = L.merge(G[["gstin", "status", "registration_date"]], on="gstin", how="left") \
         .merge(U[["udyam_number", "enterprise_type"]], on="udyam_number", how="left")
    cd = pd.to_datetime(L.created_date)
    X = pd.DataFrame({c: L[c].astype(str) for c in CAT if c in L})
    X["gst_status"] = L.status.fillna("none")
    X["udyam_type"] = L.enterprise_type.fillna("none")
    X["log_emp"] = np.log1p(L.employee_count)
    X["num_sites"] = L.num_sites
    X["log_spend"] = np.log1p(L.monthly_telecom_spend_inr)
    X["has_gstin"] = (L.has_gstin == "Y").astype(int)
    X["has_udyam"] = (L.has_udyam == "Y").astype(int)
    X["gst_age_yrs"] = ((cd - pd.to_datetime(L.registration_date)).dt.days / 365).fillna(-1)
    return L, X


def rule_score(X):
    return (2 * X.has_gstin + 2 * (X.segment != "Micro retail & services")
            + X.lead_source.map({"Referral": 2, "Inbound call": 1}).fillna(0) + (X.annual_turnover_band != "< 40 lakh"))


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class Encoder:

    def fit(self, X):
        self.cats = {}
        for c in CAT:
            vc = X[c].value_counts()
            self.cats[c] = [v for v, n in vc.items() if n >= MIN_FREQ]
        self.mu = X[NUM].mean().values
        self.sd = X[NUM].std(ddof=0).replace(0, 1).values
        self.names = [(c, v) for c in CAT for v in self.cats[c] + ["__other__"]] + [(n, None) for n in NUM]
        return self

    def transform(self, X):
        cols = []
        for c in CAT:
            s = X[c].astype(str)
            known = self.cats[c]
            for v in known:
                cols.append((s == v).values.astype(float))
            cols.append((~s.isin(known)).values.astype(float))
        num = (X[NUM].values.astype(float) - self.mu) / self.sd
        return np.column_stack(cols + [num])


def _fit_logistic(Z, y, C=C_REG, iters=30):
    n, d = Z.shape
    A = np.hstack([np.ones((n, 1)), Z])
    w = np.zeros(d + 1)
    pen = np.eye(d + 1) / C
    pen[0, 0] = 0
    for _ in range(iters):
        p = _sigmoid(A @ w)
        g = A.T @ (p - y) + pen @ w
        H = A.T @ (A * (p * (1 - p) + 1e-9)[:, None]) + pen
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-7:
            break
    return w


class Model:
    def __init__(self, X, y):
        self.enc = Encoder().fit(X)
        Z = self.enc.transform(X)
        self.w = _fit_logistic(Z, y)
        self.zmean = Z.mean(axis=0)
        self.defaults = {c: X[c].mode().iloc[0] for c in CAT}
        self.defaults.update({n: float(X[n].median()) for n in NUM})
        self.by_segment = {s: g for s, g in X.groupby("segment")}

    def predict(self, X):
        return _sigmoid(self.enc.transform(X) @ self.w[1:] + self.w[0])

    def contributions(self, X):
        Z = self.enc.transform(X)
        delta = (Z - self.zmean) * self.w[1:]
        keys = []
        for c, v in self.enc.names:
            keys.append(c)
        out = pd.DataFrame(delta, columns=range(delta.shape[1]))
        agg = {}
        for j, c in enumerate(keys):
            agg.setdefault(c, []).append(j)
        return {c: delta[:, idx].sum(axis=1) for c, idx in agg.items()}


def oof_predict(X, y, folds=5, seed=42):
    rng = np.random.RandomState(seed)
    idx = np.arange(len(y))
    pos, neg = idx[y == 1], idx[y == 0]
    rng.shuffle(pos)
    rng.shuffle(neg)
    fold_of = np.zeros(len(y), dtype=int)
    for part in (pos, neg):
        for k, i in enumerate(part):
            fold_of[i] = k % folds
    out = np.zeros(len(y))
    for f in range(folds):
        tr, te = fold_of != f, fold_of == f
        out[te] = Model(X[tr].reset_index(drop=True), y[tr]).predict(X[te].reset_index(drop=True))
    return out


def roc_auc(y, p):
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


SOURCE_UP = {"Referral": "Referred by an existing customer", "Channel partner": "Introduced by a channel partner",
             "Inbound call": "Called us directly", "Field sales": "Met in person by field sales",
             "Website form": "Asked for a quote on the website", "WhatsApp campaign": "Responded to a WhatsApp campaign"}
SOURCE_DOWN = {"Referral": "Referral that has not converted", "Channel partner": "Partner lead with little engagement",
               "Inbound call": "Inbound call, no follow-through", "Field sales": "Cold field visit",
               "Website form": "Website enquiry, low intent", "WhatsApp campaign": "Campaign response, low intent"}
GST_UP = {"Active": "Active GSTIN verified"}
GST_DOWN = {"Cancelled": "GSTIN is cancelled, needs a fresh registration", "Suspended": "GSTIN is suspended",
            "none": "No GSTIN yet, which limits product choice", "Active": "GSTIN active but little else going for it"}


def signal_text(feat: str, value, up: bool) -> str | None:
    v = str(value)
    if feat == "lead_source":
        return (SOURCE_UP if up else SOURCE_DOWN).get(v)
    if feat == "gst_status":
        return (GST_UP if up else GST_DOWN).get(v)
    if feat == "business_type":
        return f"{v} owners convert well" if up else f"{v} owners convert slowly"
    if feat == "annual_turnover_band":
        return f"Turnover band {v}, a good fit" if up else f"Turnover band {v}, smaller budget"
    if feat == "current_internet":
        return f"Currently on {v.lower()}, ready to upgrade" if up else f"Currently on {v.lower()}, less urgency"
    if feat == "current_provider":
        return f"Already with {v}, easy to cross-sell" if up else f"Tied to {v}"
    if feat == "udyam_type":
        if v == "none":
            return None if up else "No Udyam registration on file"
        return f"Registered as a {v.lower()} enterprise" if up else f"Registered as a {v.lower()} enterprise, lower spend"
    if feat == "city_tier":
        return f"Tier {v} city, full catalogue available" if up else f"Tier {v} city, narrower catalogue"
    if feat == "state":
        return f"Strong conversion in {v}" if up else f"Slower conversion in {v}"
    if feat == "preferred_language":
        return f"Prefers {v}, well served by the advisor" if up else f"Prefers {v}, needs a local-language follow-up"
    if feat == "log_emp":
        return "Larger team than most leads" if up else "Very small team"
    if feat == "num_sites":
        return "Multiple locations to connect" if up else "Single location"
    if feat == "log_spend":
        return "Already spends heavily on telecom" if up else "Low current telecom spend"
    if feat == "gst_age_yrs":
        return "Established, long-registered business" if up else "Recently registered business"
    return None


SKIP = {"has_gstin", "has_udyam", "segment"}


def odds_pct(c: float) -> int:
    return int(round((float(np.exp(c)) - 1) * 100))


def reasons(contrib: dict, X, i, k=3):
    """Top signals for row i as {text, tone, odds_pct}."""
    scored = []
    for feat, arr in contrib.items():
        if feat in SKIP:
            continue
        c = float(arr[i])
        if abs(c) < 0.02:
            continue
        text = signal_text(feat, X.iloc[i][feat], c > 0)
        if text:
            scored.append((abs(c), {"text": text, "tone": "good" if c > 0 else "warn", "odds_pct": odds_pct(c), "feature": feat}))
    scored.sort(key=lambda t: -t[0])
    return [s for _, s in scored[:k]]


FEATURE_NAME = {"lead_source": "Lead source", "gst_status": "GSTIN status", "has_gstin": "GSTIN present", "segment": "Segment",
                "city_tier": "City tier", "annual_turnover_band": "Turnover band", "business_type": "Business type",
                "preferred_language": "Language", "current_internet": "Current internet", "current_provider": "Current provider",
                "state": "State", "udyam_type": "Udyam registration", "has_udyam": "Udyam present", "log_emp": "Employees",
                "num_sites": "Locations", "log_spend": "Telecom spend", "gst_age_yrs": "Years since GST registration"}


@functools.lru_cache(maxsize=1)
def model_card(data_dir: str) -> dict:
    L, X, y, model, p_oof = _bundle(data_dir)
    base, rates = _base_and_rates(data_dir)
    top = np.argsort(-p_oof)[: len(y) // 10]
    gst = X.has_gstin == 1
    contrib = model.contributions(X)
    spread = {f: float(np.percentile(a, 90) - np.percentile(a, 10)) for f, a in contrib.items()}
    weights = sorted(({"feature": FEATURE_NAME.get(f, f), "odds_swing_pct": odds_pct(v)} for f, v in spread.items() if v > 0.01),
                     key=lambda w: -w["odds_swing_pct"])[:8]
    return {"model": "L2-regularised logistic regression", "trained_on": "smb_leads.csv", "rows": int(len(y)),
            "activated": int(y.sum()), "base_rate": round(float(y.mean()), 4),
            "auc_held_out": round(roc_auc(y, p_oof), 3), "lift_top_decile": round(float(y[top].mean() / y.mean()), 2),
            "gstin_activation": {"with": round(float(y[gst.values].mean()), 3), "without": round(float(y[~gst.values].mean()), 3)},
            "stage_rates": {k: round(v, 3) for k, v in rates.items()},
            "score_formula": "likelihood = odds(activation rate of leads that reached this stage) x model lift, lift = (p_model / average p)^0.8, capped 0.4-4",
            "weights": weights,
            "excluded_as_leaky": LEAKY}


def explain(data_dir: str, p_model: float, stage: str, terms: list[dict]) -> dict:
    base, rates = _base_and_rates(data_dir)
    r = rates.get(stage, rates["Lead"])
    lift = min(4.0, max(0.4, (p_model / base) ** 0.8))
    return {"stage": stage, "stage_rate": round(r, 4), "p_model": round(p_model, 4), "avg_p": round(base, 4),
            "lift": round(lift, 2), "likelihood": likelihood(p_model, stage, base, rates), "terms": terms}


@functools.lru_cache(maxsize=1)
def _seed_index(data_dir: str):
    L, X, y, model, p_oof = _bundle(data_dir)
    return {lid: i for i, lid in enumerate(L.lead_id)}, model.contributions(X)


def explain_seed(data_dir: str, lead_id: str, stage: str) -> dict | None:
    L, X, y, model, p_oof = _bundle(data_dir)
    idx, contrib = _seed_index(data_dir)
    i = idx.get(lead_id)
    if i is None:
        return None
    return explain(data_dir, float(p_oof[i]), stage, reasons(contrib, X, i, k=5))


STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC review", "KYC complete", "Activated"]
_STAGE_ALIAS = {"KYC review": "KYC complete"}


def stage_rates(L) -> dict:
    order = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
    idx = L.stage_reached.map({s: i for i, s in enumerate(order)})
    done = (L.outcome == "Activated").values
    out = {}
    for i, s in enumerate(order[:-1]):
        reached = (idx >= i).values
        out[s] = float(done[reached].sum() / max(1, reached.sum()))
    out["KYC review"] = out["KYC complete"]
    return out


def likelihood(p_model: float, stage: str, base: float, rates: dict) -> float:
    lift = min(4.0, max(0.4, (p_model / base) ** 0.8))
    r = min(0.97, max(0.01, rates.get(stage, rates["Lead"])))
    odds = r / (1 - r) * lift
    return round(float(min(0.92, max(0.01, odds / (1 + odds)))), 4)


@functools.lru_cache(maxsize=1)
def _bundle(data_dir: str):
    L = pd.read_csv(f"{data_dir}/smb_leads.csv")
    G = pd.read_csv(f"{data_dir}/mock_gstin_registry.csv", dtype=str)
    U = pd.read_csv(f"{data_dir}/mock_udyam_registry.csv", dtype=str)
    L, X = features(L, G, U)
    y = (L.outcome == "Activated").astype(int).values
    model = Model(X, y)
    p_oof = oof_predict(X, y)
    return L, X, y, model, p_oof


@functools.lru_cache(maxsize=4)
def _base_and_rates(data_dir: str):
    L, X, y, model, p_oof = _bundle(data_dir)
    return float(p_oof.mean()), stage_rates(L)


def seed_leads(data_dir: str) -> list[dict]:
    L, X, y, model, p_oof = _bundle(data_dir)
    contrib = model.contributions(X)
    base, rates = _base_and_rates(data_dir)
    out = []
    for i in np.where(y == 0)[0]:
        r = L.iloc[i]
        reason = r.get("drop_reason") if pd.notna(r.get("drop_reason")) else None
        out.append({
            "lead_id": r["lead_id"], "business": r.get("business_name"), "business_type": r.get("business_type"),
            "segment": r.get("segment"), "city": r.get("city"), "state": r.get("state"), "language": r.get("preferred_language"),
            "source": r.get("lead_source"), "stage": r.get("stage_reached"), "drop_reason": reason,
            "employees": int(r.get("employee_count")), "sites": int(r.get("num_sites")),
            "gstin": r.get("gstin") if pd.notna(r.get("gstin")) else None,
            "gst_status": X.iloc[i]["gst_status"], "contact": r.get("contact_name"),
            "interest": [p for p in str(r.get("products_of_interest") or "").split(";") if p],
            "spend": float(r["monthly_telecom_spend_inr"]) if pd.notna(r.get("monthly_telecom_spend_inr")) else None,
            "created": str(r.get("created_date")), "p_activate": likelihood(float(p_oof[i]), r.get("stage_reached"), base, rates),
            "p_model": round(float(p_oof[i]), 4),
            "signals": reasons(contrib, X, i), "action": action_for(reason, r.get("stage_reached")),
        })
    return out


def won_leads(data_dir: str) -> list[dict]:
    L, X, y, model, p_oof = _bundle(data_dir)
    contrib = model.contributions(X)
    out = []
    for i in np.where(y == 1)[0]:
        r = L.iloc[i]
        items = [(x.split("x")[0], int(x.split("x")[1])) for x in str(r.get("bundle_products") or "").split(";") if "x" in x]
        out.append({
            "lead_id": r["lead_id"], "business": r.get("business_name"), "business_type": r.get("business_type"),
            "segment": r.get("segment"), "city": r.get("city"), "state": r.get("state"), "language": r.get("preferred_language"),
            "source": r.get("lead_source"), "employees": int(r.get("employee_count")), "sites": int(r.get("num_sites")),
            "gstin": r.get("gstin") if pd.notna(r.get("gstin")) else None, "gst_status": X.iloc[i]["gst_status"],
            "contact": r.get("contact_name"), "items": items,
            "monthly": float(r["monthly_bundle_value_inr"]) if pd.notna(r.get("monthly_bundle_value_inr")) else 0.0,
            "setup": float(r["one_time_setup_inr"]) if pd.notna(r.get("one_time_setup_inr")) else 0.0,
            "contract": int(r["contract_months"]) if pd.notna(r.get("contract_months")) else 12,
            "spend": float(r["monthly_telecom_spend_inr"]) if pd.notna(r.get("monthly_telecom_spend_inr")) else None,
            "signals": reasons(contrib, X, i),
        })
    return out


def action_for(drop_reason, stage=None) -> dict:
    a = ACTIONS.get(drop_reason, DEFAULT_ACTION)
    return {"id": a[0], "label": a[1]}


def score_profile(data_dir: str, profile: dict, spec, stage: str = "Needs assessed", explain_out: dict | None = None) -> tuple[float, list[dict]]:
    """Score a live lead from what the customer told us."""
    L, X, y, model, _ = _bundle(data_dir)
    seg = SEGMENT_NAME.get(spec.segment, "Micro retail & services")
    pool = X[X.segment == seg]
    base = {c: (pool[c].mode().iloc[0] if len(pool) else model.defaults[c]) for c in CAT}
    base.update({n: float(pool[n].median()) if len(pool) else model.defaults[n] for n in NUM})
    base["lead_source"] = "Website form"
    base["segment"] = seg
    btype = spec.data_types[0] if spec.data_types else (pool.business_type.mode().iloc[0] if len(pool) else model.defaults["business_type"])
    base["business_type"] = btype
    city = (profile.get("city") or "").strip().title()
    row = L[L.city == city]
    if len(row):
        base["state"] = str(row.iloc[0]["state"])
        base["city_tier"] = str(row.iloc[0]["city_tier"])
    base["preferred_language"] = LANG_NAME.get(profile.get("lang", "en"), "English")
    gs = (profile.get("gstin_status") or "none").lower()
    base["gst_status"] = {"active": "Active", "unverified": "Active", "cancelled": "Cancelled", "suspended": "Suspended"}.get(gs, "none")
    base["has_gstin"] = 0 if gs == "none" else 1
    base["log_emp"] = float(np.log1p(max(1, int(profile.get("employees") or 1))))
    base["num_sites"] = float(max(1, int(profile.get("num_sites") or 1)))
    df = pd.DataFrame([base])
    p = float(model.predict(df)[0])
    contrib = model.contributions(df)
    avg, rates = _base_and_rates(data_dir)
    if explain_out is not None:
        explain_out.update(explain(data_dir, p, stage, reasons(contrib, df, 0, k=5)))
    return likelihood(p, stage, avg, rates), reasons(contrib, df, 0)


if __name__ == "__main__":
    data_dir = sys.argv[1]
    L, X, y, model, p_oof = _bundle(data_dir)
    top = np.argsort(-p_oof)[: len(y) // 10]
    rule = rule_score(X).values + np.random.RandomState(0).rand(len(X)) * 0.01
    print(f"held-out ROC-AUC {roc_auc(y, p_oof):.3f}, lift@10% {y[top].mean() / y.mean():.2f}, rule baseline AUC {roc_auc(y, rule):.3f}")
