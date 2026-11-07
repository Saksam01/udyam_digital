"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  Ban,
  CheckCircle2,
  Loader2,
  Lock,
  MessageCircle,
  Search,
  Send,
  Share2,
  X,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AdminLead, AdminLeadDetail, AdminOrder, LEAD_STAGES, LEAD_STATUSES, LeadScore, ModelCard, OrderAction, Role, api, rupees, subscribe } from "@/lib/api";
import { Chip, ChipTone } from "./ui";

export const RoleContext = createContext<Role>("sales");
const KYC_ACTIONS: OrderAction[] = ["approve", "reject"];

export const ORDER_STATUS: Record<string, { text: string; tone: ChipTone }> = {
  awaiting_kyc: { text: "Awaiting documents", tone: "neutral" },
  kyc_rejected: { text: "Documents need fixing", tone: "danger" },
  kyc_review: { text: "In review", tone: "warning" },
  approved: { text: "Approved", tone: "success" },
  in_progress: { text: "Being set up", tone: "info" },
  live: { text: "Live", tone: "success" },
  cancelled: { text: "Cancelled", tone: "danger" },
};

const ACTIONS: Record<OrderAction, { label: string; icon: LucideIcon; cls: string; allowed: string[] }> = {
  approve: { label: "Approve documents", icon: CheckCircle2, cls: "bg-success-600 text-white", allowed: ["kyc_review"] },
  reject: { label: "Ask for new documents", icon: Send, cls: "bg-white text-danger-600 ring-1 ring-danger-600/30", allowed: ["kyc_review"] },
  mark_live: { label: "Mark all services live", icon: Zap, cls: "bg-ink-900 text-white", allowed: ["in_progress"] },
  cancel: { label: "Cancel order", icon: Ban, cls: "bg-white text-ink-500 ring-1 ring-line-200", allowed: ["awaiting_kyc", "kyc_review", "kyc_rejected", "approved", "in_progress"] },
};

export function ago(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function OrderControls({ order, token, onDone }: { order: AdminOrder; token: string; onDone: (o?: AdminOrder) => void }) {
  const role = useContext(RoleContext);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<OrderAction | null>(null);
  const [err, setErr] = useState("");
  const available = (Object.keys(ACTIONS) as OrderAction[]).filter(
    (a) => ACTIONS[a].allowed.includes(order.status) && (role === "verifier" ? KYC_ACTIONS.includes(a) : !KYC_ACTIONS.includes(a)),
  );
  const kycPending = role === "sales" && ["awaiting_kyc", "kyc_review", "kyc_rejected"].includes(order.status);
  if (!available.length)
    return kycPending ? (
      <p className="mt-3 flex items-center gap-1.5 text-[12px] text-ink-500">
        <Lock size={12} />
        Document decisions are made by the verification desk.
      </p>
    ) : null;

  async function run(a: OrderAction) {
    if (a === "cancel" && !window.confirm(`Cancel order ${order.order_id}? The customer will see it as cancelled.`)) return;
    setBusy(a);
    setErr("");
    try {
      const o = await api.adminOrderStatus(token, order.order_id, a, note);
      setNote("");
      onDone(o);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update the order");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-4 rounded-2xl bg-surface-50 p-3">
      <input
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Note for the record (optional, the customer does not see it)"
        className="h-10 w-full rounded-xl bg-white px-3 text-[13px] outline-none ring-1 ring-line-200 focus:ring-2 focus:ring-brand-500"
      />
      <div className="mt-2.5 flex flex-wrap gap-2">
        {available.map((a) => {
          const A = ACTIONS[a];
          const Icon = busy === a ? Loader2 : A.icon;
          return (
            <button
              key={a}
              disabled={!!busy}
              onClick={() => run(a)}
              className={`press flex h-9 items-center gap-1.5 rounded-xl px-3.5 text-[13px] font-semibold disabled:opacity-50 ${A.cls}`}
            >
              <Icon size={15} className={busy === a ? "animate-spin" : ""} />
              {A.label}
            </button>
          );
        })}
      </div>
      {err && <p className="mt-2 text-[12px] font-medium text-danger-600">{err}</p>}
    </div>
  );
}

export function LeadDrawer({ leadId, token, onClose, onChanged }: { leadId: string; token: string; onClose: () => void; onChanged: () => void }) {
  const role = useContext(RoleContext);
  const [d, setD] = useState<AdminLeadDetail | null>(null);
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try {
      const x = await api.adminLead(token, leadId);
      setD(x);
      setStage(x.stage);
      setStatus(x.status);
      setReason(x.drop_reason ?? "");
    } catch {
      setErr("Could not load this lead.");
    }
  }, [token, leadId]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  async function save() {
    if (!d) return;
    setBusy(true);
    setErr("");
    try {
      const x = await api.adminLeadUpdate(token, d.lead_id, {
        stage: stage !== d.stage ? stage : undefined,
        status: status !== d.status ? status : undefined,
        drop_reason: status === "lost" ? reason : undefined,
        note: note.trim() || undefined,
      });
      setD(x);
      setNote("");
      onChanged();
    } catch {
      setErr("Could not save the change.");
    } finally {
      setBusy(false);
    }
  }
  const dirty = d && (stage !== d.stage || status !== d.status || note.trim() || (status === "lost" && reason !== (d.drop_reason ?? "")));

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button aria-label="Close" onClick={onClose} className="fade-in absolute inset-0 bg-ink-900/40" />
      <aside className="drawer-in relative flex h-full w-full max-w-[560px] flex-col bg-surface-50 shadow-float">
        <header className="flex items-start justify-between gap-3 border-b border-line-200 bg-white px-6 py-5">
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-ink-500">{leadId}</div>
            <h2 className="truncate text-[20px] font-bold text-ink-900">{d?.business ?? "Loading…"}</h2>
            {d && (
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                {d.live && <Chip tone="brand">From the app</Chip>}
                <Chip>{d.stage}</Chip>
                <Chip tone={d.status === "won" ? "success" : d.status === "lost" ? "danger" : d.status === "review" ? "warning" : "info"}>{d.status}</Chip>
                <span className="text-[12px] text-ink-500">
                  {d.score?.final === "won" ? "Won" : d.score?.final === "lost" ? "Lost" : `${Math.round(d.likelihood * 100)}% chance to activate`}
                </span>
              </div>
            )}
          </div>
          <button onClick={onClose} aria-label="Close" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-50 text-ink-700">
            <X size={18} />
          </button>
        </header>

        <div className="scroll-area flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {!d && !err && <div className="skeleton h-40 rounded-card" />}
          {err && <p className="rounded-2xl bg-danger-50 p-3 text-[13px] text-danger-600">{err}</p>}
          {d && (
            <>
              <section className="rounded-card bg-white p-5 shadow-soft">
                <h3 className="text-[14px] font-semibold text-ink-900">Update status</h3>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <label className="text-[12px] font-semibold text-ink-500">
                    Funnel stage
                    <select value={stage} onChange={(e) => setStage(e.target.value)} className="admin-select mt-1">
                      {LEAD_STAGES.filter(
                        (s) => s === d.stage || (LEAD_STAGES.indexOf(s) > LEAD_STAGES.indexOf(d.stage) && LEAD_STAGES.indexOf(s) <= LEAD_STAGES.indexOf("Quote accepted")),
                      ).map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                  <label className="text-[12px] font-semibold text-ink-500">
                    Status
                    <select value={status} onChange={(e) => setStatus(e.target.value)} className="admin-select mt-1">
                      {LEAD_STATUSES.map((s) => (
                        <option key={s} value={s}>
                          {{ open: "Open", review: "In review", won: "Won", lost: "Lost" }[s]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {status === "lost" && (
                  <input
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Why was it lost?"
                    className="mt-3 h-10 w-full rounded-xl bg-surface-50 px-3 text-[13px] outline-none ring-1 ring-line-200 focus:ring-2 focus:ring-brand-500"
                  />
                )}
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Add a note (call outcome, follow-up date…)"
                  className="mt-3 w-full resize-none rounded-xl bg-surface-50 px-3 py-2.5 text-[13px] outline-none ring-1 ring-line-200 focus:ring-2 focus:ring-brand-500"
                />
                <button
                  onClick={save}
                  disabled={!dirty || busy}
                  className="press mt-3 flex h-10 items-center gap-2 rounded-xl bg-brand-600 px-4 text-[13px] font-semibold text-white disabled:opacity-40"
                >
                  {busy && <Loader2 size={15} className="animate-spin" />}
                  Save changes
                </button>
              </section>

              {role === "sales" && (
                <section className="rounded-card bg-white p-5 shadow-soft">
                  <h3 className="text-[14px] font-semibold text-ink-900">Reach out</h3>
                  <p className="mt-1 text-[12px] text-ink-500">Opens WhatsApp with the message filled in; you pick the chat and press send. The action is logged on the lead.</p>
                  <div className="mt-3">
                    <QuickActions lead={d} token={token} onDone={() => (load(), onChanged())} />
                  </div>
                </section>
              )}

              {d.score && (
                <section className="rounded-card bg-white p-5 shadow-soft">
                  <h3 className="mb-3 text-[14px] font-semibold text-ink-900">Why this score</h3>
                  <ScoreBreakdown score={d.score} card={d.score.card} />
                </section>
              )}

              <section className="rounded-card bg-white p-5 shadow-soft">
                <h3 className="text-[14px] font-semibold text-ink-900">Profile</h3>
                <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-5 gap-y-2 text-[13px]">
                  {(
                    [
                      ["Business type", d.business_type],
                      ["Segment", d.segment],
                      ["City", d.city],
                      ["Language", d.language],
                      ["Source", d.source],
                      ["Staff · sites", `${d.employees ?? "—"} · ${d.sites ?? "—"}`],
                      ["GST", `${d.gst_status ?? "—"}${d.gstin ? ` (${d.gstin})` : ""}`],
                      ["Contact", d.contact ?? "—"],
                      ["Stalled because", d.drop_reason ?? "—"],
                      ["Partner", d.partner ? `${d.partner.name} (${d.partner.kind}), ${d.partner.phone}` : "—"],
                    ] as [string, string | null][]
                  ).map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-ink-400">{k}</dt>
                      <dd className="min-w-0 break-words text-ink-900">{v || "—"}</dd>
                    </div>
                  ))}
                </dl>
                {d.signals.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {d.signals.map((s, i) => (
                      <Chip key={i} tone={s.tone === "good" ? "success" : s.tone === "warn" ? "warning" : "danger"}>
                        {s.text}
                      </Chip>
                    ))}
                  </div>
                )}
                {d.bundle && (
                  <div className="mt-3 rounded-2xl bg-surface-50 p-3 text-[13px]">
                    <div className="flex justify-between gap-2 font-semibold text-ink-900">
                      <span>{d.bundle.name}</span>
                      <span className="tabular-nums">{rupees(d.bundle.monthly_ex)}/mo + GST</span>
                    </div>
                    <ul className="mt-1.5 space-y-0.5 text-ink-700">
                      {d.bundle.lines.map((l, i) => (
                        <li key={i} className="flex justify-between gap-2">
                          <span>
                            {l.label}
                            {l.qty > 1 ? ` ×${l.qty}` : ""}
                          </span>
                          <span className="tabular-nums">{rupees(l.monthly)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-2 px-1 text-[14px] font-semibold text-ink-900">Orders</h3>
                {d.orders.length === 0 ? (
                  <p className="rounded-2xl bg-white p-4 text-[13px] text-ink-500 shadow-soft">No order yet. This lead has not accepted a quote in the app.</p>
                ) : (
                  <div className="space-y-3">
                    {d.orders.map((o) => (
                      <div key={o.order_id} className="rounded-card bg-white p-4 shadow-soft">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="text-[14px] font-semibold text-ink-900">{o.order_id}</div>
                            <div className="text-[12px] text-ink-500">
                              {o.bundle_name} · {rupees(o.tax.monthly_incl_gst)}/mo with GST · {ago(o.updated_at)}
                            </div>
                          </div>
                          <Chip tone={ORDER_STATUS[o.status]?.tone}>{ORDER_STATUS[o.status]?.text ?? o.status}</Chip>
                        </div>
                        {o.kyc?.verdict && (
                          <div className="mt-2 text-[12px] text-ink-500">
                            Document check: <span className="font-semibold text-ink-900">{o.kyc.verdict}</span>
                            {o.kyc.review_note ? ` · note: ${o.kyc.review_note}` : ""}
                          </div>
                        )}
                        <OrderControls order={o} token={token} onDone={() => (load(), onChanged())} />
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-card bg-white p-5 shadow-soft">
                <h3 className="text-[14px] font-semibold text-ink-900">History</h3>
                {d.events.length === 0 ? (
                  <p className="mt-2 text-[13px] text-ink-500">Nothing recorded yet.</p>
                ) : (
                  <ol className="mt-3">
                    {d.events.map((e, i) => (
                      <li key={i} className="relative flex gap-3 pb-3.5 last:pb-0">
                        {i < d.events.length - 1 && <span className="absolute left-[5px] top-4 h-full w-0.5 bg-line-100" />}
                        <span className={`relative mt-1 h-3 w-3 shrink-0 rounded-full ring-4 ring-white ${i === 0 ? "bg-brand-500" : "bg-line-200"}`} />
                        <div className="min-w-0 text-[13px]">
                          <div className="leading-snug text-ink-900">{e.text}</div>
                          <div className="text-[12px] text-ink-400">
                            {e.order_id ? `${e.order_id} · ` : ""}
                            {e.actor} · {ago(e.ts)}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export function OrdersView({ token, onOpenLead }: { token: string; onOpenLead: (id: string) => void }) {
  const [rows, setRows] = useState<AdminOrder[] | null>(null);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const load = useCallback(() => {
    api
      .adminOrders(token, status, q)
      .then(setRows)
      .catch(() => setRows([]));
  }, [token, status, q]);
  useEffect(() => {
    load();
    return subscribe(`/api/v1/admin/stream?t=${token}`, load);
  }, [load, token]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-10 w-72 items-center gap-2 rounded-xl bg-white px-3 shadow-soft focus-within:ring-2 focus-within:ring-brand-500">
          <Search size={16} className="text-ink-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search business, order or city" className="h-full flex-1 bg-transparent text-[13px] outline-none" />
        </label>
        {["", "awaiting_kyc", "kyc_review", "kyc_rejected", "in_progress", "live", "cancelled"].map((s) => (
          <button
            key={s || "all"}
            onClick={() => setStatus(s)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold ${status === s ? "bg-ink-900 text-white" : "bg-white text-ink-700 ring-1 ring-line-200"}`}
          >
            {s ? ORDER_STATUS[s].text : "All"}
          </button>
        ))}
      </div>
      {!rows && <div className="skeleton h-40 rounded-card" />}
      {rows && rows.length === 0 && <p className="rounded-2xl bg-white p-8 text-center text-[14px] text-ink-500 shadow-soft">No orders match.</p>}
      {rows?.map((o) => (
        <article key={o.order_id} className="enter rounded-card bg-white p-5 shadow-soft">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <button onClick={() => onOpenLead(o.lead_id)} className="text-left text-[16px] font-semibold text-ink-900 hover:text-brand-600">
                {o.business ?? "Customer"}
              </button>
              <div className="text-[13px] text-ink-500">
                {o.order_id} · {o.city || "—"} · {o.bundle_name} · {rupees(o.tax.monthly_incl_gst)}/mo with GST · updated {ago(o.updated_at)}
              </div>
              <div className="mt-1 text-[12px] text-ink-500">
                {o.live_count} of {o.total_count} services live
                {o.kyc?.verdict ? ` · document check ${o.kyc.verdict}` : ""}
              </div>
            </div>
            <Chip tone={ORDER_STATUS[o.status]?.tone}>{ORDER_STATUS[o.status]?.text ?? o.status}</Chip>
          </div>
          <OrderControls order={o} token={token} onDone={load} />
        </article>
      ))}
    </div>
  );
}

const pctTxt = (x?: number) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export function ScoreBreakdown({ score, card, compact = false }: { score?: LeadScore; card?: ModelCard; compact?: boolean }) {
  if (!score) return null;
  if (score.final)
    return (
      <p className="text-[12px] leading-snug text-ink-700">
        {score.final === "won" ? "Activated. This lead is won, so it is shown as 100% and no longer scored." : "Marked lost, so it is shown as 0% and no longer scored."}
      </p>
    );
  return (
    <div className={compact ? "text-[12px]" : "text-[13px]"}>
      <div className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-ink-700">
        <span>Leads that reached &ldquo;{score.stage}&rdquo; and activated</span>
        <span className="text-right font-semibold tabular-nums text-ink-900">{pctTxt(score.stage_rate)}</span>
        <span>
          This lead vs an average lead (model {pctTxt(score.p_model)} vs {pctTxt(score.avg_p)})
        </span>
        <span className="text-right font-semibold tabular-nums text-ink-900">×{score.lift?.toFixed(2)}</span>
        <span className="border-t border-line-100 pt-1 font-semibold text-ink-900">Chance to activate</span>
        <span className="border-t border-line-100 pt-1 text-right font-bold tabular-nums text-ink-900">{pctTxt(score.likelihood)}</span>
      </div>
      {score.stage === "KYC complete" && (
        <p className="mt-2 rounded-lg bg-info-50 px-2.5 py-1.5 text-[12px] leading-snug text-info-600">
          Documents are verified, but the lead is only won when every service is live. In the data, {pctTxt(1 - (score.stage_rate ?? 0))} of verified
          leads still dropped before activation (install delays, cancellations).
        </p>
      )}
      {(score.terms ?? []).length > 0 && (
        <ul className="mt-2.5 space-y-1">
          {(score.terms ?? []).map((t, i) => (
            <li key={i} className="flex items-center justify-between gap-3">
              <span className="text-ink-700">{t.text}</span>
              <span className={`shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[11px] font-bold ${t.odds_pct >= 0 ? "bg-success-50 text-success-600" : "bg-warning-50 text-warning-600"}`}>
                {t.odds_pct >= 0 ? "+" : ""}
                {t.odds_pct}% odds
              </span>
            </li>
          ))}
        </ul>
      )}
      {card && !compact && (
        <p className="mt-2.5 text-[11px] leading-snug text-ink-500">
          {card.model} trained on {card.rows.toLocaleString("en-IN")} leads in {card.trained_on} ({card.activated} activated). Held-out AUC {card.auc_held_out}, top 10% of
          scores convert {card.lift_top_decile}× the average. Outcome columns (drop reason, stage reached, bundle, NPS…) are never used as inputs.
        </p>
      )}
    </div>
  );
}

export function ScoreTip({ value, score, setup }: { value: number; score?: LeadScore; setup?: { live: number; total: number } | null }) {
  const [on, setOn] = useState(false);
  const p = Math.round(value * 100);
  const color = score?.final === "won" ? "bg-success-600" : p >= 60 ? "bg-success-600" : p >= 35 ? "bg-warning-600" : "bg-brand-500";
  return (
    <div className="relative w-28" onMouseEnter={() => setOn(true)} onMouseLeave={() => setOn(false)}>
      <button
        type="button"
        onFocus={() => setOn(true)}
        onBlur={() => setOn(false)}
        onClick={(e) => e.stopPropagation()}
        className="block w-full cursor-help text-left"
        aria-label={`Chance to activate ${p}%. Show how it is calculated`}
      >
        <div className="text-[15px] font-bold tabular-nums text-ink-900 underline decoration-dotted decoration-ink-400 underline-offset-4">
          {score?.final === "won" ? "Won" : score?.final === "lost" ? "Lost" : `${p}%`}
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-line-100">
          <div className={`bar-in h-full rounded-full ${color}`} style={{ width: `${Math.min(100, p)}%` }} />
        </div>
        {setup && !score?.final && (
          <div className="mt-1 text-[11px] font-semibold text-info-600">
            Setting up · {setup.live}/{setup.total} live
          </div>
        )}
      </button>
      {on && score && (
        <div className="fade-in absolute right-0 top-full z-30 mt-2 w-[340px] rounded-2xl bg-white p-4 text-left shadow-float ring-1 ring-line-200" onClick={(e) => e.stopPropagation()}>
          <div className="mb-2 text-[12px] font-semibold text-ink-500">How this number is worked out</div>
          <ScoreBreakdown score={score} compact />
        </div>
      )}
    </div>
  );
}

function waLink(text: string) {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

export function quoteText(lead: AdminLead) {
  const b = lead.bundle;
  const who = lead.contact ? lead.contact.split(" ")[0] : lead.business;
  if (!b) return `Namaste ${who}, this is Accel Business. Could we have 5 minutes to suggest the right internet and phone plan for ${lead.business}?`;
  const items = b.lines.map((l) => `• ${l.label}${l.qty > 1 ? ` ×${l.qty}` : ""}`).join("\n");
  return (
    `Namaste ${who}, here is the Accel Business plan for ${lead.business}:\n*${b.name}*\n${items}\n\n` +
    `${rupees(b.monthly_ex)}/month + GST (${rupees(b.monthly_incl)} with GST), ${rupees(b.setup)} one-time setup, ${b.contract}-month contract.\n` +
    `Reply YES and we will start, or finish it yourself in the Accel Business app. Ref ${lead.lead_id}`
  );
}

function partnerText(lead: AdminLead) {
  return (
    `New lead for you: ${lead.business} (${lead.business_type}), ${lead.city || "city not shared"}.\n` +
    `Stage: ${lead.stage}. Chance to activate ${Math.round(lead.likelihood * 100)}%.\n` +
    (lead.bundle ? `Plan: ${lead.bundle.name}, ${rupees(lead.bundle.monthly_ex)}/month + GST.\n` : "") +
    (lead.drop_reason ? `Stalled because: ${lead.drop_reason}.\n` : "") +
    (lead.action ? `Suggested next step: ${lead.action.label}.\n` : "") +
    `Lead ${lead.lead_id}`
  );
}

export function QuickActions({ lead, token, onDone }: { lead: AdminLead; token: string; onDone: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  async function go(kind: "whatsapp_quote" | "notify_partner") {
    setBusy(kind);
    window.open(waLink(kind === "whatsapp_quote" ? quoteText(lead) : partnerText(lead)), "_blank", "noopener");
    try {
      await api.adminAction(token, lead.lead_id, kind);
      onDone();
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => go("whatsapp_quote")}
        disabled={!!busy}
        className="press flex h-9 items-center gap-1.5 rounded-xl bg-[#1FA855] px-3.5 text-[13px] font-semibold text-white disabled:opacity-50"
      >
        {busy === "whatsapp_quote" ? <Loader2 size={15} className="animate-spin" /> : <MessageCircle size={15} />}
        WhatsApp quote
      </button>
      <button
        onClick={() => go("notify_partner")}
        disabled={!!busy}
        className="press flex h-9 items-center gap-1.5 rounded-xl bg-white px-3.5 text-[13px] font-semibold text-ink-900 ring-1 ring-line-200 disabled:opacity-50"
      >
        {busy === "notify_partner" ? <Loader2 size={15} className="animate-spin" /> : <Share2 size={15} />}
        Send to local partner
      </button>
    </div>
  );
}
