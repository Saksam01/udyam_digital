"use client";
import { Quote } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";

export default function Tracker({ quote, lang }: { quote: Quote | null; lang: Lang }) {
  if (!quote) {
    return (
      <div className="rounded-2xl bg-white p-6 text-center text-sm text-slate-500 shadow-sm ring-1 ring-slate-200">
        {t(lang, "tracker_empty")}
      </div>
    );
  }

  const steps = [...quote.lines]
    .sort((a, b) => a.install_days - b.install_days)
    .map((l) => ({ name: l.name, day: l.install_days, live: l.install_days <= 1 }));

  return (
    <div className="space-y-4 overflow-y-auto pb-2">
      <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-slate-800">
            {t(lang, "order")} {quote.quote_id}
          </h2>
          <span className="text-xs text-slate-400">
            {t(lang, "liveIn")} ~{quote.activation_eta_days} {t(lang, "days")}
          </span>
        </div>

        <ol className="mt-4 space-y-4">
          {steps.map((s, i) => (
            <li key={i} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className={`h-3 w-3 rounded-full ${s.live ? "bg-emerald-500" : "bg-slate-300"}`} />
                {i < steps.length - 1 && <span className="mt-1 h-8 w-px bg-slate-200" />}
              </div>
              <div className="-mt-0.5">
                <div className="text-sm font-medium text-slate-800">{s.name}</div>
                <div className="text-xs text-slate-400">
                  {s.live ? t(lang, "goesFirst") : `${t(lang, "scheduled")} · ~${t(lang, "day")} ${s.day}`}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="rounded-xl bg-red-50 p-3 text-xs text-[#B3121A]">{t(lang, "whatsapp")}</div>
    </div>
  );
}
