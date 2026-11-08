"use client";
import { ArrowRight, CalendarCheck, CheckCircle2, Clock, Loader, MessageCircle, Package, PartyPopper, Wrench, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Order, OrderLine } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";
import LangPill from "./LangPill";
import { ResumeCard } from "./Resume";
import { lineLabel } from "./QuoteCard";
import { orderProgress, statusTone } from "./Home";
import { Card, Chip, ChipTone, CountUp, Hero, IconTile, LiveDot, Money, PersonCard, Ring, Segments, btn, productLook } from "./ui";

const STEPS = ["stepOrdered", "stepVerified", "stepSetup", "stepLive"];

function when(ts: number | null, lang: Lang): string {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString(lang === "en" ? "en-IN" : `${lang}-IN`, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

function eventText(e: { kind: string; text: string }, lang: Lang, lines: OrderLine[]): string {
  const key = `ev_${e.kind}`;
  const tpl = t(lang, key);
  if (tpl === key) return e.text;
  if (!tpl.includes("{x}")) return tpl;
  const m = e.text.match(/^(?:Engineer started work on )?(.+?)(?: is live)?$/);
  const x = m ? m[1] : "";
  const line = lines.find((l) => l.label === x);
  return tpl.replace("{x}", line ? lineLabel(lang, line.product_id, x) : x);
}

function lineNote(l: OrderLine, lang: Lang): string {
  if (l.state === "scheduled" && l.visit_ts) return `${t(lang, "visitOn")} ${when(l.visit_ts, lang)}`;
  if (l.state === "live" && l.live_ts) return when(l.live_ts, lang);
  return "";
}

const LINE: Record<OrderLine["state"], { tone: ChipTone; icon: LucideIcon }> = {
  queued: { tone: "neutral", icon: Clock },
  scheduled: { tone: "info", icon: CalendarCheck },
  in_progress: { tone: "warning", icon: Loader },
  live: { tone: "success", icon: CheckCircle2 },
};

export default function Tracker({
  order,
  lang,
  setLang,
  onVerify,
  onPlan,
  onOrder,
}: {
  order: Order | null;
  lang: Lang;
  setLang: (l: Lang) => void;
  onVerify: () => void;
  onPlan: () => void;
  onOrder: (o: Order) => void;
}) {
  const head = (title: string, right?: React.ReactNode) => (
    <div className="flex items-start justify-between gap-3 pt-2">
      <div className="min-w-0">
        <h1 className="text-[24px] font-bold leading-tight tracking-tight">{title}</h1>
        {right}
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
              <IconTile icon={Package} tone="teal" size={56} />
              <p className="mt-4 text-[15px] leading-relaxed text-ink-700">{t(lang, "tr_empty")}</p>
              <button onClick={onPlan} className={`${btn.primary} mt-5 w-full`}>
                {t(lang, "qa_advisor")}
                <ArrowRight size={18} />
              </button>
            </Card>
          }
        >
          {head(t(lang, "tr_progress"))}
        </Hero>
        <div className="mt-4 px-4">
          <ResumeCard lang={lang} onOrder={onOrder} />
        </div>
      </div>
    );
  }

  const { done, current } = orderProgress(order);
  const needsKyc = order.status === "awaiting_kyc" || order.status === "kyc_rejected";
  const pct = order.total_count ? Math.round((order.live_count / order.total_count) * 100) : 0;
  const live = order.status === "live";
  const events = order.events.filter((e) => e.kind !== "consent").slice(0, 8);

  return (
    <div className="pb-28">
      <Hero
        overlap={
          <Card className="p-4">
            <div className="flex items-center gap-4">
              <Ring pct={pct} size={88} stroke={8} color={live ? "#0E8A4E" : "#ED1C24"}>
                {live ? (
                  <PartyPopper size={28} className="text-success-600" />
                ) : (
                  <>
                    <span className="text-[22px] font-bold leading-none text-ink-900">
                      <CountUp value={order.live_count} format={(v) => String(Math.round(v))} />
                      <span className="text-[14px] text-ink-400">/{order.total_count}</span>
                    </span>
                    <span className="mt-1 text-[11px] font-semibold text-ink-500">{t(lang, "ln_live")}</span>
                  </>
                )}
              </Ring>
              <div className="min-w-0 flex-1">
                <Chip tone={statusTone(order.status)}>{t(lang, `st_${order.status}`)}</Chip>
                <div className="mt-2 text-[14px] font-medium leading-snug text-ink-700">
                  {t(lang, "liveCount").replace("{a}", String(order.live_count)).replace("{b}", String(order.total_count))}
                </div>
              </div>
            </div>
            <div className="mt-4">
              <Segments labels={STEPS.map((k) => t(lang, k))} done={done} current={current} />
            </div>
            {needsKyc && (
              <button onClick={onVerify} className={`${btn.primary} mt-4 w-full`}>
                {t(lang, "verifyBtn")}
                <ArrowRight size={18} />
              </button>
            )}
          </Card>
        }
      >
        {head(
          `${t(lang, "tr_title")} ${order.order_id}`,
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px] text-white/85">
            <span>{order.bundle_name}</span>
            <span>·</span>
            <span>
              <Money value={order.tax.monthly_incl_gst} />
              {t(lang, "perMonth")}
            </span>
            {!live && (
              <span className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2 py-0.5 text-[12px] font-semibold text-white">
                <LiveDot color="bg-white" />
                {t(lang, "updatedLive")}
              </span>
            )}
          </div>,
        )}
      </Hero>

      <div className="mt-4 space-y-4 px-4">
        <section>
          <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink-900">{t(lang, "tr_services")}</h2>
          <Card className="stagger overflow-hidden">
            {order.lines.map((l, i) => {
              const look = productLook(undefined, `${l.label} ${l.spec}`);
              const st = LINE[l.state];
              const note = lineNote(l, lang);
              return (
                <div key={l.product_id} className={`flex items-start gap-3 px-4 py-4 ${i ? "border-t border-line-100" : ""}`}>
                  <IconTile icon={look.icon} tone={look.tone} size={44} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[15px] font-semibold leading-snug text-ink-900">
                      {lineLabel(lang, l.product_id, l.label)}
                      {l.qty > 1 && <span className="font-medium text-ink-500"> ×{l.qty}</span>}
                    </div>
                    <div className="text-[13px] text-ink-500">{l.spec}</div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Chip tone={st.tone} icon={st.icon}>
                        {t(lang, `ln_${l.state}`)}
                      </Chip>
                      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-ink-500">
                        {l.kind === "field" ? <Wrench size={12} /> : <Zap size={12} />}
                        {l.kind === "field" ? t(lang, "visitNeeded") : t(lang, "remoteOk")}
                      </span>
                    </div>
                    {note && <div className="mt-1.5 text-[13px] font-medium text-ink-700">{note}</div>}
                  </div>
                </div>
              );
            })}
          </Card>
        </section>

        {order.engineer && (
          <Card className="enter p-4">
            <PersonCard label={t(lang, "engineerCard")} name={order.engineer.name} sub={order.engineer.city} phone={order.engineer.phone} callLabel={t(lang, "callEngineer")} />
          </Card>
        )}
        {order.assist && (
          <Card className="enter p-4">
            <PersonCard label={t(lang, "partnerCard")} name={order.assist.name} sub={order.assist.city} phone={order.assist.phone} callLabel={t(lang, "callEngineer")} />
          </Card>
        )}

        {events.length > 0 && (
          <Card className="p-4">
            <h2 className="mb-3 text-[15px] font-semibold text-ink-900">{t(lang, "activity")}</h2>
            <ol className="relative">
              {events.map((e, i) => (
                <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < events.length - 1 && <span className="absolute left-[5px] top-4 h-full w-0.5 bg-line-100" aria-hidden="true" />}
                  <span className={`relative mt-1.5 h-3 w-3 shrink-0 rounded-full ring-4 ring-white ${i === 0 ? "bg-brand-500" : "bg-line-200"}`} />
                  <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
                    <span className={`text-[14px] leading-snug ${i === 0 ? "font-semibold text-ink-900" : "text-ink-700"}`}>{eventText(e, lang, order.lines)}</span>
                    <span className="shrink-0 text-[12px] text-ink-400">{when(e.ts, lang)}</span>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        )}

        <div className="flex items-start gap-3 rounded-card bg-success-50 p-4 text-[14px] leading-snug text-success-600">
          <MessageCircle size={20} className="mt-0.5 shrink-0" />
          {t(lang, "whatsapp")}
        </div>
      </div>
    </div>
  );
}
