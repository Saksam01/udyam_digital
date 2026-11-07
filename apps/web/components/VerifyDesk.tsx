"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileSearch,
  Info,
  Loader2,
  Lock,
  MinusCircle,
  ScanText,
  ShieldCheck,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AdminOrder, Evidence, KycOcrResult, KycSample, Thresholds, TraceItem, api, kycDocUrl, rupees, samplePageUrl, subscribe, vaultPageUrl } from "@/lib/api";
import { Chip, ChipTone } from "./ui";
import { OrderControls, ago } from "./AdminPanels";

const DOC_ORDER = ["gst", "udyam", "sig", "bill"] as const;
const DOC_LABEL: Record<string, string> = { gst: "GST certificate", udyam: "Udyam certificate", sig: "Signatory ID", bill: "Address proof" };
const DOC_SLOT: Record<string, string> = { gst: "gst_certificate", udyam: "udyam_certificate", sig: "signatory_id", bill: "address_proof" };
const SLOT_DOC: Record<string, string> = Object.fromEntries(Object.entries(DOC_SLOT).map(([d, s]) => [s, d]));

const RESULT: Record<TraceItem["result"], { icon: LucideIcon; cls: string; label: string }> = {
  pass: { icon: CheckCircle2, cls: "text-success-600", label: "Pass" },
  review: { icon: AlertTriangle, cls: "text-warning-600", label: "Needs a person" },
  fail: { icon: XCircle, cls: "text-danger-600", label: "Fail" },
  info: { icon: MinusCircle, cls: "text-ink-400", label: "Noted" },
};

export const VERDICT: Record<string, { tone: ChipTone; icon: LucideIcon; text: string; next: string }> = {
  PASS: { tone: "success", icon: CheckCircle2, text: "PASS", next: "Approved automatically. Setup starts and no images are kept." },
  REVIEW: { tone: "warning", icon: AlertTriangle, text: "REVIEW", next: "Sent to the verification desk. Cleaned page images are held encrypted until a reviewer decides." },
  REJECT: { tone: "danger", icon: XCircle, text: "REJECT", next: "The customer is asked to upload again. Nothing is kept." },
};

function docOf(t: TraceItem): string {
  const d = t.evidence?.doc ?? t.doc;
  return SLOT_DOC[d] ?? d;
}

function pct(x: number | null | undefined) {
  return x == null ? "—" : `${Math.round(x * 100)}%`;
}

function ScoreBar({ e, th, result }: { e: Evidence; th?: Thresholds; result?: TraceItem["result"] }) {
  if (e.score == null) return null;
  const pass = e.threshold ?? th?.pass ?? 0.95;
  const review = th?.review ?? 0.8;
  const ok = e.score >= pass && e.distinctive_token_match !== false;
  const color = result === "fail" ? "bg-danger-600" : ok ? "bg-success-600" : e.score >= review ? "bg-warning-600" : "bg-danger-600";
  return (
    <div className="mt-2">
      <div className="relative h-2 rounded-full bg-line-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(100, e.score * 100)}%` }} />
        <span className="absolute -top-1 h-4 w-0.5 bg-ink-900" style={{ left: `${pass * 100}%` }} title={`pass threshold ${pct(pass)}`} />
        <span className="absolute -top-1 h-4 w-0.5 bg-ink-400" style={{ left: `${review * 100}%` }} title={`review threshold ${pct(review)}`} />
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[12px] text-ink-500">
        <span className="font-semibold tabular-nums text-ink-900">
          Similarity {pct(e.score)} {ok ? "≥" : "<"} {pct(pass)}
        </span>
        {e.distinctive_token_match === false && <span className="font-semibold text-danger-600">distinctive word differs</span>}
        <span>review band {pct(review)}–{pct(pass)}</span>
      </div>
    </div>
  );
}

function PageView({ src, e, label }: { src: string | null; e: Evidence | null; label: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed)
    return (
      <div className="flex aspect-[3/4] items-center justify-center rounded-2xl bg-surface-50 p-6 text-center text-[13px] text-ink-500">
        <div>
          <Lock size={22} className="mx-auto mb-2 text-ink-400" />
          {src ? "This page is no longer held. It is deleted as soon as a decision is made." : "No page image for this document."}
        </div>
      </div>
    );
  const box = e?.box && e.page_size ? e.box : null;
  const [w, h] = e?.page_size ?? [1, 1];
  return (
    <figure className="relative overflow-hidden rounded-2xl bg-white ring-1 ring-line-200">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={label} onError={() => setFailed(true)} className="block w-full" />
      {box && (
        <span
          className="pointer-events-none absolute rounded-sm ring-[3px] ring-brand-500"
          style={{
            left: `${(box[0] / w) * 100}%`,
            top: `${(box[1] / h) * 100}%`,
            width: `${(box[2] / w) * 100}%`,
            height: `${(box[3] / h) * 100}%`,
            boxShadow: "0 0 0 9999px rgba(23,23,28,0.28)",
          }}
        />
      )}
      <figcaption className="absolute left-2 top-2 rounded-md bg-ink-900/80 px-2 py-0.5 text-[11px] font-semibold text-white">
        {label}
        {box ? ` · ${e?.field}` : ""}
      </figcaption>
    </figure>
  );
}

export function AuditDrawer({
  title,
  subtitle,
  verdict,
  trace,
  thresholds,
  pageUrl,
  footer,
  onClose,
}: {
  title: string;
  subtitle?: string;
  verdict: string;
  trace: TraceItem[];
  thresholds?: Thresholds;
  pageUrl: (slot: string) => string | null;
  footer?: React.ReactNode;
  onClose: () => void;
}) {
  const groups = useMemo(() => {
    const g: Record<string, TraceItem[]> = {};
    for (const t of trace) (g[docOf(t)] ??= []).push(t);
    return DOC_ORDER.filter((d) => g[d]?.length).map((d) => ({ doc: d, items: g[d] }));
  }, [trace]);
  const firstIssue = trace.find((t) => t.result !== "pass" && t.evidence) ?? trace.find((t) => t.evidence) ?? null;
  const [sel, setSel] = useState<TraceItem | null>(firstIssue);
  const selDoc = sel ? docOf(sel) : groups[0]?.doc;
  const v = VERDICT[verdict] ?? VERDICT.REVIEW;
  const failing = trace.filter((t) => t.result === "fail" || t.result === "review").length;

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button aria-label="Close" onClick={onClose} className="fade-in absolute inset-0 bg-ink-900/40" />
      <aside className="drawer-in relative flex h-full w-full max-w-[1100px] flex-col bg-surface-50 shadow-float">
        <header className="flex items-start justify-between gap-3 border-b border-line-200 bg-white px-6 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[12px] font-semibold text-ink-500">
              <FileSearch size={14} />
              Rule audit
            </div>
            <h2 className="truncate text-[20px] font-bold text-ink-900">{title}</h2>
            {subtitle && <div className="text-[13px] text-ink-500">{subtitle}</div>}
          </div>
          <div className="flex items-center gap-3">
            <Chip tone={v.tone} icon={v.icon}>
              {v.text}
            </Chip>
            <button onClick={onClose} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-50 text-ink-700">
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
          <div className="scroll-area min-h-0 space-y-4 overflow-y-auto px-6 py-5">
            {groups.map((g, gi) => (
              <section key={g.doc} className="rounded-card bg-white p-4 shadow-soft">
                <h3 className="flex items-center gap-2 text-[14px] font-semibold text-ink-900">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-ink-900 text-[12px] font-bold text-white">{gi + 1}</span>
                  {DOC_LABEL[g.doc] ?? g.doc}
                  <span className="ml-auto text-[12px] font-medium text-ink-500">
                    {g.items.filter((t) => t.result === "pass").length}/{g.items.length} passed
                  </span>
                </h3>
                <ul className="mt-2 divide-y divide-line-100">
                  {g.items.map((t, i) => {
                    const R = RESULT[t.result];
                    const on = sel === t;
                    const e = t.evidence;
                    return (
                      <li key={t.code + i}>
                        <button
                          onClick={() => setSel(t)}
                          className={`flex w-full items-start gap-3 rounded-xl px-2 py-2.5 text-left transition-colors ${on ? "bg-brand-50" : "hover:bg-surface-50"}`}
                        >
                          <R.icon size={18} className={`mt-0.5 shrink-0 ${R.cls}`} />
                          <span className="min-w-0 flex-1">
                            <span className="flex flex-wrap items-baseline gap-x-2">
                              <span className="text-[13px] font-semibold text-ink-900">{t.check}</span>
                              <span className="font-mono text-[11px] text-ink-400">{t.code}</span>
                            </span>
                            {e && (on || t.result !== "pass") && (
                              <span className="mt-1.5 block text-[12px] leading-relaxed text-ink-700">
                                <span className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                                  <span className="text-ink-400">Read ({e.field})</span>
                                  <span className="break-words font-medium text-ink-900">{String(e.extracted ?? "—")}</span>
                                  <span className="text-ink-400">{e.reference_source}</span>
                                  <span className="break-words font-medium text-ink-900">{String(e.reference ?? "—")}</span>
                                </span>
                                <ScoreBar e={e} th={thresholds} result={t.result} />
                              </span>
                            )}
                          </span>
                          <span className={`shrink-0 text-[11px] font-semibold ${R.cls}`}>{R.label}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}

            <section className={`rounded-card p-4 ${v.tone === "success" ? "bg-success-50" : v.tone === "danger" ? "bg-danger-50" : "bg-warning-50"}`}>
              <div className="flex items-start gap-3">
                <v.icon size={20} className={`mt-0.5 shrink-0 ${v.tone === "success" ? "text-success-600" : v.tone === "danger" ? "text-danger-600" : "text-warning-600"}`} />
                <div className="text-[13px] leading-relaxed text-ink-700">
                  <div className="font-bold text-ink-900">
                    Rule engine verdict: {v.text} · {failing} of {trace.length} checks did not pass
                  </div>
                  {v.next}
                  {thresholds && (
                    <div className="mt-1 text-[12px] text-ink-500">
                      Names: {thresholds.method}. Pass at {pct(thresholds.pass)}, a person reviews {pct(thresholds.review)}–{pct(thresholds.pass)}, below that it fails.
                    </div>
                  )}
                </div>
              </div>
            </section>
            {footer}
          </div>

          <div className="scroll-area hidden min-h-0 overflow-y-auto border-l border-line-200 bg-white px-5 py-5 lg:block">
            <div className="mb-3 flex flex-wrap gap-1.5">
              {groups.map((g) => (
                <button
                  key={g.doc}
                  onClick={() => setSel(g.items.find((t) => t.evidence?.box) ?? g.items[0])}
                  className={`rounded-full px-3 py-1 text-[12px] font-semibold ${selDoc === g.doc ? "bg-ink-900 text-white" : "text-ink-700 ring-1 ring-line-200"}`}
                >
                  {DOC_LABEL[g.doc]}
                </button>
              ))}
            </div>
            {selDoc && <PageView src={pageUrl(sel?.evidence?.slot ?? DOC_SLOT[selDoc])} e={sel && docOf(sel) === selDoc ? sel.evidence ?? null : null} label={DOC_LABEL[selDoc]} />}
            <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-snug text-ink-500">
              <Info size={12} className="mt-0.5 shrink-0" />
              The highlighted box is where the OCR read the field. Page images are the cleaned copy the OCR used; any Aadhaar number has its first 8 digits blacked out.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}

export function ReviewDesk({ token }: { token: string }) {
  const [rows, setRows] = useState<AdminOrder[] | null>(null);
  const [open, setOpen] = useState<AdminOrder | null>(null);
  const load = useCallback(() => {
    api
      .verifyQueue(token)
      .then((r) => {
        setRows(r);
        setOpen((cur) => (cur ? r.find((x) => x.order_id === cur.order_id) ?? null : null));
      })
      .catch(() => setRows([]));
  }, [token]);
  useEffect(() => {
    load();
    return subscribe(`/api/v1/admin/stream?t=${token}`, load);
  }, [load, token]);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-card bg-white p-5 shadow-soft">
        <ShieldCheck size={22} className="mt-0.5 shrink-0 text-aqua-600" />
        <p className="text-[13px] leading-relaxed text-ink-700">
          Only cases the rules could not decide come here: blurred pages, near-miss names, a signatory who may not be authorised. Page images are held encrypted for
          this desk only and are deleted the moment you approve or ask for new documents. Sales never sees them.
        </p>
      </div>
      {!rows && <div className="skeleton h-40 rounded-card" />}
      {rows && rows.length === 0 && <p className="rounded-2xl bg-white p-8 text-center text-[14px] text-ink-500 shadow-soft">Nothing waiting. Every recent case was decided by the rules.</p>}
      {rows?.map((o) => {
        const issues = (o.kyc?.trace ?? []).filter((t) => t.result === "fail" || t.result === "review");
        return (
          <article key={o.order_id} className="enter rounded-card bg-white p-5 shadow-soft">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[16px] font-semibold text-ink-900">{o.kyc?.summary?.business ?? o.business}</div>
                <div className="text-[13px] text-ink-500">
                  {o.order_id} · {o.city || "—"} · {o.bundle_name} · {rupees(o.tax.monthly_incl_gst)}/mo · waiting {ago(o.updated_at)}
                </div>
                {o.kyc?.declared && (
                  <div className="mt-1 text-[12px] text-ink-500">
                    Name typed in the app: <span className="font-semibold text-ink-900">{o.kyc.declared}</span>
                  </div>
                )}
              </div>
              <Chip tone="warning" icon={AlertTriangle}>
                REVIEW
              </Chip>
            </div>
            <ul className="mt-3 space-y-1.5">
              {issues.map((t, i) => (
                <li key={i} className="flex gap-2 text-[13px]">
                  <span className={`h-fit shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold ${t.result === "fail" ? "bg-danger-50 text-danger-600" : "bg-warning-50 text-warning-600"}`}>
                    {t.code}
                  </span>
                  <span className="text-ink-700">
                    {DOC_LABEL[docOf(t)] ?? t.doc}: {t.check}
                    {t.evidence?.score != null && <span className="text-ink-500"> · similarity {pct(t.evidence.score)}</span>}
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-500">
              <span className="flex items-center gap-1">
                <Lock size={12} />
                {o.vault ? `${Object.keys(o.vault.slots).length} page(s) held, encrypted` : "No pages held (fixture sample)"}
              </span>
              {o.vault && (
                <span className="flex items-center gap-1">
                  <Trash2 size={12} />
                  auto-delete {new Date(o.vault.purge_after * 1000).toLocaleDateString("en-IN")}
                </span>
              )}
              {o.consent && <span className="font-mono">{o.consent.consent_id}</span>}
              {o.kyc?.source && <span>source: {o.kyc.source}</span>}
            </div>
            <button onClick={() => setOpen(o)} className="press mt-3 flex h-10 items-center gap-2 rounded-xl bg-ink-900 px-4 text-[13px] font-semibold text-white">
              <FileSearch size={16} />
              Open audit and documents
            </button>
            <OrderControls order={o} token={token} onDone={load} />
          </article>
        );
      })}
      {open && (
        <AuditDrawer
          title={open.kyc?.summary?.business ?? open.business ?? open.order_id}
          subtitle={`${open.order_id} · ${open.kyc?.source ?? "upload"}`}
          verdict={open.kyc?.verdict ?? "REVIEW"}
          trace={open.kyc?.trace ?? []}
          thresholds={open.kyc?.thresholds}
          pageUrl={(slot) => (open.vault?.slots?.[slot] ? vaultPageUrl(token, open.order_id, slot) : null)}
          onClose={() => setOpen(null)}
          footer={<OrderControls order={open} token={token} onDone={() => (setOpen(null), load())} />}
        />
      )}
    </div>
  );
}

export function KycSamplesView({ token }: { token: string }) {
  const [rows, setRows] = useState<KycSample[] | null>(null);
  const [ocr, setOcr] = useState<Record<string, KycOcrResult | "busy" | "error">>({});
  const [audit, setAudit] = useState<{ id: string; ocr: boolean } | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    api.adminKycSamples(token).then(setRows).catch(() => setRows([]));
  }, [token]);

  async function runOcr(id: string) {
    setOcr((m) => ({ ...m, [id]: "busy" }));
    try {
      const r = await api.adminKycOcr(token, id);
      setOcr((m) => ({ ...m, [id]: r }));
      setNonce((n) => n + 1);
    } catch {
      setOcr((m) => ({ ...m, [id]: "error" }));
    }
  }
  async function runAll() {
    for (const r of rows ?? []) await runOcr(r.case_id);
  }

  const auditRow = audit ? rows?.find((r) => r.case_id === audit.id) : null;
  const auditOcr = audit?.ocr ? ocr[audit.id] : null;
  const auditRes = auditOcr && typeof auditOcr === "object" ? auditOcr : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-card bg-white p-5 shadow-soft">
        <div>
          <h2 className="text-[16px] font-semibold text-ink-900">Hackathon KYC applicants (K01–K12)</h2>
          <p className="text-[13px] text-ink-500">
            Click a verdict to see every rule, what was read, what it was compared to and the score. &ldquo;Read with OCR&rdquo; runs Tesseract on the real images, the same
            path a customer upload takes, and marks where each field was found.
          </p>
        </div>
        <button onClick={runAll} className="press flex h-10 items-center gap-2 rounded-xl bg-ink-900 px-4 text-[13px] font-semibold text-white">
          <ScanText size={16} />
          Read all 12 with OCR
        </button>
      </div>
      {!rows && <div className="skeleton h-64 rounded-card" />}
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {rows?.map((r) => {
          const v = VERDICT[r.verdict];
          const o = ocr[r.case_id];
          const res = typeof o === "object" ? o : null;
          const match = res?.verdict ? res.verdict === r.verdict : null;
          const hard = (r.trace ?? []).filter((t) => t.result === "fail" || t.result === "review");
          return (
            <article key={r.case_id} className="enter flex flex-col rounded-card bg-white p-5 shadow-soft">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-[12px] font-bold text-ink-500">{r.case_id}</div>
                  <h3 className="truncate text-[15px] font-semibold text-ink-900">{r.business}</h3>
                  <div className="text-[12px] text-ink-500">{r.constitution}</div>
                </div>
                <button onClick={() => setAudit({ id: r.case_id, ocr: false })} title="Open the rule audit" className="press rounded-full">
                  <Chip tone={v.tone} icon={v.icon}>
                    {r.verdict} ›
                  </Chip>
                </button>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-1.5">
                {r.documents.map((s) => (
                  <button key={s} onClick={() => setAudit({ id: r.case_id, ocr: !!res })} title={DOC_LABEL[SLOT_DOC[s]]} className="press overflow-hidden rounded-lg ring-1 ring-line-200">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={kycDocUrl(r.case_id, s, token)} alt={DOC_LABEL[SLOT_DOC[s]]} loading="lazy" className="aspect-[3/4] w-full bg-surface-50 object-cover object-top" />
                  </button>
                ))}
              </div>
              <ul className="mt-3 space-y-1 text-[12px]">
                {hard.slice(0, 3).map((t, i) => (
                  <li key={i} className="flex gap-2">
                    <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold ${t.result === "fail" ? "bg-danger-50 text-danger-600" : "bg-warning-50 text-warning-600"}`}>
                      {t.code}
                    </span>
                    <span className="text-ink-700">
                      {t.check}
                      {t.evidence?.score != null && <span className="text-ink-400"> · {pct(t.evidence.score)}</span>}
                    </span>
                  </li>
                ))}
                {hard.length === 0 && <li className="text-success-600">All {r.trace?.length ?? 0} checks passed</li>}
              </ul>
              <div className="mt-auto pt-4">
                {o === "busy" ? (
                  <div className="flex h-9 items-center gap-2 text-[13px] font-medium text-ink-500">
                    <Loader2 size={15} className="animate-spin" /> Reading the images…
                  </div>
                ) : o === "error" ? (
                  <div className="text-[13px] text-danger-600">OCR failed. Is Tesseract installed on the server?</div>
                ) : res ? (
                  <button
                    onClick={() => setAudit({ id: r.case_id, ocr: true })}
                    className={`w-full rounded-xl p-2.5 text-left text-[12px] ${match ? "bg-success-50 text-success-600" : "bg-warning-50 text-warning-600"}`}
                  >
                    <div className="flex items-center gap-1.5 font-semibold">
                      {match ? <ShieldCheck size={14} /> : <AlertTriangle size={14} />}
                      OCR verdict {res.verdict ?? res.status} {match ? "matches" : "differs"} · open audit ›
                      <span className="ml-auto flex items-center gap-1 font-medium">
                        <Clock size={12} />
                        {res.seconds}s
                      </span>
                    </div>
                    {res.raw_findings && res.raw_findings.length > 0 && <div className="mt-0.5 text-ink-700">{res.raw_findings.map((f) => f.code).join(", ")}</div>}
                    {res.needs?.map((n) => (
                      <div key={n.text} className="mt-0.5 text-ink-700">
                        {n.text}
                      </div>
                    ))}
                  </button>
                ) : (
                  <button onClick={() => runOcr(r.case_id)} className="press flex h-9 items-center gap-1.5 rounded-xl px-3 text-[13px] font-semibold text-ink-900 ring-1 ring-line-200">
                    <ScanText size={15} />
                    Read with OCR
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      {auditRow && audit && (
        <AuditDrawer
          title={`${auditRow.case_id} · ${auditRow.business}`}
          subtitle={auditRes ? `Read from the images with OCR in ${auditRes.seconds}s` : "Pre-extracted fields from the hackathon pack (no OCR)"}
          verdict={auditRes?.verdict ?? auditRow.verdict}
          trace={auditRes?.trace ?? auditRow.trace ?? []}
          thresholds={auditRes?.thresholds ?? auditRow.thresholds}
          pageUrl={(slot) => (auditRes ? samplePageUrl(token, auditRow.case_id, slot, nonce) : auditRow.documents.includes(slot) ? kycDocUrl(auditRow.case_id, slot, token) : null)}
          onClose={() => setAudit(null)}
        />
      )}
    </div>
  );
}
