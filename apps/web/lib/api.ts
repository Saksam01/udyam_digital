export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Segment = "micro" | "prof" | "multi" | "mfg";
export type GstinStatus = "none" | "active" | "unverified" | "cancelled" | "suspended";

export interface Profile {
  segment: Segment;
  business_type?: string;
  need_tags?: string[];
  employees: number;
  num_sites: number;
  city?: string;
  gstin_status: GstinStatus;
  current_tools?: string;
  needs?: string[];
  categories?: string[];
}

export interface Tax {
  rate_pct: number;
  monthly_ex_gst: string;
  monthly_gst: string;
  monthly_incl_gst: string;
  setup_ex_gst: string;
  setup_gst: string;
  setup_incl_gst: string;
  itc_monthly: string;
  itc_eligible: boolean;
}

export interface QuoteLine {
  product_id: string;
  label?: string;
  spec?: string;
  category?: string;
  kind?: "digital" | "field";
  note?: string;
  popularity?: number;
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
  bundle_name?: string;
  tax?: Tax;
  lines: QuoteLine[];
  violations: Violation[];
}

export interface AdvisorReply {
  text: string;
  quote_card: Quote | null;
  bundle: string | null;
  chips: string[];
  validator: string;
  profile?: Profile;
  lead_id?: string;
}

export type OrderStatus = "awaiting_kyc" | "kyc_review" | "kyc_rejected" | "approved" | "in_progress" | "live" | "cancelled";

export interface OrderLine {
  product_id: string;
  label: string;
  spec: string;
  qty: number;
  kind: "digital" | "field";
  state: "queued" | "scheduled" | "in_progress" | "live";
  install_days: number;
  visit_ts: number | null;
  live_ts: number | null;
  status_text: string;
}

export interface Engineer {
  name: string;
  phone: string;
  role: string;
  city: string;
}

export interface CustomerFinding {
  code: string;
  kind: "check" | "fix" | "info";
  text: string;
  action: string | null;
}

export interface ChecklistItem {
  id: string;
  label: string;
  state: "ok" | "check" | "fail";
}

export interface OrderKyc {
  verdict: "PASS" | "REVIEW" | "REJECT";
  findings: CustomerFinding[];
  checklist: ChecklistItem[];
  summary: Record<string, string>;
  erased?: boolean;
}

export interface Evidence {
  doc: string;
  field: string;
  extracted: string | number | null;
  reference_source: string;
  reference: string | number | null;
  score: number | null;
  threshold: number | null;
  distinctive_token_match?: boolean | null;
  slot?: string;
  box?: [number, number, number, number];
  page_size?: [number, number];
}
export interface TraceItem {
  code: string;
  doc: string;
  check: string;
  result: "pass" | "fail" | "review" | "info";
  evidence?: Evidence;
}
export interface Thresholds {
  pass: number;
  review: number;
  method: string;
}

export interface ConsentArtifact {
  consent_id: string;
  order_id: string;
  timestamp_utc: string;
  purpose: string;
  legal_basis: string;
  data_categories: string[];
  not_used_for: string[];
  processing: string[];
  aadhaar_masking: string;
  raw_document_retention: string;
  data_retention_days: number;
  withdrawal_endpoint: string;
  grievance_contact: string;
  artifact_sha256: string;
  status: "active" | "withdrawn";
  integrity_ok?: boolean;
  withdrawn_at_utc?: string | null;
}

export interface OrderEvent {
  ts: number;
  kind: string;
  text: string;
}

export interface Order {
  order_id: string;
  lead_id: string;
  status: OrderStatus;
  headline: string;
  business: string | null;
  city?: string | null;
  created_at: number;
  updated_at: number;
  bundle_name: string | null;
  tax: Tax;
  setup_total_inr: number;
  contract_months: number;
  activation_eta_days: number;
  lines: OrderLine[];
  kyc: OrderKyc | null;
  engineer: Engineer | null;
  assist: Engineer | null;
  events: OrderEvent[];
  live_count: number;
  total_count: number;
}

export interface KycUploadResponse {
  consent_id?: string;
  status: "verdict" | "incomplete" | "unavailable";
  verdict?: "PASS" | "REVIEW" | "REJECT";
  findings?: CustomerFinding[];
  checklist?: ChecklistItem[];
  needs?: { slot: string; text: string; doc?: string | null; kind?: string }[];
  message?: string;
  order: Order;
}

export interface AdminLead {
  lead_id: string;
  live: boolean;
  business: string;
  business_type: string;
  segment: string;
  city: string;
  language: string;
  source: string;
  stage: string;
  status: string;
  drop_reason: string | null;
  likelihood: number;
  signals: { text: string; tone: "good" | "warn" | "bad"; odds_pct?: number }[];
  score?: LeadScore;
  setup?: { status: string; live: number; total: number } | null;
  action: { id: string; label: string } | null;
  action_done: { id: string; text: string; at: number } | null;
  bundle: {
    name: string;
    monthly_ex: string;
    monthly_incl: string;
    setup: number;
    contract: number;
    lines: { label: string; spec: string; qty: number; monthly: string }[];
    dropped?: { label: string; monthly: string }[];
    added?: string[];
    recommended_monthly?: string | null;
  } | null;
  interest: string[];
  contact: string | null;
  updated_at: number;
  partner: { name: string; phone: string; kind: string } | null;
  employees: number | null;
  sites: number | null;
  gst_status: string | null;
}

export interface LeadScore {
  final?: "won" | "lost";
  stage?: string;
  stage_rate?: number;
  p_model?: number;
  avg_p?: number;
  lift?: number;
  likelihood?: number;
  terms?: { text: string; tone: "good" | "warn"; odds_pct: number; feature: string }[];
  card?: ModelCard;
}
export interface ModelCard {
  model: string;
  trained_on: string;
  rows: number;
  activated: number;
  base_rate: number;
  auc_held_out: number;
  lift_top_decile: number;
  gstin_activation: { with: number; without: number };
  stage_rates: Record<string, number>;
  score_formula: string;
  weights: { feature: string; odds_swing_pct: number }[];
}

export interface AdminOrder extends Order {
  kyc:
    | (OrderKyc & {
        raw_findings?: { code: string; severity: string; message: string }[];
        review_note?: string;
        pages_held?: number;
        declared?: string | null;
        trace?: TraceItem[];
        thresholds?: Thresholds;
        documents?: Record<string, { doctype: string; size: [number, number] }>;
        masking?: { fields: number; image_regions: number } | null;
        source?: string;
      })
    | null;
  vault?: { stored_at: number; purge_after: number; slots: Record<string, { size: [number, number] }> } | null;
  consent?: ConsentArtifact | null;
}

export interface AdminOverview {
  ready: boolean;
  kpi: { open_leads: number; live_today: number; awaiting_review: number; in_fulfilment: number; activated: number; quotes_open_value: number };
  call_next: AdminLead[];
  leads: AdminLead[];
  live_leads: AdminLead[];
  review_queue: AdminOrder[];
  fulfilment: AdminOrder[];
  awaiting_customer: AdminOrder[];
  leads_matched?: number;
  activity: { ts: number; kind: string; text: string; actor: string; business: string | null }[];
  model_card?: ModelCard;
}

export interface Finding {
  code: string;
  severity: "HARD" | "REVIEW" | "INFO";
  message: string;
  customer_action: string | null;
  evidence?: Evidence | null;
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
  label?: string;
  recommended_for_you?: boolean;
  popularity_pct?: number;
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
  requires_one_of?: string[];
  eligible: boolean;
  eligibility_note: string | null;
  in_recommended_bundle: boolean;
}

export interface Understood {
  business_type?: string;
  segment?: Segment;
  employees?: number;
  num_sites?: number;
  city?: string;
  gstin_status?: GstinStatus;
  need_tags?: string[];
  need_groups?: string[];
}

export interface SuitableResult {
  recommended_bundle: string;
  products: SuitableProduct[];
}

export interface KycCase {
  case_id: string;
  business: string;
  constitution: string;
  documents?: string[];
}

export interface KycSample extends KycCase {
  verdict: "PASS" | "REVIEW" | "REJECT";
  findings: Finding[];
  documents: string[];
  trace?: TraceItem[];
  thresholds?: Thresholds;
}

export interface KycOcrResult {
  case_id: string;
  status: "verdict" | "incomplete" | "unavailable";
  verdict?: "PASS" | "REVIEW" | "REJECT";
  raw_findings?: { code: string; severity: string; message: string }[];
  checklist?: ChecklistItem[];
  summary?: Record<string, string>;
  needs?: { slot: string; text: string; doc?: string | null; kind?: string }[];
  message?: string;
  seconds: number;
  trace?: TraceItem[];
  thresholds?: Thresholds;
  masking?: { fields: number; image_regions: number };
}

export interface AdminLeadDetail extends AdminLead {
  score?: LeadScore;
  origin: string;
  created_at: number;
  gstin: string | null;
  phone: string | null;
  orders: AdminOrder[];
  events: { ts: number; kind: string; text: string; actor: string; order_id: string | null }[];
}

export type OrderAction = "approve" | "reject" | "mark_live" | "cancel";
export const LEAD_STAGES = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC review", "KYC complete", "Activated"];
export const LEAD_STATUSES = ["open", "review", "won", "lost"] as const;

export const kycDocUrl = (caseId: string, slot: string, token = "") =>
  `${API_BASE}/api/v1/kyc/cases/${caseId}/docs/${slot}${token ? `?t=${token}` : ""}`;
export const samplePageUrl = (token: string, caseId: string, slot: string, v = 0) =>
  `${API_BASE}/api/v1/admin/kyc/samples/${caseId}/pages/${slot}?t=${token}&v=${v}`;
export const vaultPageUrl = (token: string, orderId: string, slot: string) => `${API_BASE}/api/v1/verify/orders/${orderId}/pages/${slot}?t=${token}`;
export type Role = "sales" | "verifier";

export function subscribe(
  path: string,
  onChange: (events: { kind: string; order_id: string | null; lead_id: string | null }[]) => void,
): () => void {
  if (typeof window === "undefined" || typeof EventSource === "undefined") return () => {};
  let es: EventSource | null = null;
  let closed = false;
  let retry: ReturnType<typeof setTimeout> | null = null;
  const open = () => {
    if (closed) return;
    es = new EventSource(`${API_BASE}${path}`);
    es.addEventListener("change", (ev) => {
      try {
        onChange(JSON.parse((ev as MessageEvent).data));
      } catch {
        /* ignore malformed */
      }
    });
    es.onerror = () => {
      es?.close();
      if (!closed)
        retry = setTimeout(() => {
          onChange([]);
          open();
        }, 1500);
    };
  };
  open();
  return () => {
    closed = true;
    if (retry) clearTimeout(retry);
    es?.close();
  };
}

async function postStrict<T>(path: string, body: unknown, extra?: Record<string, string>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json", ...(extra ?? {}) }, body: JSON.stringify(body) });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).detail ?? "";
    } catch {
      /* not json */
    }
    const err = new Error(detail || `${path} failed: ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

const ORDER_KEYS = "udyam_keys";
function loadKeys(): Record<string, string> {
  try {
    return JSON.parse(window.localStorage.getItem(ORDER_KEYS) ?? "{}");
  } catch {
    return {};
  }
}
export function rememberOrderKey(id: string, key: string) {
  try {
    window.localStorage.setItem(ORDER_KEYS, JSON.stringify({ ...loadKeys(), [id]: key }));
  } catch {
    /* storage unavailable */
  }
}
export function orderKey(id: string): string {
  return typeof window === "undefined" ? "" : loadKeys()[id] ?? "";
}
const ok = (id: string) => ({ "X-Order-Key": orderKey(id) });

async function post<T>(path: string, body: unknown, token?: string, extra?: Record<string, string>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(extra ?? {}) },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function get<T>(path: string, token?: string, extra?: Record<string, string>): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(extra ?? {}) } });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  advisor: (session_id: string, profile?: Profile, text = "", lang = "en", business?: string) =>
    post<AdvisorReply>("/api/v1/advisor/messages", { session_id, profile, text, lang, business }),
  understand: (session_id: string, text: string, lang = "en") =>
    post<Understood>("/api/v1/advisor/understand", { session_id, text, lang }),
  resume: (ref: string, code: string) =>
    postStrict<Order & { access_key?: string }>("/api/v1/orders/resume", { ref, code }).then((o) => {
      if (o.access_key) rememberOrderKey(o.order_id, o.access_key);
      return o;
    }),
  savePhone: (id: string, phone: string) => postStrict<{ ok: boolean }>(`/api/v1/orders/${id}/phone`, { phone }, ok(id)),
  suitable: (profile: Profile, categories: string[] = [], needs: string[] = []) =>
    post<SuitableResult>("/api/v1/catalogue/suitable", { profile, categories, needs }),
  quote: (profile: Profile, items: { product_id: string; qty: number }[], price_point = "list") =>
    post<Quote>("/api/v1/quotes", { profile, items, price_point }),
  kycCases: () => get<KycCase[]>("/api/v1/kyc/cases"),
  assess: (case_id: string) => post<KycResult>("/api/v1/kyc/assess", { case_id }),
  assessAll: () => get<KycResult[]>("/api/v1/kyc/assess-all"),
  createOrder: (body: {
    profile: Profile;
    items: { product_id: string; qty: number }[];
    business?: string;
    contact?: string;
    lead_id?: string;
    session_id: string;
    lang: string;
  }) =>
    postStrict<Order & { access_key?: string; resume_code?: string }>("/api/v1/orders", body).then((o) => {
      if (o.access_key) rememberOrderKey(o.order_id, o.access_key);
      return o;
    }),
  order: (id: string) => get<Order>(`/api/v1/orders/${id}`, undefined, ok(id)),
  assist: (id: string) => post<Order>(`/api/v1/orders/${id}/assist`, {}, undefined, ok(id)),
  consent: (id: string, lang: string) => post<ConsentArtifact>(`/api/v1/orders/${id}/consent?lang=${lang}`, {}, undefined, ok(id)),
  consentGet: (id: string, cid: string) => get<ConsentArtifact>(`/api/v1/consent/${cid}`, undefined, ok(id)),
  consentWithdraw: (id: string, cid: string) => post<ConsentArtifact>("/api/v1/consent/withdraw", { consent_id: cid }, undefined, ok(id)),
  kycUpload: async (id: string, files: Record<string, File>, consentId: string): Promise<KycUploadResponse> => {
    const fd = new FormData();
    fd.append("consent_id", consentId);
    for (const [slot, f] of Object.entries(files)) fd.append(slot, f);
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 150000);
    try {
      const res = await fetch(`${API_BASE}/api/v1/orders/${id}/kyc`, { method: "POST", body: fd, headers: ok(id), signal: ctl.signal });
      if (!res.ok) throw Object.assign(new Error(`kyc failed: ${res.status}`), { status: res.status });
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  },
  kycCase: (id: string, case_id: string, consentId: string, ocr = false) =>
    post<KycUploadResponse>(`/api/v1/orders/${id}/kyc/case`, { case_id, ocr, consent_id: consentId }, undefined, ok(id)),
  ocrStatus: () => get<{ available: boolean }>("/api/v1/ocr/status"),
  adminLogin: (password: string) => post<{ token: string; role: Role }>("/api/v1/admin/login", { password }),
  verifyQueue: (token: string) => get<AdminOrder[]>("/api/v1/verify/queue", token),
  storage: (token: string) => get<Record<string, string | number>>("/api/v1/admin/storage", token),
  overview: (token: string, q = "", stage = "", liveOnly = false, status = "open", limit = 60) =>
    get<AdminOverview>(
      `/api/v1/admin/overview?q=${encodeURIComponent(q)}&stage=${encodeURIComponent(stage)}&live_only=${liveOnly}&status=${status}&limit=${limit}`,
      token,
    ),
  leads: (token: string, status = "open", liveOnly = false, q = "") =>
    get<{ leads: AdminLead[]; matched: number }>(`/api/v1/admin/leads?status=${status}&live_only=${liveOnly}&q=${encodeURIComponent(q)}&limit=100`, token),
  adminLead: (token: string, id: string) => get<AdminLeadDetail>(`/api/v1/admin/leads/${id}`, token),
  adminLeadUpdate: (token: string, id: string, body: { stage?: string; status?: string; drop_reason?: string; note?: string }) =>
    post<AdminLeadDetail>(`/api/v1/admin/leads/${id}/update`, body, token),
  adminOrders: (token: string, status = "", q = "") =>
    get<AdminOrder[]>(`/api/v1/admin/orders?status=${status}&q=${encodeURIComponent(q)}`, token),
  adminOrderStatus: (token: string, id: string, action: OrderAction, note = "") =>
    post<AdminOrder>(`/api/v1/admin/orders/${id}/status`, { action, note }, token),
  adminKycSamples: (token: string) => get<KycSample[]>("/api/v1/admin/kyc/samples", token),
  adminKycOcr: (token: string, id: string) => post<KycOcrResult>(`/api/v1/admin/kyc/samples/${id}/ocr`, {}, token),
  adminAction: (token: string, lead: string, action: string) =>
    post<{ action_done: { text: string } }>(`/api/v1/admin/leads/${lead}/action`, { action }, token),
  adminAdvance: (token: string, order: string, product_id: string) =>
    post<AdminOrder>(`/api/v1/admin/orders/${order}/advance`, { product_id }, token),
  adminReview: (token: string, order: string, decision: "approve" | "reject", note: string) =>
    post<AdminOrder>(`/api/v1/admin/orders/${order}/review`, { decision, note }, token),
};

export function rupees(x: string | number): string {
  const n = typeof x === "string" ? parseFloat(x) : x;
  return "₹" + (Number.isInteger(n) ? n.toLocaleString("en-IN") : n.toLocaleString("en-IN", { minimumFractionDigits: 2 }));
}
