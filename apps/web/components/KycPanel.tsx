"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Camera,
  Check,
  CheckCircle2,
  FileText,
  Hourglass,
  IdCard,
  LifeBuoy,
  Loader2,
  Lock,
  ReceiptText,
  ScanText,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api, ChecklistItem, CustomerFinding, KycCase, KycUploadResponse, Order, kycDocUrl } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";
import { prepareUpload } from "@/lib/upload";
import LangPill from "./LangPill";
import { ResumeCard, SaveCard } from "./Resume";
import { Card, Hero, IconTile, Money, PersonCard, Tone, btn } from "./ui";

const SLOTS: { key: string; labelKey: string; required: boolean; icon: LucideIcon; tone: Tone }[] = [
  { key: "gst_certificate", labelKey: "slot_gst", required: true, icon: FileText, tone: "red" },
  { key: "signatory_id", labelKey: "slot_sig", required: true, icon: IdCard, tone: "blue" },
  { key: "address_proof", labelKey: "slot_bill", required: true, icon: ReceiptText, tone: "amber" },
  { key: "udyam_certificate", labelKey: "slot_udyam", required: false, icon: BadgeCheck, tone: "teal" },
];

export default function KycPanel({
  lang,
  setLang,
  order,
  onOrder,
  onTrack,
  onPlan,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  order: Order | null;
  onOrder: (o: Order) => void;
  onTrack: () => void;
  onPlan: () => void;
}) {
  const [files, setFiles] = useState<Record<string, File>>({});
  const [consentId, setConsentId] = useState<string | null>(null);
  const [consentBusy, setConsentBusy] = useState(false);
  const [preparing, setPreparing] = useState<string | null>(null);
  const consented = !!consentId;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [resp, setResp] = useState<KycUploadResponse | null>(null);
  const [cases, setCases] = useState<KycCase[]>([]);
  const [useOcr, setUseOcr] = useState(true);
  const [ocrOk, setOcrOk] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    let demo = process.env.NEXT_PUBLIC_DEMO === "1";
    try {
      const q = new URLSearchParams(window.location.search).get("demo");
      if (q === "1") window.localStorage.setItem("udyam_demo", "1");
      if (q === "0") window.localStorage.removeItem("udyam_demo");
      demo = demo || window.localStorage.getItem("udyam_demo") === "1";
    } catch {
      /* storage unavailable */
    }
    if (demo) api.kycCases().then(setCases).catch(() => {});
    api
      .ocrStatus()
      .then((s) => setOcrOk(s.available))
      .catch(() => setOcrOk(false));
  }, []);

  const orderKey = order ? `udyam_consent_${order.order_id}` : "";
  useEffect(() => {
    if (!orderKey) return;
    let saved: string | null = null;
    try {
      saved = window.localStorage.getItem(orderKey);
    } catch {
      /* storage unavailable */
    }
    if (!saved) {
      setConsentId(null);
      return;
    }
    api
      .consentGet(order!.order_id, saved)
      .then((c) => setConsentId(c.status === "active" ? c.consent_id : null))
      .catch(() => setConsentId(null));
  }, [orderKey]);

  async function giveConsent(on: boolean) {
    if (!order || consentBusy) return;
    setConsentBusy(true);
    setErr("");
    try {
      if (on) {
        const c = await api.consent(order.order_id, lang);
        setConsentId(c.consent_id);
        try {
          window.localStorage.setItem(orderKey, c.consent_id);
        } catch {
          /* storage unavailable */
        }
      } else if (consentId) {
        if (!window.confirm(t(lang, "cons_confirm_withdraw"))) return;
        await api.consentWithdraw(order.order_id, consentId);
        setConsentId(null);
        setFiles({});
        setResp(null);
        try {
          window.localStorage.removeItem(orderKey);
        } catch {
          /* storage unavailable */
        }
        onOrder(await api.order(order.order_id));
      }
    } catch {
      setErr(t(lang, "netErr"));
    } finally {
      setConsentBusy(false);
    }
  }

  const tk = (key: string, fallback: string) => {
    const v = t(lang, key);
    return v === key ? fallback : v;
  };
  const needText = (n: { doc?: string | null; kind?: string; text: string }) => {
    if (!n.kind) return n.text;
    if (n.kind === "dates") return tk("need_dates", n.text);
    const doc = n.doc ? tk(`dn_${n.doc}`, n.doc) : "";
    return tk(`need_${n.kind}`, n.text).replace("{doc}", doc);
  };

  const previews = useMemo(() => {
    const out: Record<string, string> = {};
    for (const [k, f] of Object.entries(files)) if (f.type.startsWith("image/")) out[k] = URL.createObjectURL(f);
    return out;
  }, [files]);
  useEffect(() => () => Object.values(previews).forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const header = (
    <div className="flex items-start justify-between gap-3 pt-2">
      <div className="min-w-0">
        <h1 className="text-[24px] font-bold leading-tight tracking-tight">{t(lang, "kyc_title")}</h1>
        <p className="mt-1 text-[14px] leading-snug text-white/80">{t(lang, "kyc_sub")}</p>
      </div>
      <LangPill lang={lang} setLang={setLang} />
    </div>
  );

  if (!order) {
    return (
      <div className="pb-28">
        <Hero
          overlap={
            <Card className="flex flex-col items-center p-6 text-center">
              <IconTile icon={ShieldCheck} tone="red" size={56} />
              <p className="mt-4 text-[15px] leading-relaxed text-ink-700">{t(lang, "kyc_noorder")}</p>
              <button onClick={onPlan} className={`${btn.primary} mt-5 w-full`}>
                {t(lang, "qa_advisor")}
                <ArrowRight size={18} />
              </button>
            </Card>
          }
        >
          {header}
        </Hero>
        <div className="mt-4 px-4">
          <ResumeCard lang={lang} onOrder={onOrder} />
        </div>
      </div>
    );
  }

  const status = order.status;
  const approved = status === "approved" || status === "in_progress" || status === "live";
  const inReview = status === "kyc_review";
  const findings: CustomerFinding[] = resp?.findings ?? order.kyc?.findings ?? [];
  const checklist: ChecklistItem[] = resp?.checklist ?? order.kyc?.checklist ?? [];
  const missing = SLOTS.filter((s) => s.required && !files[s.key]);
  const requiredCount = SLOTS.filter((s) => s.required).length;
  const showUpload = !approved && !inReview;
  const stepNow = approved || inReview || busy ? 2 : consented ? 1 : 0;

  async function submit() {
    if (!order || !consentId) return;
    setBusy(true);
    setErr("");
    try {
      const r = await api.kycUpload(order.order_id, files, consentId);
      setResp(r);
      onOrder(r.order);
    } catch (e) {
      const status = (e as { status?: number }).status;
      setErr(status ? `${t(lang, "uploadFail")} (${status})` : t(lang, "netErr"));
    } finally {
      setBusy(false);
    }
  }

  async function runCase(id: string) {
    if (!order || !consentId) return;
    setBusy(true);
    setRunning(id);
    setErr("");
    try {
      const r = await api.kycCase(order.order_id, id, consentId, useOcr && ocrOk);
      setResp(r);
      onOrder(r.order);
    } catch {
      setErr(t(lang, "netErr"));
    } finally {
      setBusy(false);
      setRunning(null);
    }
  }

  async function pick(slot: string, f: File | undefined) {
    setErr("");
    let ready: File | undefined = f;
    if (f) {
      setPreparing(slot);
      try {
        ready = await prepareUpload(f);
      } catch {
        ready = undefined;
        setErr(t(lang, "fileUnreadable"));
        const el = inputs.current[slot];
        if (el) el.value = "";
      } finally {
        setPreparing(null);
      }
    }
    setFiles((cur) => {
      const next = { ...cur };
      if (ready) next[slot] = ready;
      else delete next[slot];
      return next;
    });
  }

  return (
    <div className="pb-28">
      <Hero
        overlap={
          <Card className="p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[13px] font-semibold text-ink-500">{order.order_id}</div>
                <div className="truncate text-[16px] font-bold text-ink-900">{order.bundle_name}</div>
              </div>
              <div className="shrink-0 text-right">
                <Money value={order.tax.monthly_incl_gst} className="text-[20px] font-bold text-ink-900" />
                <div className="text-[12px] text-ink-500">
                  {t(lang, "perMonth")} · {t(lang, "inclGstShort")}
                </div>
              </div>
            </div>
            <Stepper lang={lang} now={stepNow} allDone={approved} />
          </Card>
        }
      >
        {header}
      </Hero>

      <div className="mt-4 space-y-4 px-4">
        {approved && (
          <div className="enter rounded-card bg-success-50 p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-success-600 text-white">
                <Check size={26} strokeWidth={3} />
              </span>
              <div>
                <div className="text-[17px] font-bold leading-snug text-success-600">{t(lang, "approvedMsg")}</div>
                <button onClick={onTrack} className={`${btn.primary} mt-4 bg-success-600`}>
                  {t(lang, "goTrack")}
                  <ArrowRight size={18} />
                </button>
              </div>
            </div>
          </div>
        )}

        {inReview && (
          <div className="enter rounded-card bg-warning-50 p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white text-warning-600">
                <Hourglass size={22} />
              </span>
              <div>
                <div className="text-[17px] font-bold text-warning-600">{t(lang, "reviewHead")}</div>
                <p className="mt-1 text-[14px] leading-relaxed text-ink-700">{t(lang, "reviewBody")}</p>
              </div>
            </div>
          </div>
        )}

        {showUpload && (
          <>
            {resp?.status === "incomplete" && resp.needs && (
              <Banner tone="warning" title={t(lang, "incompleteHead")}>
                <ul className="mt-1 list-disc space-y-0.5 pl-4">
                  {resp.needs.map((n) => (
                    <li key={n.slot + n.text}>{needText(n)}</li>
                  ))}
                </ul>
              </Banner>
            )}
            {resp?.status === "unavailable" && resp.message && <Banner tone="warning" title={resp.message} />}
            {status === "kyc_rejected" && <Banner tone="danger" title={t(lang, "rejectHead")}>{t(lang, "rejectBody")}</Banner>}

            <Card className={`p-4 transition-colors ${consented ? "ring-1 ring-success-600/30" : ""}`}>
              <div className="flex items-center gap-2.5">
                <IconTile icon={Lock} tone={consented ? "green" : "slate"} size={36} />
                <h2 className="text-[15px] font-semibold text-ink-900">{t(lang, "cons_title")}</h2>
              </div>
              <ul className="mt-3 space-y-2 text-[13px] leading-snug text-ink-700">
                {(["cons_purpose", "cons_noshare", "cons_mask", "cons_keep"] as const).map((k) => (
                  <li key={k} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-ink-400" />
                    {t(lang, k)}
                  </li>
                ))}
              </ul>
              <label className={`press mt-3 flex cursor-pointer items-start gap-3 rounded-2xl p-3 transition-colors ${consented ? "bg-success-50" : "bg-surface-50"}`}>
                <input
                  type="checkbox"
                  checked={consented}
                  disabled={consentBusy}
                  onChange={(e) => giveConsent(e.target.checked)}
                  className="peer sr-only"
                />
                <span
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 ${
                    consented ? "bg-success-600 text-white" : "bg-white ring-2 ring-line-200"
                  }`}
                >
                  {consentBusy ? <Loader2 size={14} className="animate-spin text-ink-500" /> : consented && <Check size={16} strokeWidth={3} />}
                </span>
                <span className="text-[14px] font-medium leading-relaxed text-ink-900">{t(lang, "cons_agree")}</span>
              </label>
              {consented && consentId && (
                <div className="fade-in mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-[12px] text-ink-500">
                  <span className="font-mono">{t(lang, "cons_recorded").replace("{id}", consentId)}</span>
                  <button onClick={() => giveConsent(false)} className="font-semibold text-brand-600 underline-offset-2 hover:underline">
                    {t(lang, "cons_withdraw")}
                  </button>
                </div>
              )}
            </Card>

            {order.business && !order.business.startsWith("New ") && (
              <div className="flex items-start gap-2.5 rounded-2xl bg-info-50 px-4 py-3 text-[13px] leading-snug text-info-600">
                <BadgeCheck size={18} className="mt-0.5 shrink-0" />
                <span>{t(lang, "name_note").replace("{name}", order.business)}</span>
              </div>
            )}

            {!consented && (
              <p className="flex items-center gap-1.5 px-1 text-[13px] font-medium text-ink-500">
                <Lock size={14} />
                {t(lang, "cons_locked")}
              </p>
            )}

            <Card className={`overflow-hidden transition-opacity ${consented ? "" : "pointer-events-none select-none opacity-45 grayscale"}`} aria-disabled={!consented}>
              {SLOTS.map((sl, i) => {
                const f = files[sl.key];
                return (
                  <div key={sl.key} className={`flex items-center gap-3 px-4 py-3.5 ${i ? "border-t border-line-100" : ""}`}>
                    <input
                      ref={(el) => {
                        inputs.current[sl.key] = el;
                      }}
                      type="file"
                      accept="image/*,application/pdf"
                      className="hidden"
                      onChange={(e) => pick(sl.key, e.target.files?.[0])}
                    />
                    {previews[sl.key] ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={previews[sl.key]} alt="" className="h-11 w-11 shrink-0 rounded-[12px] object-cover ring-1 ring-line-200" />
                    ) : (
                      <IconTile icon={sl.icon} tone={sl.tone} size={44} />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-[15px] font-semibold leading-snug text-ink-900">{t(lang, sl.labelKey)}</div>
                      {preparing === sl.key ? (
                        <div className="flex items-center gap-1 text-[13px] font-medium text-ink-500">
                          <Loader2 size={14} className="animate-spin" />
                          {t(lang, "reading")}
                        </div>
                      ) : f ? (
                        <div className="flex items-center gap-1 truncate text-[13px] font-medium text-success-600">
                          <CheckCircle2 size={14} className="shrink-0" />
                          <span className="truncate">{f.name}</span>
                        </div>
                      ) : (
                        <div className="text-[13px] text-ink-500">{sl.required ? t(lang, "required") : t(lang, "optional")}</div>
                      )}
                    </div>
                    {f ? (
                      <button
                        onClick={() => {
                          pick(sl.key, undefined);
                          const el = inputs.current[sl.key];
                          if (el) el.value = "";
                        }}
                        aria-label="remove"
                        className="press flex h-10 w-10 items-center justify-center rounded-full bg-surface-50 text-ink-500"
                      >
                        <X size={18} />
                      </button>
                    ) : (
                      <button onClick={() => inputs.current[sl.key]?.click()} className={`${btn.secondary} h-10 px-3.5`}>
                        <Camera size={16} />
                        {t(lang, "addDoc")}
                      </button>
                    )}
                  </div>
                );
              })}
            </Card>
          </>
        )}

        {(findings.length > 0 || checklist.length > 0) && !approved && (
          <Card className="p-4">
            {checklist.length > 0 && (
              <>
                <h2 className="text-[15px] font-semibold text-ink-900">{t(lang, "checking")}</h2>
                <ul className="stagger mt-3 space-y-2.5">
                  {checklist.map((c) => (
                    <li key={c.id} className="flex items-start gap-2.5 text-[14px] leading-snug text-ink-700">
                      {c.state === "ok" ? (
                        <CheckCircle2 size={20} className="shrink-0 text-success-600" />
                      ) : c.state === "check" ? (
                        <AlertTriangle size={20} className="shrink-0 text-warning-600" />
                      ) : (
                        <XCircle size={20} className="shrink-0 text-danger-600" />
                      )}
                      {tk(`kc_${c.id}`, c.label)}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {findings.length > 0 && (
              <ul className={`space-y-3 ${checklist.length ? "mt-4 border-t border-line-100 pt-4" : ""}`}>
                {findings.map((f) => (
                  <li key={f.code + f.text} className="text-[14px]">
                    <div className="font-medium text-ink-900">{tk(`kf_${f.code}`, f.text)}</div>
                    {f.action && <div className="mt-0.5 text-[13px] text-ink-500">{tk(`kfa_${f.code}`, f.action)}</div>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {!approved && (
          <Card className="p-4">
            {order.assist ? (
              <PersonCard label={t(lang, "partnerCard")} name={order.assist.name} sub={order.assist.city} phone={order.assist.phone} callLabel={t(lang, "callEngineer")} />
            ) : (
              <div className="flex items-start gap-3">
                <IconTile icon={LifeBuoy} tone="blue" size={44} />
                <div className="flex-1">
                  <p className="text-[14px] leading-snug text-ink-700">{t(lang, "needHelp")}</p>
                  <button
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        onOrder(await api.assist(order.order_id));
                      } finally {
                        setBusy(false);
                      }
                    }}
                    className={`${btn.secondary} mt-3`}
                  >
                    {t(lang, "askPartner")}
                  </button>
                </div>
              </div>
            )}
          </Card>
        )}

        {showUpload && <SaveCard lang={lang} order={order} />}

        {cases.length > 0 && showUpload && (
          <Card className={`p-4 transition-opacity ${consented ? "" : "pointer-events-none select-none opacity-45 grayscale"}`} aria-disabled={!consented}>
            <div className="flex items-start gap-3">
              <IconTile icon={FileText} tone="teal" size={40} />
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-[15px] font-semibold text-ink-900">
                  {t(lang, "smp_title")}
                  <span className="rounded-md bg-warning-50 px-1.5 py-0.5 text-[11px] font-bold text-warning-600">DEMO</span>
                </div>
                <p className="text-[13px] leading-snug text-ink-500">{t(lang, "smp_sub")}</p>
              </div>
            </div>
            {ocrOk && (
              <label className="mt-3 flex cursor-pointer items-center gap-2.5 rounded-xl bg-surface-50 px-3 py-2.5 text-[13px] font-medium text-ink-700">
                <input type="checkbox" checked={useOcr} onChange={(e) => setUseOcr(e.target.checked)} className="h-4 w-4 accent-[#D2131B]" />
                <ScanText size={16} className="text-aqua-600" />
                {t(lang, "smp_ocr")}
              </label>
            )}
            <div className="mt-3 grid grid-cols-3 gap-2">
              {cases.map((c) => (
                <button
                  key={c.case_id}
                  disabled={busy}
                  onClick={() => runCase(c.case_id)}
                  className="press relative overflow-hidden rounded-2xl bg-surface-50 text-left ring-1 ring-line-200 disabled:opacity-50"
                >
                  {c.documents?.includes("gst_certificate") && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={kycDocUrl(c.case_id, "gst_certificate")} alt="" loading="lazy" className="h-14 w-full object-cover object-top opacity-80" />
                  )}
                  <div className="px-2 py-2">
                    <div className="flex items-center gap-1 text-[13px] font-bold text-ink-900">
                      {running === c.case_id && <Loader2 size={12} className="animate-spin" />}
                      {c.case_id}
                    </div>
                    <div className="truncate text-[12px] text-ink-500">{c.business}</div>
                  </div>
                </button>
              ))}
            </div>
            {running && <p className="mt-2 text-[12px] font-medium text-ink-500">{t(lang, "smp_running")}</p>}
          </Card>
        )}
      </div>

      {showUpload && (
        <div className="sticky bottom-[88px] z-20 mt-4 px-3">
          <div className="flex items-center justify-between gap-3 rounded-[22px] bg-white p-3 pl-4 shadow-float">
            <div className="min-w-0 flex-1 text-[13px] font-semibold leading-snug text-ink-700">
              {t(lang, "docsAdded").replace("{a}", String(requiredCount - missing.length)).replace("{b}", String(requiredCount))}
              {err && <div className="text-danger-600">{err}</div>}
            </div>
            <button onClick={submit} disabled={busy || !!preparing || !consented || missing.length > 0} className={`${btn.primary} max-w-[58%]`}>
              {busy ? <Loader2 size={18} className="animate-spin" /> : null}
              {busy ? t(lang, "reading") : status === "kyc_rejected" ? t(lang, "reupload") : t(lang, "verifyBtn")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Stepper({ lang, now, allDone }: { lang: Lang; now: number; allDone: boolean }) {
  const steps = ["kstep_consent", "kstep_docs", "kstep_check"];
  return (
    <ol className="mt-4 flex items-center">
      {steps.map((k, i) => {
        const done = allDone || i < now;
        const cur = !allDone && i === now;
        return (
          <li key={k} className="flex flex-1 items-center last:flex-none">
            <span className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-[13px] font-bold transition-colors ${
                  done ? "bg-success-600 text-white" : cur ? "bg-brand-600 text-white ring-4 ring-brand-100" : "bg-line-100 text-ink-500"
                }`}
              >
                {done ? <Check size={15} strokeWidth={3} /> : i + 1}
              </span>
              <span className={`text-[13px] font-semibold ${done ? "text-success-600" : cur ? "text-ink-900" : "text-ink-400"}`}>{t(lang, k)}</span>
            </span>
            {i < steps.length - 1 && <span className={`mx-2 h-0.5 flex-1 rounded-full ${done ? "bg-success-600" : "bg-line-200"}`} />}
          </li>
        );
      })}
    </ol>
  );
}

function Banner({ tone, title, children }: { tone: "warning" | "danger"; title: string; children?: React.ReactNode }) {
  const c = tone === "danger" ? "bg-danger-50 text-danger-600" : "bg-warning-50 text-warning-600";
  return (
    <div className={`enter flex gap-3 rounded-card p-4 ${c}`}>
      {tone === "danger" ? <XCircle size={20} className="mt-0.5 shrink-0" /> : <AlertTriangle size={20} className="mt-0.5 shrink-0" />}
      <div className="text-[14px] leading-relaxed">
        <div className="font-bold">{title}</div>
        {children && <div className="text-ink-700">{children}</div>}
      </div>
    </div>
  );
}
