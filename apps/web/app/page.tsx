"use client";
import { useState } from "react";
import { Profile, Quote } from "@/lib/api";
import { Lang, LANGS, t } from "@/lib/i18n";
import AdvisorChat from "@/components/AdvisorChat";
import KycPanel from "@/components/KycPanel";
import Tracker from "@/components/Tracker";

type Tab = "advisor" | "kyc" | "tracker";

export default function Page() {
  const [tab, setTab] = useState<Tab>("advisor");
  const [lang, setLang] = useState<Lang>("en");
  const [, setProfile] = useState<Profile | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);

  const tabs: { id: Tab; label: string; icon: JSX.Element }[] = [
    { id: "advisor", label: t(lang, "tab_advisor"), icon: <ChatIcon /> },
    { id: "kyc", label: t(lang, "tab_kyc"), icon: <ShieldIcon /> },
    { id: "tracker", label: t(lang, "tab_tracker"), icon: <BoxIcon /> },
  ];

  return (
    <main className="phone">
      <header className="bg-gradient-to-br from-[#ED1C24] to-[#B3121A] px-4 pb-4 pt-5 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AccelMark />
            <div className="flex items-baseline gap-1.5">
              <span className="text-xl font-extrabold tracking-tight">{t(lang, "brand")}</span>
              <span className="rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase">
                {t(lang, "brandSub")}
              </span>
            </div>
          </div>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value as Lang)}
            className="rounded-full bg-white/15 px-2.5 py-1 text-xs font-medium text-white outline-none"
          >
            {LANGS.map((l) => (
              <option key={l.code} value={l.code} className="text-slate-800">
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <h1 className="mt-2 text-lg font-bold">{t(lang, "appName")}</h1>
        <p className="text-xs text-red-100">{t(lang, "tagline")}</p>
      </header>

      <div className="flex-1 overflow-hidden px-3 py-3">
        <div className={tab === "advisor" ? "h-full" : "hidden"}>
          <AdvisorChat
            key={`advisor-${lang}`}
            lang={lang}
            quote={quote}
            setQuote={setQuote}
            setProfile={setProfile}
            onProceed={() => setTab("kyc")}
          />
        </div>
        <div className={tab === "kyc" ? "h-full overflow-y-auto" : "hidden"}>
          <KycPanel lang={lang} />
        </div>
        <div className={tab === "tracker" ? "h-full overflow-y-auto" : "hidden"}>
          <Tracker quote={quote} lang={lang} />
        </div>
      </div>

      <nav className="grid grid-cols-3 border-t border-slate-200 bg-white">
        {tabs.map((tb) => (
          <button
            key={tb.id}
            onClick={() => setTab(tb.id)}
            className={`flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium ${
              tab === tb.id ? "text-[#ED1C24]" : "text-slate-400"
            }`}
          >
            {tb.icon}
            {tb.label}
          </button>
        ))}
      </nav>
    </main>
  );
}

function AccelMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="8" fill="#ffffff" />
      <path d="M8.5 24 L16 8 L23.5 24" fill="none" stroke="#ED1C24" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 18.5 H20" stroke="#ED1C24" strokeWidth="3.2" strokeLinecap="round" />
      <circle cx="24.5" cy="8.5" r="1.8" fill="#ED1C24" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
function ShieldIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function BoxIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}
