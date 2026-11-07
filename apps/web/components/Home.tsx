"use client";
import {
  Plus,
  ArrowRight,
  BadgeIndianRupee,
  CalendarClock,
  ChevronRight,
  Factory,
  Gauge,
  Keyboard,
  Languages,
  Mic,
  MessageSquareText,
  Percent,
  ReceiptIndianRupee,
  ShieldCheck,
  Stethoscope,
  Store,
  Truck,
  UploadCloud,
  Users,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { Order, Quote } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";
import LangPill from "./LangPill";
import { AccelLogo } from "./Logo";
import { Card, Chip, ChipTone, CountUp, Hero, IconTile, LiveDot, Money, Ring, SectionTitle, Segments, Tone, btn, inr } from "./ui";

export type Tab = "home" | "advisor" | "kyc" | "tracker";

const STEP_KEYS = ["stepOrdered", "stepVerified", "stepSetup", "stepLive"];

export function orderProgress(o: Order): { done: number; current: number | null } {
  if (o.status === "live") return { done: 4, current: null };
  if (o.status === "approved" || o.status === "in_progress") return { done: 2, current: 2 };
  return { done: 1, current: 1 };
}

export function statusTone(s: Order["status"]): ChipTone {
  if (s === "live" || s === "approved") return "success";
  if (s === "kyc_review") return "warning";
  if (s === "kyc_rejected" || s === "cancelled") return "danger";
  if (s === "in_progress") return "info";
  return "neutral";
}

const SEGS: { seg: string; tone: Tone; icon: LucideIcon }[] = [
  { seg: "micro", tone: "red", icon: Store },
  { seg: "prof", tone: "blue", icon: Stethoscope },
  { seg: "multi", tone: "teal", icon: Users },
  { seg: "mfg", tone: "amber", icon: Factory },
];

export default function Home({
  lang,
  setLang,
  order,
  quote,
  onStart,
  go,
  onNew,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  order: Order | null;
  quote: Quote | null;
  onStart: (mode: "text" | "voice") => void;
  go: (tab: Tab) => void;
  onNew?: () => void;
}) {
  const [seg, setSeg] = useState("micro");
  const needsKyc = order && (order.status === "awaiting_kyc" || order.status === "kyc_rejected");

  const actions: { icon: LucideIcon; tone: Tone; label: string; onClick: () => void }[] = [
    { icon: MessageSquareText, tone: "blue", label: t(lang, "qa_advisor"), onClick: () => (quote || order ? go("advisor") : onStart("text")) },
    { icon: Mic, tone: "red", label: t(lang, "qa_voice"), onClick: () => (quote || order ? go("advisor") : onStart("voice")) },
    { icon: UploadCloud, tone: "green", label: t(lang, "qa_docs"), onClick: () => go("kyc") },
    { icon: Truck, tone: "teal", label: t(lang, "qa_track"), onClick: () => go("tracker") },
  ];

  return (
    <div className="pb-28">
      <Hero overlap={<StatusCard lang={lang} order={order} quote={quote} onStart={onStart} go={go} />}>
        <div className="flex items-center justify-between pt-2">
          <AccelLogo onDark />
          <LangPill lang={lang} setLang={setLang} />
        </div>
        <div className="mt-6">
          <p className="text-[14px] font-medium text-white/80">{order?.business ? t(lang, "home_greet") : t(lang, "home_sub")}</p>
          <h1 className="mt-0.5 text-[24px] font-bold leading-tight tracking-tight">{order?.business ?? t(lang, "home_guest")}</h1>
          {(order || quote) && onNew && (
            <button
              onClick={() => window.confirm(t(lang, "newBizAsk")) && onNew()}
              className="press mt-2 inline-flex h-8 items-center gap-1.5 rounded-full bg-white/15 px-3 text-[13px] font-semibold text-white"
            >
              <Plus size={14} />
              {t(lang, "newBiz")}
            </button>
          )}
        </div>
      </Hero>

      <div className="mt-4 space-y-6 px-4">
        {order ? (
          <div className="stagger grid grid-cols-2 gap-3">
            <Card className="p-4">
              <IconTile icon={ReceiptIndianRupee} tone="amber" size={36} />
              <div className="mt-3 text-[13px] font-semibold text-ink-500">{t(lang, "monthlyBill")}</div>
              <Money value={order.tax.monthly_incl_gst} className="mt-0.5 block text-[22px] font-bold leading-tight text-ink-900" />
              <div className="text-[12px] font-medium text-ink-500">{t(lang, "inclGstShort")}</div>
            </Card>
            <Card className="p-4">
              <IconTile icon={Percent} tone="green" size={36} />
              <div className="mt-3 text-[13px] font-semibold text-ink-500">{t(lang, "itcCard")}</div>
              {order.tax.itc_eligible ? (
                <>
                  <Money value={order.tax.itc_monthly} className="mt-0.5 block text-[22px] font-bold leading-tight text-success-600" />
                  <div className="text-[12px] font-medium text-ink-500">{t(lang, "itcPerMonth")}</div>
                </>
              ) : (
                <div className="mt-1 text-[13px] font-medium leading-snug text-ink-700">{t(lang, "itcAdd")}</div>
              )}
            </Card>
            {order.engineer ? (
              <Card className="col-span-2 flex items-center gap-3 p-4">
                <IconTile icon={Wrench} tone="blue" size={44} />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-ink-500">{t(lang, "engineerCard")}</div>
                  <div className="truncate text-[16px] font-semibold text-ink-900">{order.engineer.name}</div>
                  <div className="truncate text-[13px] text-ink-500">{order.engineer.city}</div>
                </div>
                <a href={`tel:${order.engineer.phone.replace(/[^\d+]/g, "")}`} className={`${btn.secondary} h-10 px-3.5`}>
                  {t(lang, "callEngineer")}
                </a>
              </Card>
            ) : null}
            <Card className="p-4">
              <IconTile icon={CalendarClock} tone="blue" size={36} />
              <div className="mt-3 text-[13px] font-semibold text-ink-500">{t(lang, "contractCard")}</div>
              <div className="text-[20px] font-bold text-ink-900">
                <CountUp value={order.contract_months} format={(v) => String(Math.round(v))} /> {t(lang, "months")}
              </div>
            </Card>
            <Card className="p-4">
              <IconTile icon={BadgeIndianRupee} tone="teal" size={36} />
              <div className="mt-3 text-[13px] font-semibold text-ink-500">{t(lang, "setupCard")}</div>
              <div className="text-[20px] font-bold text-ink-900">
                <CountUp value={order.setup_total_inr} format={(v) => inr(v)} />
              </div>
            </Card>
          </div>
        ) : (
          <section>
            <SectionTitle>{t(lang, "why_title")}</SectionTitle>
            <div className="stagger grid grid-cols-2 gap-3">
              <WhyCard icon={BadgeIndianRupee} tone="red" title={t(lang, "why_price")} sub={t(lang, "why_price_sub")} />
              <WhyCard icon={Percent} tone="green" title={t(lang, "why_gst")} sub={t(lang, "why_gst_sub")} />
              <WhyCard icon={Gauge} tone="blue" title={t(lang, "why_fast")} sub={t(lang, "why_fast_sub")} />
              <WhyCard icon={Languages} tone="teal" title={t(lang, "why_lang")} sub={t(lang, "why_lang_sub")} />
            </div>
          </section>
        )}

        <section>
          <SectionTitle>{t(lang, "quickActions")}</SectionTitle>
          <div className="stagger grid grid-cols-4 gap-2">
            {actions.map((a) => (
              <button key={a.label} onClick={a.onClick} className="press relative flex flex-col items-center gap-2 rounded-2xl py-1 text-center">
                <IconTile icon={a.icon} tone={a.tone} size={52} />
                <span className="text-[12px] font-semibold leading-tight text-ink-900">{a.label}</span>
                {a.icon === UploadCloud && needsKyc && <span className="absolute right-3 top-0 h-2.5 w-2.5 rounded-full border-2 border-surface-50 bg-brand-500" />}
              </button>
            ))}
          </div>
        </section>

        {!order && (
          <section>
            <SectionTitle>{t(lang, "popular_title")}</SectionTitle>
            <div className="no-scrollbar -mx-4 mb-3 flex gap-2 overflow-x-auto px-4">
              {SEGS.map((s) => (
                <button
                  key={s.seg}
                  onClick={() => setSeg(s.seg)}
                  className={`press shrink-0 whitespace-nowrap rounded-full px-4 py-2 text-[13px] font-semibold transition-colors ${
                    seg === s.seg ? "bg-ink-900 text-white" : "bg-white text-ink-700 ring-1 ring-line-200"
                  }`}
                >
                  {t(lang, `seg_${s.seg}`)}
                </button>
              ))}
            </div>
            {SEGS.filter((s) => s.seg === seg).map((s) => (
              <SegmentCard key={s.seg} lang={lang} seg={s.seg} tone={s.tone} icon={s.icon} onStart={() => onStart("text")} />
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

function StatusCard({
  lang,
  order,
  quote,
  onStart,
  go,
}: {
  lang: Lang;
  order: Order | null;
  quote: Quote | null;
  onStart: (mode: "text" | "voice") => void;
  go: (tab: Tab) => void;
}) {
  if (order) {
    const { done, current } = orderProgress(order);
    const pct = order.total_count ? Math.round((order.live_count / order.total_count) * 100) : 0;
    const needsKyc = order.status === "awaiting_kyc" || order.status === "kyc_rejected";
    return (
      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[13px] font-semibold text-ink-500">{t(lang, "yourSetup")}</span>
          <Chip tone={statusTone(order.status)}>
            {order.status !== "live" && <LiveDot color={order.status === "kyc_rejected" ? "bg-danger-600" : order.status === "kyc_review" ? "bg-warning-600" : "bg-success-600"} />}
            {t(lang, `st_${order.status}`)}
          </Chip>
        </div>
        <div className="flex gap-4">
          <Ring pct={pct} size={92} stroke={8} color={pct === 100 ? "#0E8A4E" : "#ED1C24"}>
            <span className="text-[20px] font-bold leading-none text-ink-900">
              <CountUp value={pct} format={(v) => `${Math.round(v)}%`} />
            </span>
            <span
              className="mt-1 text-[11px] font-semibold tabular-nums text-ink-500"
              title={t(lang, "servicesLive").replace("{a}", String(order.live_count)).replace("{b}", String(order.total_count))}
            >
              {order.live_count}/{order.total_count}
            </span>
          </Ring>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[16px] font-bold text-ink-900">{order.bundle_name ?? order.order_id}</div>
            <div className="mb-3 text-[13px] text-ink-500">
              <Money value={order.tax.monthly_ex_gst} />
              {t(lang, "perMonth")} + GST
            </div>
            <Segments labels={STEP_KEYS.map((k) => t(lang, k))} done={done} current={current} />
          </div>
        </div>
        <button onClick={() => go(needsKyc ? "kyc" : "tracker")} className={`${btn.primary} mt-4 w-full`}>
          {needsKyc ? t(lang, "verifyBtn") : t(lang, "goTrack")}
          <ArrowRight size={18} />
        </button>
      </Card>
    );
  }

  if (quote) {
    return (
      <Card className="p-4">
        <div className="text-[13px] font-semibold text-ink-500">{t(lang, "home_quote_title")}</div>
        <div className="mt-1 flex items-end justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[17px] font-bold text-ink-900">{quote.bundle_name}</div>
            <div className="text-[13px] text-ink-500">{t(lang, "home_quote_next")}</div>
          </div>
          <div className="shrink-0 text-right">
            <Money value={quote.monthly_inr} className="text-[26px] font-bold leading-none text-ink-900" />
            <div className="text-[12px] font-medium text-ink-500">{t(lang, "perMonth")} + GST</div>
          </div>
        </div>
        <button onClick={() => go("advisor")} className={`${btn.primary} mt-4 w-full`}>
          {t(lang, "home_continue")}
          <ArrowRight size={18} />
        </button>
      </Card>
    );
  }

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <IconTile icon={ShieldCheck} tone="red" size={44} />
        <div>
          <div className="text-[18px] font-bold leading-snug text-ink-900">{t(lang, "home_start_title")}</div>
          <p className="mt-1 text-[14px] leading-snug text-ink-500">{t(lang, "home_start_body")}</p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button onClick={() => onStart("voice")} className={btn.primary}>
          <Mic size={18} />
          {t(lang, "home_start_voice")}
        </button>
        <button onClick={() => onStart("text")} className={btn.dark}>
          <Keyboard size={18} />
          {t(lang, "home_start_text")}
        </button>
      </div>
    </Card>
  );
}

function WhyCard({ icon, tone, title, sub }: { icon: LucideIcon; tone: Tone; title: string; sub: string }) {
  return (
    <Card className="p-4">
      <IconTile icon={icon} tone={tone} size={36} />
      <div className="mt-3 text-[15px] font-semibold leading-snug text-ink-900">{title}</div>
      <div className="mt-0.5 text-[13px] leading-snug text-ink-500">{sub}</div>
    </Card>
  );
}

const TINT: Record<Tone, string> = {
  red: "bg-brand-50",
  blue: "bg-info-50",
  teal: "bg-aqua-50",
  amber: "bg-warning-50",
  green: "bg-success-50",
  slate: "bg-slate2-50",
};
const SOLID: Record<Tone, string> = {
  red: "bg-brand-600",
  blue: "bg-info-600",
  teal: "bg-aqua-600",
  amber: "bg-warning-600",
  green: "bg-success-600",
  slate: "bg-ink-700",
};
const TEXT: Record<Tone, string> = {
  red: "text-brand-600",
  blue: "text-info-600",
  teal: "text-aqua-600",
  amber: "text-warning-600",
  green: "text-success-600",
  slate: "text-ink-700",
};

function SegmentCard({ lang, seg, tone, icon: Icon, onStart }: { lang: Lang; seg: string; tone: Tone; icon: LucideIcon; onStart: () => void }) {
  const items = t(lang, `pop_${seg}`).split("|");
  return (
    <button onClick={onStart} className={`press enter block w-full rounded-card p-5 text-left ${TINT[tone]}`}>
      <div className="flex items-center gap-3">
        <span className={`flex h-11 w-11 items-center justify-center rounded-2xl bg-white ${TEXT[tone]}`}>
          <Icon size={22} strokeWidth={1.9} />
        </span>
        <span className="text-[17px] font-bold text-ink-900">{t(lang, `seg_${seg}`)}</span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {items.map((it) => (
          <li key={it} className="flex items-center gap-2.5 text-[14px] font-medium text-ink-700">
            <span className={`h-1.5 w-1.5 rounded-full ${SOLID[tone]}`} />
            {it}
          </li>
        ))}
      </ul>
      <div className="mt-5 flex items-center justify-between">
        <span className={`text-[14px] font-semibold ${TEXT[tone]}`}>{t(lang, "popular_cta")}</span>
        <span className={`flex h-11 w-11 items-center justify-center rounded-full text-white ${SOLID[tone]}`}>
          <ChevronRight size={20} />
        </span>
      </div>
    </button>
  );
}
