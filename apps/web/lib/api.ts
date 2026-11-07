// Typed client for the core API.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Segment = "micro" | "prof" | "multi" | "mfg";
export type GstinStatus = "none" | "active" | "unverified" | "cancelled" | "suspended";

export interface Profile {
  segment: Segment;
  business_type?: string;
  employees: number;
  num_sites: number;
  city?: string;
  gstin_status: GstinStatus;
  current_tools?: string;
  needs?: string[];
}

export interface QuoteLine {
  product_id: string;
  name: string;
  unit: string;
  qty: number;
  unit_list_inr: string;
  line_monthly_list_inr: string;
  setup_inr: number;
  min_contract_months: number;
  install_days: number;
}

export interface Violation {
  rule: string;
  product: string | null;
  severity: "block" | "conditional" | "warn" | "advise";
  message: string;
  fix: string[];
}

export interface Quote {
  quote_id: string;
  monthly_inr: string;
  monthly_range_inr: [number, number];
  setup_total_inr: number;
  contract_months: number;
  activation_eta_days: number;
  per_item_eta_days: Record<string, number>;
  status: "ok" | "conditional" | "blocked";
  lines: QuoteLine[];
  violations: Violation[];
}

export interface AdvisorReply {
  text: string;
  quote_card: Quote | null;
  bundle: string | null;
  chips: string[];
  validator: string;
}

export interface Finding {
  code: string;
  severity: "HARD" | "REVIEW" | "INFO";
  message: string;
  customer_action: string | null;
}

export interface KycResult {
  case_id: string;
  business: string;
  verdict: "PASS" | "REVIEW" | "REJECT";
  findings: Finding[];
  mode: string;
  as_of: string;
}

export interface SuitableProduct {
  product_id: string;
  name: string;
  category: string;
  description: string;
  unit: string;
  price_inr: number;
  price_range_inr: [number, number];
  setup_inr: number;
  min_contract_months: number;
  install_days: number;
  requires_gstin: boolean;
  eligible: boolean;
  eligibility_note: string | null;
  in_recommended_bundle: boolean;
}

export interface SuitableResult {
  recommended_bundle: string;
  products: SuitableProduct[];
}

export interface KycExtract {
  ocr_available: boolean;
  message?: string;
  extracted?: { gstin: string; source: string };
  validation?: {
    format_ok: boolean;
    checksum_ok: boolean;
    state: string | null;
    in_registry: boolean;
    registry_status: string | null;
    legal_name: string | null;
  };
}

export interface KycCase {
  case_id: string;
  business: string;
  constitution: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  advisor: (session_id: string, profile?: Profile, text = "", lang = "en") =>
    post<AdvisorReply>("/api/v1/advisor/messages", { session_id, profile, text, lang }),
  suitable: (profile: Profile, categories: string[] = [], needs: string[] = []) =>
    post<SuitableResult>("/api/v1/catalogue/suitable", { profile, categories, needs }),
  quote: (profile: Profile, items: { product_id: string; qty: number }[], price_point = "list") =>
    post<Quote>("/api/v1/quotes", { profile, items, price_point }),
  kycCases: () => get<KycCase[]>("/api/v1/kyc/cases"),
  assess: (case_id: string) => post<KycResult>("/api/v1/kyc/assess", { case_id }),
  assessAll: () => get<KycResult[]>("/api/v1/kyc/assess-all"),
  kycExtract: (file: File): Promise<KycExtract> => {
    const fd = new FormData();
    fd.append("gst_certificate", file);
    return fetch(`${API_BASE}/api/v1/kyc/extract`, { method: "POST", body: fd }).then((r) => r.json());
  },
};

export function rupees(x: string | number): string {
  const n = typeof x === "string" ? parseFloat(x) : x;
  return "₹" + (Number.isInteger(n) ? n.toLocaleString("en-IN") : n.toLocaleString("en-IN", { minimumFractionDigits: 2 }));
}
