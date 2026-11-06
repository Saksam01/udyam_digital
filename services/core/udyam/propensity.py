"""Lead propensity model with a rule score and reason codes."""

import sys, numpy as np, pandas as pd
from functools import lru_cache
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score

LEAKY = ["customer_follow_up_calls", "acquisition_cost_inr", "stage_reached", "drop_reason", "outcome", "bundle_products",
         "monthly_bundle_value_inr", "one_time_setup_inr", "contract_months", "churned_within_6_months", "nps_score",
         "days_lead_to_activation"]
CAT = ["lead_source", "segment", "city_tier", "preferred_language", "annual_turnover_band", "current_internet",
       "current_provider", "business_type", "state", "gst_status", "udyam_type"]
NUM = ["log_emp", "num_sites", "log_spend", "has_gstin", "has_udyam", "gst_age_yrs"]

def features(L, G, U):
    L = L.merge(G[["gstin", "status", "registration_date"]], on="gstin", how="left") \
         .merge(U[["udyam_number", "enterprise_type"]], on="udyam_number", how="left")
    cd = pd.to_datetime(L.created_date)
    X = pd.DataFrame({c: L[c].astype(str) for c in CAT if c in L})
    X["gst_status"] = L.status.fillna("none"); X["udyam_type"] = L.enterprise_type.fillna("none")
    X["log_emp"] = np.log1p(L.employee_count); X["num_sites"] = L.num_sites
    X["log_spend"] = np.log1p(L.monthly_telecom_spend_inr)
    X["has_gstin"] = (L.has_gstin == "Y").astype(int); X["has_udyam"] = (L.has_udyam == "Y").astype(int)
    X["gst_age_yrs"] = ((cd - pd.to_datetime(L.registration_date)).dt.days / 365).fillna(-1)
    return L, X

def rule_score(X):
    return (2 * X.has_gstin + 2 * (X.segment != "Micro retail & services")
            + X.lead_source.map({"Referral": 2, "Inbound call": 1}).fillna(0) + (X.annual_turnover_band != "< 40 lakh"))

def model():
    pre = ColumnTransformer([("c", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CAT), ("n", StandardScaler(), NUM)])
    return make_pipeline(pre, LogisticRegression(C=0.3, max_iter=3000))

def reason_codes(fitted, X, k=3):
    pre, lr = fitted[0], fitted[-1]; Z = pre.transform(X); Z = Z.toarray() if hasattr(Z, "toarray") else Z
    contrib = Z * lr.coef_[0]; names = pre.get_feature_names_out()
    out = []
    for row in contrib:
        idx = np.argsort(-np.abs(row))[:k]
        out.append("; ".join(f"{'+' if row[i] > 0 else '-'} {names[i].split('__')[1]}" for i in idx))
    return out

@lru_cache(maxsize=1)
def rank_unclosed(data_dir: str):
    """Leads the advisor could not close, ranked by how likely they are to activate if called."""
    L = pd.read_csv(f"{data_dir}/smb_leads.csv")
    G = pd.read_csv(f"{data_dir}/mock_gstin_registry.csv", dtype=str)
    U = pd.read_csv(f"{data_dir}/mock_udyam_registry.csv", dtype=str)
    L, X = features(L, G, U)
    y = (L.outcome == "Activated").astype(int).values
    fitted = model().fit(X, y)
    L["p_activate"] = fitted.predict_proba(X)[:, 1]
    L["rule_points"] = rule_score(X).values
    L["reasons"] = reason_codes(fitted, X)
    un = L[L.outcome != "Activated"].sort_values("p_activate", ascending=False)
    out = []
    for _, r in un.iterrows():
        out.append({
            "lead_id": r["lead_id"],
            "business": r.get("business_name"),
            "segment": r.get("segment"),
            "city": r.get("city"),
            "language": r.get("preferred_language"),
            "stage": r.get("stage_reached"),
            "drop_reason": r.get("drop_reason") if pd.notna(r.get("drop_reason")) else None,
            "p_activate": round(float(r["p_activate"]), 3),
            "rule_points": int(r["rule_points"]),
            "reasons": r["reasons"],
            "monthly_spend": int(r["monthly_telecom_spend_inr"]) if pd.notna(r.get("monthly_telecom_spend_inr")) else None,
        })
    return out


if __name__ == "__main__":
    L, G, U = pd.read_csv(sys.argv[1]), pd.read_csv(sys.argv[2], dtype=str), pd.read_csv(sys.argv[3], dtype=str)
    L, X = features(L, G, U); y = (L.outcome == "Activated").astype(int).values
    skf = StratifiedKFold(5, shuffle=True, random_state=42)
    p = cross_val_predict(model(), X, y, cv=skf, method="predict_proba")[:, 1]
    o = np.argsort(-p); top = o[: len(y) // 10]
    print(f"LR  ROC-AUC {roc_auc_score(y, p):.3f}  PR-AUC {average_precision_score(y, p):.3f}  lift@10% {y[top].mean() / y.mean():.2f}")
    r = rule_score(X).values + np.random.RandomState(0).rand(len(X)) * 0.01
    print(f"Rule ROC-AUC {roc_auc_score(y, r):.3f}")
    cal = CalibratedClassifierCV(model(), method="isotonic", cv=5).fit(X, y)
    fitted = model().fit(X, y)
    L["p_activate"] = cal.predict_proba(X)[:, 1]; L["rule_points"] = rule_score(X); L["reasons"] = reason_codes(fitted, X)
    print(L[["lead_id", "segment", "lead_source", "p_activate", "rule_points", "reasons"]].sort_values("p_activate", ascending=False).head(5).to_string(index=False))
