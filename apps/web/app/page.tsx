"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { House, MessageSquareText, Package, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api, Order, Profile, Quote, orderKey, subscribe } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";
import AdvisorChat, { ProceedMeta } from "@/components/AdvisorChat";
import KycPanel from "@/components/KycPanel";
import Tracker from "@/components/Tracker";
import Home, { Tab } from "@/components/Home";
import { rememberCode } from "@/components/Resume";

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function safeSet(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

export default function Page() {
  const [tab, setTab] = useState<Tab>("home");
  const [lang, setLang] = useState<Lang>("en");
  const [profile, setProfileState] = useState<Profile | null>(null);
  const [quote, setQuoteState] = useState<Quote | null>(null);
  const setQuote = useCallback((q: Quote | null) => {
    setQuoteState(q);
    if (!q) safeSet("udyam_quote", null);
  }, []);
  const setProfile = useCallback((p: Profile | null) => setProfileState(p), []);

  useEffect(() => {
    if (quote && profile) safeSet("udyam_quote", JSON.stringify({ quote, profile }));
  }, [quote, profile]);
  const [order, setOrderState] = useState<Order | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [startMode, setStartMode] = useState<"text" | "voice" | null>(null);
  const prevStatus = useRef<string | null>(null);

  const setOrder = useCallback((o: Order | null) => {
    setOrderState(o);
    safeSet("udyam_order", o ? o.order_id : null);
  }, []);

  const newSession = () => {
    const sid = "web-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    safeSet("udyam_sid", sid);
    return sid;
  };

  const startFresh = useCallback(() => {
    safeSet("udyam_order", null);
    safeSet("udyam_quote", null);
    setOrderState(null);
    setQuote(null);
    setProfile(null);
    prevStatus.current = null;
    setSessionId(newSession());
    setTab("home");
  }, []);

  useEffect(() => {
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.get("new") === "1") {
        safeSet("udyam_order", null);
        safeSet("udyam_sid", null);
        safeSet("udyam_quote", null);
        url.searchParams.delete("new");
        window.history.replaceState(null, "", url.pathname + url.search);
      }
    } catch {
      /* ignore */
    }
    let sid = safeGet("udyam_sid");
    if (!sid) {
      sid = "web-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
      safeSet("udyam_sid", sid);
    }
    setSessionId(sid);
    const resumeId = new URL(window.location.href).searchParams.get("resume");
    if (resumeId) {
      try {
        window.sessionStorage.setItem("udyam_resume_ref", resumeId);
      } catch {
        /* storage unavailable */
      }
      setTab("kyc");
      window.history.replaceState(null, "", window.location.pathname);
    }
    try {
      const q = JSON.parse(safeGet("udyam_quote") ?? "null");
      if (q?.quote && q?.profile) {
        setQuoteState(q.quote);
        setProfileState(q.profile);
      }
    } catch {
      safeSet("udyam_quote", null);
    }
    const saved = safeGet("udyam_order");
    if (saved) {
      api
        .order(saved)
        .then((o) => setOrderState(o))
        .catch(() => safeSet("udyam_order", null));
    }
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);

  const orderId = order?.order_id;
  useEffect(() => {
    if (!orderId) return;
    const refresh = () => api.order(orderId).then(setOrderState).catch(() => {});
    const stop = subscribe(`/api/v1/orders/${orderId}/stream?k=${encodeURIComponent(orderKey(orderId))}`, refresh);
    const onVis = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [orderId]);

  useEffect(() => {
    const s = order?.status ?? null;
    const was = prevStatus.current;
    prevStatus.current = s;
    const passed = s === "approved" || s === "in_progress" || s === "live";
    const wasPassed = was === "approved" || was === "in_progress" || was === "live";
    if (passed && !wasPassed && was !== null) {
      setToast(t(lang, "approvedMsg"));
      const h = setTimeout(() => {
        setTab("tracker");
        setToast("");
      }, 2200);
      return () => clearTimeout(h);
    }
  }, [order?.status, lang]);

  async function startOrder(q: Quote, profile: Profile, meta: ProceedMeta) {
    setCreating(true);
    setError("");
    try {
      const o = await api.createOrder({
        profile,
        items: q.lines.map((l) => ({ product_id: l.product_id, qty: l.qty })),
        business: meta.business,
        lead_id: meta.leadId,
        session_id: sessionId,
        lang,
      });
      if (o.resume_code) rememberCode(o.order_id, o.resume_code);
      setOrder(o);
      setTab("kyc");
    } catch (e) {
      const err = e as { status?: number; message?: string };
      if (err.status === 422 && /english/i.test(err.message ?? "")) setError(t(lang, "nameEnglish"));
      else if (err.status === 409) setError(err.message ?? t(lang, "orderFail"));
      else setError(t(lang, "orderFail"));
      setTimeout(() => setError(""), 4000);
    } finally {
      setCreating(false);
    }
  }

  function resumed(o: Order) {
    setOrder(o);
    prevStatus.current = o.status;
    const needs = o.status === "awaiting_kyc" || o.status === "kyc_rejected";
    setTab(needs ? "kyc" : "tracker");
  }

  function resumedOrSet(o: Order) {
    if (!order) resumed(o);
    else setOrder(o);
  }

  function startAdvisor(mode: "text" | "voice") {
    setStartMode(mode);
    setTab("advisor");
  }

  const needsKyc = order?.status === "awaiting_kyc" || order?.status === "kyc_rejected";
  const tabs: { id: Tab; label: string; icon: LucideIcon; dot?: boolean }[] = [
    { id: "home", label: t(lang, "tab_home"), icon: House },
    { id: "advisor", label: t(lang, "step_plan"), icon: MessageSquareText },
    { id: "kyc", label: t(lang, "step_verify"), icon: ShieldCheck, dot: needsKyc },
    { id: "tracker", label: t(lang, "step_track"), icon: Package },
  ];
  const active = tabs.findIndex((x) => x.id === tab);

  return (
    <main className="phone">
      {(toast || creating || error) && (
        <div className="pointer-events-none absolute inset-x-3 top-3 z-40">
          <div
            className={`drop-in rounded-2xl px-4 py-3 text-center text-[14px] font-semibold text-white shadow-float ${
              error ? "bg-danger-600" : toast ? "bg-success-600" : "bg-ink-900"
            }`}
          >
            {error || toast || t(lang, "creating")}
          </div>
        </div>
      )}

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={tab === "home" ? "scroll-area h-full overflow-y-auto" : "hidden"}>
          <Home lang={lang} setLang={setLang} order={order} quote={quote} onStart={startAdvisor} go={setTab} onNew={startFresh} />
        </div>
        <div className={tab === "advisor" ? "h-full" : "hidden"}>
          {sessionId && (
            <AdvisorChat
              key={`advisor-${lang}-${sessionId}`}
              lang={lang}
              setLang={setLang}
              sessionId={sessionId}
              quote={quote}
              setQuote={setQuote}
              setProfile={setProfile}
              savedProfile={profile}
              onProceed={startOrder}
              startMode={startMode}
              onStartHandled={() => setStartMode(null)}
              onHome={() => setTab("home")}
              hasOrder={!!order}
              goVerify={() => setTab("kyc")}
            />
          )}
        </div>
        <div className={tab === "kyc" ? "scroll-area h-full overflow-y-auto" : "hidden"}>
          <KycPanel key={order?.order_id ?? "none"} lang={lang} setLang={setLang} order={order} onOrder={resumedOrSet} onTrack={() => setTab("tracker")} onPlan={() => setTab("advisor")} />
        </div>
        <div className={tab === "tracker" ? "scroll-area h-full overflow-y-auto" : "hidden"}>
          <Tracker order={order} lang={lang} setLang={setLang} onVerify={() => setTab("kyc")} onPlan={() => setTab("advisor")} onOrder={resumed} />
        </div>
      </div>

      <nav className="absolute inset-x-3 bottom-3 z-30 rounded-[24px] bg-white p-1.5 shadow-float pb-[max(0.375rem,env(safe-area-inset-bottom))]">
        <div className="relative grid grid-cols-4">
          <span
            aria-hidden="true"
            className="absolute inset-y-0 rounded-[18px] bg-brand-600 transition-[left] duration-300 ease-out"
            style={{ left: `calc(${active * 25}% + 2px)`, width: "calc(25% - 4px)" }}
          />
          {tabs.map((tb) => {
            const on = tab === tb.id;
            const Icon = tb.icon;
            return (
              <button
                key={tb.id}
                onClick={() => setTab(tb.id)}
                aria-current={on ? "page" : undefined}
                className={`press relative z-10 flex h-14 flex-col items-center justify-center gap-0.5 text-[12px] font-semibold transition-colors ${
                  on ? "text-white" : "text-ink-500"
                }`}
              >
                <Icon size={22} strokeWidth={on ? 2.2 : 1.9} />
                {tb.label}
                {tb.dot && !on && <span className="absolute right-[30%] top-2 h-2.5 w-2.5 rounded-full border-2 border-white bg-brand-500" />}
              </button>
            );
          })}
        </div>
      </nav>
    </main>
  );
}
