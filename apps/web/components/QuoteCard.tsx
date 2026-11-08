"use client";
import { useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, BadgeIndianRupee, CalendarClock, ChevronDown, Clock, Lock, Minus, Pencil, Plus, ShieldCheck, Trash2, Users, Wrench, Zap, Percent } from "lucide-react";
import { api, Profile, Quote, QuoteLine, SuitableResult, SuitableProduct, rupees } from "@/lib/api";
import { FLOW, Lang, label, t } from "@/lib/i18n";
import LangPill from "./LangPill";
import { cityLabel } from "@/lib/i18n/more";

const CORE = new Set(["P01", "P02", "P03", "P04", "P05", "P06"]);
const SINGLE_UNITS = new Set(["per account", "per pack"]);

export function lineLabel(lang: Lang, pid: string, fallback: string): string {
  if (lang === "en") return fallback;
  const k = `pl_${pid}`;
  const v = t(lang, k);
  return v === k ? fallback : v;
}
import { Card, Chip, CountUp, IconTile, Money, TONE, btn, num, productLook } from "./ui";

export default function QuoteCard({
  quote,
  catalog,
  profile,
  onQuote,
  onProceed,
  onBack,
  setLang,
  lang,
}: {
  quote: Quote;
  catalog: SuitableResult | null;
  profile: Profile;
  onQuote: (q: Quote) => void;
  onProceed: () => void;
  onBack: () => void;
  setLang: (l: Lang) => void;
  lang: Lang;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [billOpen, setBillOpen] = useState(true);
  const items = Object.fromEntries(quote.lines.map((l) => [l.product_id, l.qty]));
  const blocked = quote.status === "blocked";

  const detail: Record<string, SuitableProduct> = {};
  for (const p of catalog?.products ?? []) detail[p.product_id] = p;
  const missingPre = (id: string) => {
    const need = detail[id]?.requires_one_of ?? [];
    if (!need.length || need.some((x) => items[x])) return null;
    return need.find((x) => detail[x]?.eligible) ?? "";
  };
  const addons = (catalog?.products ?? []).filter((p) => p.eligible && !items[p.product_id] && missingPre(p.product_id) !== "");
  const neededBy = (id: string) =>
    quote.lines
      .filter((l) => {
        const need = detail[l.product_id]?.requires_one_of ?? [];
        return l.product_id !== id && need.includes(id) && !need.some((x) => x !== id && items[x]);
      })
      .map((l) => lineLabel(lang, l.product_id, l.label ?? l.name));

  async function setItems(next: Record<string, number>) {
    setBusy(true);
    try {
      const list = Object.entries(next).map(([product_id, qty]) => ({ product_id, qty }));
      onQuote(await api.quote(profile, list));
    } catch {
      /* keep current */
    } finally {
      setBusy(false);
    }
  }
  const addProduct = (id: string) => {
    const pre = missingPre(id);
    setItems(pre ? { ...items, [pre]: 1, [id]: 1 } : { ...items, [id]: 1 });
  };
  const setQty = (id: string, n: number) => setItems({ ...items, [id]: n });
  const maxQty = (l: QuoteLine) => (l.unit === "per site" ? Math.max(1, profile.num_sites) : 50);
  const removeProduct = (id: string) => {
    const next = { ...items };
    delete next[id];
    setItems(next);
  };

  const bizOpt = FLOW[0].options?.find((o) => o.value === profile.business_type);
  const chips = [
    bizOpt ? label(bizOpt, lang) : null,
    profile.employees ? t(lang, "staffN").replace("{n}", String(profile.employees)) : null,
    profile.num_sites === 1 ? t(lang, "sitesOne") : profile.num_sites ? t(lang, "sitesN").replace("{n}", String(profile.num_sites)) : null,
    profile.city ? cityLabel(profile.city, lang) : null,
  ].filter(Boolean) as string[];

  const ex = quote.tax ? num(quote.tax.monthly_ex_gst) : num(quote.monthly_inr);
  const gst = quote.tax ? num(quote.tax.monthly_gst) : 0;
  const exPct = ex + gst > 0 ? (ex / (ex + gst)) * 100 : 100;

  return (
    <div>
      <section className="relative">
        <div className="hero-band absolute inset-x-0 top-0 bottom-24 rounded-b-hero" />
        <div className="relative px-4 pt-4 text-white">
          <div className="flex items-center justify-between">
            <button onClick={onBack} aria-label={t(lang, "editAnswers")} className="press flex h-10 w-10 items-center justify-center rounded-full bg-white/15">
              <ArrowLeft size={20} />
            </button>
            <LangPill lang={lang} setLang={setLang} />
          </div>
          <p className="mt-4 text-[14px] font-medium text-white/80">{t(lang, "plan_reco")}</p>
          <h1 className="text-[26px] font-bold leading-tight tracking-tight">{quote.bundle_name ?? t(lang, "planFor")}</h1>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span key={c} className="rounded-full bg-white/15 px-3 py-1 text-[13px] font-semibold">
                {c}
              </span>
            ))}
            <button onClick={onBack} className="press flex items-center gap-1 rounded-full bg-white px-3 py-1 text-[13px] font-semibold text-brand-600">
              <Pencil size={13} />
              {t(lang, "editAnswers")}
            </button>
          </div>
        </div>

        <div className="enter relative mt-5 px-4">
          <Card className="p-5">
            <div className="flex items-end gap-1.5">
              <Money value={quote.monthly_inr} className="text-[44px] font-bold leading-none tracking-tight text-ink-900" />
              <span className="pb-1 text-[15px] font-medium text-ink-500">
                {t(lang, "perMonth")} + GST
              </span>
            </div>
            {quote.tax && (
              <div className="mt-1.5 text-[14px] text-ink-500">
                {t(lang, "inclGstLine").replace("{x}", rupees(quote.tax.monthly_incl_gst))}
              </div>
            )}
            <div className="stagger mt-4 grid grid-cols-3 gap-2">
              <Fact tone="amber" icon={Zap} value={<CountUp value={quote.setup_total_inr} format={(v) => rupees(Math.round(v))} />} label={t(lang, "setupCard")} />
              <Fact tone="blue" icon={CalendarClock} value={`${quote.contract_months} ${t(lang, "months")}`} label={t(lang, "contractCard")} />
              <Fact tone="green" icon={Clock} value={`~${quote.activation_eta_days} ${t(lang, "days")}`} label={t(lang, "liveIn")} />
            </div>
            {!blocked && (
              <p className="mt-3 flex items-start gap-1.5 text-[12px] leading-snug text-ink-500">
                <ShieldCheck size={14} className="mt-0.5 shrink-0 text-success-600" />
                {t(lang, "rulesChecked")}
              </p>
            )}
          </Card>
        </div>
      </section>

      <div className="mt-6 space-y-6 px-4">
        {blocked && (
          <div className="flex gap-3 rounded-card bg-danger-50 p-4 text-[14px] text-danger-600">
            <AlertTriangle size={20} className="mt-0.5 shrink-0" />
            <div className="space-y-1">
              {quote.violations
                .filter((v) => v.severity === "block")
                .map((v) => (
                  <p key={v.rule + v.product}>{v.message}</p>
                ))}
            </div>
          </div>
        )}

        <section>
          <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink-900">{t(lang, "included")}</h2>
          <div className="stagger space-y-2.5">
            {quote.lines.map((l: QuoteLine) => {
              const look = productLook(l.category, l.name);
              const isOpen = open === l.product_id;
              return (
                <div key={l.product_id} className={`rounded-card ${TONE[look.tone].tint} ring-1 ring-black/[0.03]`}>
                  <button onClick={() => setOpen(isOpen ? null : l.product_id)} aria-expanded={isOpen} className="flex w-full items-start gap-3 p-4 text-left">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] bg-white">
                      <look.icon size={22} strokeWidth={1.9} className={TONE[look.tone].icon} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[16px] font-semibold leading-snug text-ink-900">
                        {lineLabel(lang, l.product_id, l.label ?? l.name)}
                        {l.qty > 1 && <span className="font-medium text-ink-500"> ×{l.qty}</span>}
                      </span>
                      {l.spec && l.spec !== l.label && <span className="block text-[13px] text-ink-500">{l.spec}</span>}
                      {l.kind && (
                        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-[12px] font-semibold text-ink-700">
                          {l.kind === "field" ? <Wrench size={12} /> : <Zap size={12} />}
                          {l.kind === "field" ? t(lang, "visitNeeded") : t(lang, "remoteOk")}
                        </span>
                      )}
                    </span>
                    <span className="flex flex-col items-end gap-2">
                      <span className="text-[16px] font-bold tabular-nums text-ink-900">{rupees(l.line_monthly_list_inr)}</span>
                      <ChevronDown size={18} className={`text-ink-400 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                    </span>
                  </button>
                  {isOpen && (
                    <div className="fade-in -mt-1 px-4 pb-4 pl-[72px] text-[13px] leading-relaxed text-ink-700">
                      {detail[l.product_id]?.description && <p>{detail[l.product_id].description}</p>}
                      {l.popularity != null && l.popularity >= 20 && (
                        <Chip tone="success" icon={Users} className="mt-2">
                          {t(lang, "similar").replace("{n}", String(l.popularity))}
                        </Chip>
                      )}
                      {l.note && <p className="mt-2 text-ink-500">{l.note}</p>}
                      <p className="mt-2 text-ink-500">
                        {rupees(l.unit_list_inr)}/{l.unit}
                        {l.qty > 1 && ` × ${l.qty}`} · {l.setup_inr > 0 ? `${rupees(l.setup_inr)} ${t(lang, "setup")}` : t(lang, "noSetup")} · ~{l.install_days} {t(lang, "days")}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        {!SINGLE_UNITS.has(l.unit) && (
                          <span className="inline-flex h-9 items-center gap-1 rounded-full bg-white px-1 ring-1 ring-line-200">
                            <button
                              disabled={busy || l.qty <= 1}
                              onClick={() => setQty(l.product_id, l.qty - 1)}
                              aria-label={`${t(lang, "qtyLabel")} -1`}
                              className="press flex h-7 w-7 items-center justify-center rounded-full text-ink-900 disabled:opacity-30"
                            >
                              <Minus size={15} />
                            </button>
                            <span className="min-w-[2ch] text-center text-[14px] font-bold tabular-nums text-ink-900">{l.qty}</span>
                            <button
                              disabled={busy || l.qty >= maxQty(l)}
                              onClick={() => setQty(l.product_id, l.qty + 1)}
                              aria-label={`${t(lang, "qtyLabel")} +1`}
                              className="press flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-white disabled:opacity-30"
                            >
                              <Plus size={15} />
                            </button>
                          </span>
                        )}
                        {neededBy(l.product_id).length > 0 ? (
                          <span className="inline-flex h-9 items-center gap-1.5 rounded-full bg-white/70 px-3 text-[12px] font-semibold text-ink-500">
                            <Lock size={12} />
                            {t(lang, "neededFor").replace("{x}", neededBy(l.product_id).join(", "))}
                          </span>
                        ) : CORE.has(l.product_id) ? (
                          <span className="inline-flex h-9 items-center gap-1.5 rounded-full bg-white/70 px-3 text-[12px] font-semibold text-ink-500">
                            <Lock size={12} />
                            {t(lang, "coreLocked")}
                          </span>
                        ) : (
                          quote.lines.length > 1 && (
                            <button
                              disabled={busy}
                              onClick={() => removeProduct(l.product_id)}
                              className="press inline-flex h-9 items-center gap-1.5 rounded-full bg-white px-3 text-[13px] font-semibold text-danger-600 ring-1 ring-danger-50 disabled:opacity-40"
                            >
                              <Trash2 size={14} />
                              {t(lang, "removeLbl")}
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {addons.length > 0 && (
          <section>
            <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink-900">{t(lang, "addons")}</h2>
            <div className="no-scrollbar -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1">
              {addons.map((p) => {
                const look = productLook(p.category, p.name);
                return (
                  <div key={p.product_id} className="flex w-[220px] shrink-0 snap-start flex-col rounded-card bg-white p-4 shadow-soft">
                    <IconTile icon={look.icon} tone={look.tone} size={40} />
                    <div className="mt-3 line-clamp-2 text-[15px] font-semibold leading-snug text-ink-900">{lineLabel(lang, p.product_id, p.label ?? p.name)}</div>
                    {p.description && <p className="mt-1 line-clamp-2 text-[13px] leading-snug text-ink-500">{p.description}</p>}
                    {missingPre(p.product_id) && (
                      <p className="mt-1.5 text-[12px] font-semibold leading-snug text-info-600">
                        {t(lang, "addsAlso").replace("{x}", lineLabel(lang, missingPre(p.product_id)!, detail[missingPre(p.product_id)!]?.label ?? detail[missingPre(p.product_id)!]?.name ?? ""))}
                      </p>
                    )}
                    <div className="mt-auto flex items-end justify-between pt-3">
                      <div>
                        <div className="text-[17px] font-bold tabular-nums text-ink-900">{rupees(p.price_inr)}</div>
                        <div className="text-[12px] text-ink-500">/{p.unit}</div>
                      </div>
                      <button
                        disabled={busy}
                        onClick={() => addProduct(p.product_id)}
                        aria-label={`${t(lang, "addLabel")} ${p.label ?? p.name}`}
                        className="press flex h-11 w-11 items-center justify-center rounded-full bg-brand-600 text-white disabled:opacity-40"
                      >
                        <Plus size={20} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {quote.tax && (
          <Card className="p-4">
            <button onClick={() => setBillOpen((o) => !o)} aria-expanded={billOpen} className="flex w-full items-center justify-between">
              <span className="flex items-center gap-3">
                <IconTile icon={BadgeIndianRupee} tone="amber" size={36} />
                <span className="text-[16px] font-semibold text-ink-900">{t(lang, "monthlyBill")}</span>
              </span>
              <ChevronDown size={20} className={`text-ink-400 transition-transform ${billOpen ? "rotate-180" : ""}`} />
            </button>
            {billOpen && (
              <div className="fade-in mt-4">
                <div className="flex h-2.5 overflow-hidden rounded-full bg-line-100">
                  <div className="bar-in h-full bg-brand-500" style={{ width: `${exPct}%` }} />
                  <div className="bar-in h-full bg-warning-600/70" style={{ width: `${100 - exPct}%`, animationDelay: "400ms" }} />
                </div>
                <div className="mt-4 space-y-2 text-[14px] text-ink-700">
                  <Row dot="bg-brand-500" k={`${t(lang, "monthlyBill")} (${t(lang, "exclGst")})`} v={rupees(quote.tax.monthly_ex_gst)} />
                  <Row dot="bg-warning-600/70" k={`${t(lang, "gstLabel")} (${quote.tax.rate_pct}%)`} v={rupees(quote.tax.monthly_gst)} />
                  <div className="border-t border-line-100 pt-2">
                    <Row k={t(lang, "totalIncl")} v={rupees(quote.tax.monthly_incl_gst)} strong />
                  </div>
                </div>
                <div className={`mt-3 flex gap-2 rounded-2xl p-3 text-[13px] leading-snug ${quote.tax.itc_eligible ? "bg-success-50 text-success-600" : "bg-surface-50 text-ink-500"}`}>
                  <Percent size={16} className="mt-0.5 shrink-0" />
                  {quote.tax.itc_eligible ? t(lang, "itcYes").replace("{x}", rupees(quote.tax.itc_monthly)) : t(lang, "itcNo")}
                </div>
              </div>
            )}
          </Card>
        )}
      </div>

      <div className="sticky bottom-[88px] z-20 mt-6 px-3">
        <div className="flex items-center justify-between gap-3 rounded-[22px] bg-white p-3 pl-4 shadow-float">
          <div className="min-w-0">
            <div className="text-[17px] font-bold leading-tight text-ink-900">
              {rupees(quote.monthly_inr)}
              <span className="text-[13px] font-medium text-ink-500">
                {t(lang, "perMonth")} + GST
              </span>
            </div>
            {quote.tax && <div className="text-[12px] text-ink-500">{t(lang, "inclGstLine").replace("{x}", rupees(quote.tax.monthly_incl_gst))}</div>}
          </div>
          <button disabled={blocked || busy} onClick={onProceed} className={`${btn.primary} shrink-0`}>
            {t(lang, "acceptVerify")}
            <ArrowRight size={18} />
          </button>
        </div>
      </div>
      <div className="h-[96px]" aria-hidden="true" />
    </div>
  );
}

function Fact({ tone, icon: Icon, value, label: l }: { tone: "amber" | "blue" | "green"; icon: typeof Zap; value: React.ReactNode; label: string }) {
  return (
    <div className={`flex flex-col items-center rounded-2xl px-1 py-3 text-center ${TONE[tone].tint}`}>
      <span className={`flex h-8 w-8 items-center justify-center rounded-[10px] bg-white ${TONE[tone].icon}`}>
        <Icon size={16} strokeWidth={2} />
      </span>
      <span className="mt-2 text-[15px] font-bold tabular-nums leading-tight text-ink-900">{value}</span>
      <span className={`text-[12px] font-semibold ${TONE[tone].icon}`}>{l}</span>
    </div>
  );
}

function Row({ k, v, strong, dot }: { k: string; v: string; strong?: boolean; dot?: string }) {
  return (
    <div className={`flex items-center justify-between gap-3 ${strong ? "text-[15px] font-bold text-ink-900" : ""}`}>
      <span className="flex items-center gap-2">
        {dot && <span className={`h-2 w-2 rounded-full ${dot}`} />}
        {k}
      </span>
      <span className="tabular-nums">{v}</span>
    </div>
  );
}
