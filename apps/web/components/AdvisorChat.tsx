"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Keyboard,
  Lock,
  MapPin,
  Mic,
  Minus,
  Plus,
  Search,
  SendHorizontal,
  Headset,
  X,
} from "lucide-react";
import { api, Profile, Quote, Segment, GstinStatus, SuitableResult, Understood } from "@/lib/api";
import { FLOW, Lang, label, question, matchOption, parseNumber, t, localeFor } from "@/lib/i18n";
import { CITIES, cityLabel, matchCity } from "@/lib/i18n/more";
import { sttSupported, listenOnce, speak, stopSpeaking } from "@/lib/speech";
import { sarvamOn, sarvamSpeak, sarvamListen, sarvamWarm, stopSarvam, releaseMic, cancelListen, ListenResult } from "@/lib/sarvam";
import QuoteCard from "./QuoteCard";
import LangPill from "./LangPill";
import { IconTile, btn } from "./ui";

type Msg = { id: number; role: "bot" | "user"; text: string };
type Mode = "text" | "voice" | null;

export interface ProceedMeta {
  business?: string;
  leadId?: string;
}

export default function AdvisorChat({
  lang,
  setLang,
  sessionId,
  quote,
  setQuote,
  setProfile,
  onProceed,
  startMode,
  onStartHandled,
  onHome,
  savedProfile,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  sessionId: string;
  quote: Quote | null;
  setQuote: (q: Quote | null) => void;
  setProfile: (p: Profile) => void;
  onProceed: (quote: Quote, profile: Profile, meta: ProceedMeta) => void;
  startMode: "text" | "voice" | null;
  onStartHandled: () => void;
  onHome: () => void;
  hasOrder?: boolean;
  goVerify?: () => void;
  savedProfile?: Profile | null;
}) {
  const locale = localeFor(lang);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [step, setStep] = useState(0);
  const [view, setView] = useState<"chat" | "plan">(quote ? "plan" : "chat");
  const [sheet, setSheet] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [data, setData] = useState<Record<string, string | number | string[]>>({});
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const [mode, setMode] = useState<Mode>(null);
  const [mounted, setMounted] = useState(false);
  const [picks, setPicks] = useState<string[]>([]);
  const [numVal, setNumVal] = useState(1);
  const [citySheet, setCitySheet] = useState(false);
  const [catalog, setCatalog] = useState<SuitableResult | null>(null);
  const [qProfile, setQProfile] = useState<Profile | null>(null);
  const leadRef = useRef<string | undefined>(undefined);
  const answeredRef = useRef<Set<string>>(new Set());

  const idRef = useRef(0);
  const initRef = useRef(false);
  const stepRef = useRef(0);
  const modeRef = useRef<Mode>(null);
  const sarvamRef = useRef(false);
  const dataRef = useRef<Record<string, string | number | string[]>>({});
  const listRef = useRef<HTMLDivElement>(null);
  const listenId = useRef(0);

  const add = (role: "bot" | "user", text: string) =>
    setMsgs((m) => [...m, { id: idRef.current++, role, text }]);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    add("bot", t(lang, "welcome"));
    add("bot", t(lang, "chooseMode"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setMounted(true);
    sarvamOn().then((on) => {
      sarvamRef.current = on;
      warmVoice();
    });
  }, []);
  useEffect(
    () => () => {
      stopSpeaking();
      stopSarvam();
      releaseMic();
    },
    [],
  );

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [msgs, quote, listening, thinking, view]);

  useEffect(() => {
    if (!startMode || !mounted) return;
    if (modeRef.current === null && !done) chooseMode(startMode);
    else if (quote) setView("plan");
    onStartHandled();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startMode, mounted]);

  function speakQ(text: string, onEnd?: () => void) {
    if (!sarvamRef.current) {
      speak(text, locale, onEnd);
      return;
    }
    sarvamSpeak(text, locale, onEnd).then((ok) => {
      if (!ok) {
        sarvamRef.current = false;
        speak(text, locale, onEnd);
      }
    });
  }

  function canListen() {
    return sarvamRef.current || sttSupported();
  }

  async function listen(): Promise<ListenResult> {
    if (sarvamRef.current) return sarvamListen(locale);
    try {
      const tr = await listenOnce(locale);
      return { transcript: tr.trim(), heardSpeech: !!tr.trim() };
    } catch (e) {
      if (e instanceof Error && e.message === "no-speech") return { transcript: "", heardSpeech: false };
      throw e;
    }
  }

  function fallbackToText(msgKey: string) {
    if (modeRef.current !== "text") {
      modeRef.current = "text";
      setMode("text");
    }
    add("bot", t(lang, msgKey));
  }

  function startListen() {
    if (!canListen()) return;
    const id = ++listenId.current;
    setListening(true);
    listen()
      .then((res) => {
        if (id !== listenId.current) return;
        setListening(false);
        if (res.transcript) {
          handleText(res.transcript);
        } else if (!res.heardSpeech) {
          if (modeRef.current !== "text") {
            modeRef.current = "text";
            setMode("text");
          }
        } else {
          fallbackToText("notUnderstood");
        }
      })
      .catch((e: unknown) => {
        if (id !== listenId.current) return;
        setListening(false);
        console.warn("voice error:", e);
        fallbackToText("voiceUnavailable");
      });
  }

  function chooseMode(m: Exclude<Mode, null>) {
    modeRef.current = m;
    setMode(m);
    add("user", m === "voice" ? t(lang, "opt_speak") : t(lang, "opt_type"));
    add("bot", t(lang, "oneLine"));
    askStep(0);
  }

  function askStep(from: number) {
    let i = from;
    while (i < FLOW.length && answeredRef.current.has(FLOW[i].field)) i++;
    stepRef.current = i;
    setStep(i);
    if (i >= FLOW.length) {
      recommend();
      return;
    }
    const st = FLOW[i];
    if (st.kind === "multi") setPicks([]);
    if (st.kind === "number") setNumVal(st.def ?? 1);
    const q = question(st, lang);
    add("bot", q);
    if (st.kind === "select") {
      if (modeRef.current === "voice") speakQ(q, () => startListen());
      return;
    }
    if (st.kind === "name") return;
    if (modeRef.current === "voice") {
      if (FLOW[i].kind === "multi") speakQ(q);
      else speakQ(q, () => startListen());
    }
  }

  function warmVoice() {
    if (!sarvamRef.current) return;
    const texts = FLOW.filter((s) => s.kind !== "select" && s.kind !== "name").map((s) => question(s, lang));
    sarvamWarm([...texts, t(lang, "recommending"), t(lang, "notUnderstood")], locale);
  }

  function record(field: string, value: string | number | string[]) {
    answeredRef.current.add(field);
    dataRef.current = { ...dataRef.current, [field]: value };
    setData(dataRef.current);
  }

  function answer(display: string, value: string | number) {
    listenId.current++;
    cancelListen();
    setListening(false);
    const i = stepRef.current;
    add("user", display);
    record(FLOW[i].field, value);
    setText("");
    setTimeout(() => askStep(i + 1), 150);
  }

  function chooseSelect(value: string) {
    const i = stepRef.current;
    const opt = FLOW[i].options!.find((o) => o.value === value);
    if (!opt) return;
    record("business_type", opt.value);
    answer(label(opt, lang), opt.seg ?? value);
  }

  function submitNumber(n: number) {
    const st = FLOW[stepRef.current];
    const v = Math.max(st.min ?? 1, Math.min(st.max ?? 999, Math.round(n)));
    answer(String(v), v);
  }

  function chooseCity(en: string) {
    setCitySheet(false);
    answer(cityLabel(en, lang), en);
  }

  function togglePick(v: string) {
    setPicks((p) => (p.includes(v) ? p.filter((x) => x !== v) : [...p, v]));
  }

  function submitMulti() {
    const i = stepRef.current;
    const step = FLOW[i];
    const display = picks.length
      ? picks.map((v) => label(step.options!.find((o) => o.value === v)!, lang)).join(", ")
      : "-";
    add("user", display);
    record(step.field, picks);
    setPicks([]);
    setText("");
    setTimeout(() => askStep(i + 1), 150);
  }

  function buildProfile(): Profile {
    return dataToProfile(dataRef.current);
  }

  async function showQuote(r: Awaited<ReturnType<typeof api.advisor>>, prof: Profile) {
    add("bot", r.text);
    if (modeRef.current === "voice") speakQ(r.text);
    leadRef.current = r.lead_id;
    setQProfile(prof);
    setProfile(prof);
    setQuote(r.quote_card);
    if (r.quote_card) setTimeout(() => setView("plan"), 900);
    try {
      setCatalog(await api.suitable(prof, [], prof.need_tags ?? []));
    } catch {
      /* product detail is optional */
    }
  }

  async function recommend() {
    add("bot", t(lang, "recommending"));
    setThinking(true);
    const prof = buildProfile();
    try {
      const business = String(dataRef.current.business ?? "") || undefined;
      const r = await api.advisor(sessionId, prof, "", lang, business);
      setThinking(false);
      await showQuote(r, prof);
    } catch {
      setThinking(false);
      add("bot", t(lang, "netErr"));
    }
    setDone(true);
  }

  async function absorb(input: string): Promise<boolean> {
    setThinking(true);
    let u: Understood = {};
    try {
      u = await api.understand(sessionId, input, lang);
    } catch {
      u = {};
    }
    setThinking(false);
    if (!u.city) {
      const c = matchCity(input);
      if (c) u.city = c;
    }
    const parts: string[] = [];
    const bizOpt = FLOW[0].options?.find((o) => o.value === u.business_type);
    if (bizOpt) {
      record("business_type", bizOpt.value);
      record("segment", bizOpt.seg ?? u.segment ?? "micro");
      parts.push(label(bizOpt, lang));
    }
    if (u.employees) {
      record("employees", u.employees);
      parts.push(t(lang, "staffN").replace("{n}", String(u.employees)));
    }
    if (u.num_sites) {
      record("num_sites", u.num_sites);
      parts.push(u.num_sites === 1 ? t(lang, "sitesOne") : t(lang, "sitesN").replace("{n}", String(u.num_sites)));
    }
    if (u.city) {
      record("city", u.city);
      parts.push(cityLabel(u.city, lang));
    }
    const needStep = FLOW.find((f) => f.field === "need_tags");
    const groups = (u.need_groups ?? []).filter((g) => needStep?.options?.some((o) => o.value === g));
    if (groups.length) {
      record("need_tags", [...groups, ...(u.need_tags ?? [])]);
      parts.push(groups.map((g) => label(needStep!.options!.find((o) => o.value === g)!, lang)).join(", "));
    }
    const gstStep = FLOW.find((f) => f.field === "gstin_status");
    const gstOpt = gstStep?.options?.find((o) => o.value === u.gstin_status);
    if (gstOpt) {
      record("gstin_status", gstOpt.value);
      parts.push(`GST: ${label(gstOpt, lang)}`);
    }
    if (!parts.length) return false;
    listenId.current++;
    cancelListen();
    setListening(false);
    add("user", input);
    add("bot", t(lang, "understood").replace("{x}", parts.join(" · ")));
    setText("");
    setTimeout(() => askStep(0), 150);
    return true;
  }

  async function handleText(raw: string) {
    const input = raw.trim();
    if (!input) return;
    const s = FLOW[stepRef.current];
    if (!s) return;
    if (s.kind !== "name" && input.split(/\s+/).length >= 4 && (await absorb(input))) return;
    if (s.kind === "multi") return;
    if (s.kind === "text") return answer(input, input);
    if (s.kind === "name") {
      const clean = input.replace(/\s+/g, " ").trim();
      if (/[^\x00-\x7F]/.test(clean) || !/[A-Za-z]/.test(clean)) {
        add("user", input);
        add("bot", t(lang, "nameEnglish"));
        return;
      }
      return answer(clean, clean);
    }
    if (s.kind === "city") {
      const c = matchCity(input);
      if (c) return answer(cityLabel(c, lang), c);
      if (!/[^\x00-\x7F]/.test(input) && /[A-Za-z]{3,}/.test(input)) {
        const typed = input.replace(/\s+/g, " ").trim().replace(/\b\w/g, (m) => m.toUpperCase());
        return answer(typed, typed);
      }
      add("user", input);
      add("bot", t(lang, "cityEnglish"));
      setCitySheet(true);
      if (modeRef.current === "voice") {
        modeRef.current = "text";
        setMode("text");
      }
      return;
    }
    if (s.kind === "number") {
      const n = parseNumber(input);
      if (n != null) return submitNumber(n);
    }
    const v = matchOption(s, input, lang);
    if (v) {
      const opt = s.options!.find((o) => o.value === v)!;
      if (s.kind === "select") record("business_type", opt.value);
      return answer(label(opt, lang), s.kind === "select" ? opt.seg ?? v : opt.num ?? v);
    }
    if (s.kind === "select" && (await absorb(input))) return;
    add("user", input);
    add("bot", t(lang, "notUnderstood"));
    if (modeRef.current === "voice") {
      modeRef.current = "text";
      setMode("text");
    }
  }

  const s = FLOW[stepRef.current];
  const isMulti = s?.kind === "multi";
  const isSelect = s?.kind === "select";
  const isName = s?.kind === "name";
  const isCity = s?.kind === "city";
  const isNumber = s?.kind === "number";
  const total = FLOW.length;
  const profile = qProfile ?? savedProfile ?? dataToProfile(data);

  if (view === "plan" && quote) {
    return (
      <div className="scroll-area h-full overflow-y-auto">
        <QuoteCard
          quote={quote}
          catalog={catalog}
          profile={profile}
          onQuote={setQuote}
          onBack={() => setView("chat")}
          setLang={setLang}
          onProceed={() =>
            onProceed(quote, profile, {
              business: String(dataRef.current.business ?? "") || undefined,
              leadId: leadRef.current,
            })
          }
          lang={lang}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col pb-[84px]">
      <header className="hero-band shrink-0 rounded-b-hero px-4 pb-4 pt-4 text-white">
        <div className="flex items-center justify-between">
          <button onClick={onHome} aria-label={t(lang, "backHome")} className="press flex h-10 w-10 items-center justify-center rounded-full bg-white/15">
            <ArrowLeft size={20} />
          </button>
          <LangPill lang={lang} setLang={setLang} />
        </div>
        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-bold leading-tight tracking-tight">{t(lang, "advisor_title")}</h1>
            <p className="text-[13px] font-medium text-white/80">{t(lang, "advisor_sub")}</p>
          </div>
          {quote && (
            <button onClick={() => setView("plan")} className="press flex h-9 items-center gap-1 rounded-full bg-white px-3 text-[13px] font-semibold text-brand-600">
              {t(lang, "seePlan")}
              <ChevronRight size={16} />
            </button>
          )}
        </div>

      </header>

      <div ref={listRef} className="scroll-area flex-1 space-y-3 overflow-y-auto px-4 pb-3 pt-4">
        {msgs.map((m) =>
          m.role === "bot" ? (
            <div key={m.id} className="rise flex items-start gap-2.5">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                <Headset size={15} strokeWidth={2.2} />
              </span>
              <div className="max-w-[85%] rounded-2xl rounded-tl-md bg-white px-4 py-3 text-[15px] leading-relaxed text-ink-900 shadow-soft">{m.text}</div>
            </div>
          ) : (
            <div key={m.id} className="rise flex justify-end">
              <div className="max-w-[80%] rounded-2xl rounded-br-md bg-ink-900 px-4 py-2.5 text-[15px] font-medium leading-relaxed text-white">{m.text}</div>
            </div>
          ),
        )}

        {thinking && (
          <div className="rise flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Headset size={15} strokeWidth={2.2} />
            </span>
            <div className="typing rounded-2xl rounded-tl-md bg-white px-4 py-3.5 shadow-soft">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        {mode === null && !done && (
          <div className="stagger space-y-3 pt-2">
            <p className="px-1 text-[15px] font-semibold text-ink-900">{t(lang, "howAnswer")}</p>
            <ModeCard
              disabled={!mounted}
              onClick={() => chooseMode("voice")}
              icon={<IconTile icon={Mic} tone="red" size={48} />}
              title={t(lang, "opt_speak")}
              sub={t(lang, "mode_speak_sub")}
            />
            <ModeCard
              disabled={!mounted}
              onClick={() => chooseMode("text")}
              icon={<IconTile icon={Keyboard} tone="slate" size={48} />}
              title={t(lang, "opt_type")}
              sub={t(lang, "mode_type_sub")}
            />
            <p className="flex items-center gap-1.5 px-1 text-[12px] text-ink-500">
              <Lock size={13} />
              {t(lang, "privacyNote")}
            </p>
          </div>
        )}

        {done && quote && (
          <div className="rise pt-1">
            <button onClick={() => setView("plan")} className={`${btn.primary} w-full`}>
              {t(lang, "seePlan")}
              <ArrowRight size={18} />
            </button>
          </div>
        )}
      </div>

      {!done && mode !== null && !thinking && step < total && (
        <div className="shrink-0 rounded-t-[24px] bg-white px-4 pb-3 pt-4 shadow-bar">
          {listening ? (
            <div className="fade-in flex flex-col items-center gap-3 py-2">
              <div className="flex items-center gap-4">
                <div className="eq flex h-8 items-center gap-1" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="breathe flex h-16 w-16 items-center justify-center rounded-full bg-brand-600 text-white shadow-float">
                  <Mic size={28} />
                </span>
                <div className="eq flex h-8 items-center gap-1" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
              <div className="text-[16px] font-semibold text-ink-900">{t(lang, "speakPrompt")}</div>
              <button
                onClick={() => {
                  listenId.current++;
                  cancelListen();
                  stopSarvam();
                  setListening(false);
                  modeRef.current = "text";
                  setMode("text");
                }}
                className="flex items-center gap-1.5 text-[14px] font-semibold text-brand-600"
              >
                <Keyboard size={16} />
                {t(lang, "typeInstead")}
              </button>
            </div>
          ) : (
            <>
              {isSelect && s?.options ? (
                <button onClick={() => setSheet(true)} className="press mb-3 flex h-12 w-full items-center justify-between rounded-btn bg-surface-50 px-4 text-[15px] font-semibold text-ink-900 ring-1 ring-line-200">
                  <span className="flex items-center gap-2">
                    <Search size={18} className="text-ink-500" />
                    {t(lang, "selectBiz")}
                  </span>
                  <ChevronDown size={18} className="text-ink-500" />
                </button>
              ) : isMulti && s?.options ? (
                <div className="mb-3">
                  <div className="grid grid-cols-2 gap-2">
                    {s.options.map((o) => {
                      const on = picks.includes(o.value);
                      return (
                        <button
                          key={o.value}
                          onClick={() => togglePick(o.value)}
                          aria-pressed={on}
                          className={`press flex min-h-[48px] items-center gap-2 rounded-btn px-3 text-left text-[14px] font-semibold ring-1 transition-colors ${
                            on ? "bg-brand-50 text-brand-700 ring-brand-500" : "bg-white text-ink-900 ring-line-200"
                          }`}
                        >
                          <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md ${on ? "bg-brand-600 text-white" : "ring-1 ring-line-200"}`}>
                            {on && <Check size={14} strokeWidth={3} />}
                          </span>
                          <span className="leading-tight">{label(o, lang)}</span>
                        </button>
                      );
                    })}
                  </div>
                  <button onClick={submitMulti} className={`${btn.dark} mt-3 w-full`}>
                    {t(lang, "continueBtn")}
                    {picks.length > 0 && <span className="rounded-full bg-white/20 px-2 py-0.5 text-[12px]">{picks.length}</span>}
                  </button>
                </div>
              ) : isNumber ? (
                <div className="mb-3 flex items-center gap-3">
                  <div className="flex h-14 flex-1 items-center justify-between rounded-btn bg-surface-50 px-2 ring-1 ring-line-200">
                    <button
                      onClick={() => setNumVal((v) => Math.max(s.min ?? 1, v - 1))}
                      disabled={numVal <= (s.min ?? 1)}
                      aria-label="-1"
                      className="press flex h-10 w-10 items-center justify-center rounded-full bg-white text-ink-900 shadow-soft disabled:opacity-40"
                    >
                      <Minus size={18} />
                    </button>
                    <input
                      inputMode="numeric"
                      value={String(numVal)}
                      onChange={(e) => {
                        const n = parseInt(e.target.value.replace(/\D/g, "") || "0", 10);
                        setNumVal(Math.min(s.max ?? 999, n));
                      }}
                      onKeyDown={(e) => e.key === "Enter" && submitNumber(numVal || 1)}
                      aria-label={t(lang, "qtyLabel")}
                      className="w-20 bg-transparent text-center text-[24px] font-bold tabular-nums text-ink-900 outline-none"
                    />
                    <button
                      onClick={() => setNumVal((v) => Math.min(s.max ?? 999, v + 1))}
                      aria-label="+1"
                      className="press flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-soft"
                    >
                      <Plus size={18} />
                    </button>
                  </div>
                  <button onClick={() => submitNumber(numVal || 1)} className={`${btn.dark} h-14 shrink-0 px-5`}>
                    {t(lang, "confirmNum")}
                  </button>
                </div>
              ) : isCity ? (
                <button onClick={() => setCitySheet(true)} className="press mb-3 flex h-12 w-full items-center justify-between rounded-btn bg-surface-50 px-4 text-[15px] font-semibold text-ink-900 ring-1 ring-line-200">
                  <span className="flex items-center gap-2">
                    <MapPin size={18} className="text-ink-500" />
                    {t(lang, "pickCity")}
                  </span>
                  <ChevronDown size={18} className="text-ink-500" />
                </button>
              ) : isName ? (
                <p className="mb-2 px-1 text-[12px] leading-snug text-ink-500">{t(lang, "nameHint")}</p>
              ) : s?.options ? (
                <div className="mb-3 grid grid-cols-2 gap-2">
                  {s.options.map((o) => (
                    <button
                      key={o.value}
                      onClick={() => answer(label(o, lang), o.num ?? o.value)}
                      className="press flex min-h-[48px] items-center justify-center rounded-btn bg-white px-3 text-center text-[15px] font-semibold text-ink-900 ring-1 ring-line-200 hover:ring-brand-500"
                    >
                      {label(o, lang)}
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="flex items-center gap-2">
                <button
                  onClick={() => startListen()}
                  aria-label={t(lang, "tap_speak")}
                  disabled={!mounted || isMulti || isName}
                  className={`press flex h-12 w-12 shrink-0 items-center justify-center rounded-full disabled:opacity-40 ${
                    mode === "voice" ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-600"
                  }`}
                >
                  <Mic size={20} />
                </button>
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleText(text)}
                  onFocus={() => {
                    if (!listening) return;
                    listenId.current++;
                    cancelListen();
                    setListening(false);
                    modeRef.current = "text";
                    setMode("text");
                  }}
                  lang={isName ? "en" : undefined}
                  autoCapitalize={isName ? "words" : undefined}
                  placeholder={isSelect ? t(lang, "typeOwn") : isName ? t(lang, "namePh") : isCity ? t(lang, "searchCity") : t(lang, "type_here")}
                  className="h-12 min-w-0 flex-1 rounded-full bg-surface-50 px-4 text-[15px] text-ink-900 outline-none ring-1 ring-line-200 placeholder:text-ink-400 focus:ring-2 focus:ring-brand-500"
                />
                <button
                  onClick={() => handleText(text)}
                  aria-label={t(lang, "send")}
                  disabled={!text.trim()}
                  className="press flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white disabled:bg-line-200 disabled:text-ink-400"
                >
                  <SendHorizontal size={20} />
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {citySheet && isCity && <CitySheet lang={lang} onClose={() => setCitySheet(false)} onPick={chooseCity} />}

      {sheet && isSelect && s?.options && (
        <BusinessSheet
          lang={lang}
          options={s.options}
          onClose={() => setSheet(false)}
          onPick={(v) => {
            setSheet(false);
            chooseSelect(v);
          }}
        />
      )}
    </div>
  );
}

function ModeCard({ onClick, disabled, icon, title, sub }: { onClick: () => void; disabled: boolean; icon: React.ReactNode; title: string; sub: string }) {
  return (
    <button onClick={onClick} disabled={disabled} className="press flex w-full items-center gap-4 rounded-card bg-white p-4 text-left shadow-soft disabled:opacity-50">
      {icon}
      <span className="min-w-0 flex-1">
        <span className="block text-[17px] font-bold text-ink-900">{title}</span>
        <span className="block text-[14px] leading-snug text-ink-500">{sub}</span>
      </span>
      <ChevronRight size={20} className="text-ink-400" />
    </button>
  );
}

function BusinessSheet({
  lang,
  options,
  onPick,
  onClose,
}: {
  lang: Lang;
  options: NonNullable<(typeof FLOW)[number]["options"]>;
  onPick: (v: string) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((o) => label(o, lang).toLowerCase().includes(needle) || o.keywords.some((k) => k.toLowerCase().includes(needle)));
  }, [q, options, lang]);
  return (
    <div className="absolute inset-0 z-50 flex flex-col justify-end">
      <button aria-label="Close" onClick={onClose} className="fade-in absolute inset-0 bg-ink-900/40" />
      <div className="sheet-up relative flex max-h-[82%] flex-col rounded-t-hero bg-white shadow-float">
        <div className="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-line-200" />
        <div className="flex items-center justify-between px-5 pb-2 pt-3">
          <h2 className="text-[18px] font-bold text-ink-900">{t(lang, "selectBiz")}</h2>
          <button onClick={onClose} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-50 text-ink-700">
            <X size={18} />
          </button>
        </div>
        <div className="px-5 pb-3">
          <label className="flex h-12 items-center gap-2 rounded-btn bg-surface-50 px-4 ring-1 ring-line-200 focus-within:ring-2 focus-within:ring-brand-500">
            <Search size={18} className="text-ink-500" />
            <input ref={useCalmFocus()} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(lang, "searchBiz")} className="h-full flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-400" />
          </label>
        </div>
        <div className="scroll-area flex-1 overflow-y-auto px-5 pb-6">
          {(["micro", "prof", "multi", "mfg"] as const).map((seg) => {
            const group = list.filter((o) => o.seg === seg);
            if (!group.length) return null;
            return (
              <div key={seg} className="mb-4">
                <div className="mb-2 text-[13px] font-semibold text-ink-500">{t(lang, `seg_${seg}`)}</div>
                <div className="overflow-hidden rounded-2xl ring-1 ring-line-200">
                  {group.map((o, i) => (
                    <button
                      key={o.value}
                      onClick={() => onPick(o.value)}
                      className={`flex h-12 w-full items-center justify-between px-4 text-left text-[15px] font-medium text-ink-900 hover:bg-surface-50 active:bg-brand-50 ${i ? "border-t border-line-100" : ""}`}
                    >
                      {label(o, lang)}
                      <ChevronRight size={18} className="text-ink-400" />
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CitySheet({ lang, onPick, onClose }: { lang: Lang; onPick: (en: string) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return CITIES;
    return CITIES.filter((c) => [c.en, ...Object.values(c.alt), ...(c.also ?? [])].some((x) => (x ?? "").toLowerCase().includes(n)));
  }, [q]);
  return (
    <div className="absolute inset-0 z-50 flex flex-col justify-end">
      <button aria-label="Close" onClick={onClose} className="fade-in absolute inset-0 bg-ink-900/40" />
      <div className="sheet-up relative flex max-h-[82%] flex-col rounded-t-hero bg-white shadow-float">
        <div className="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-line-200" />
        <div className="flex items-center justify-between px-5 pb-2 pt-3">
          <h2 className="text-[18px] font-bold text-ink-900">{t(lang, "pickCity")}</h2>
          <button onClick={onClose} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-50 text-ink-700">
            <X size={18} />
          </button>
        </div>
        <div className="px-5 pb-3">
          <label className="flex h-12 items-center gap-2 rounded-btn bg-surface-50 px-4 ring-1 ring-line-200 focus-within:ring-2 focus-within:ring-brand-500">
            <Search size={18} className="text-ink-500" />
            <input ref={useCalmFocus()} value={q} onChange={(e) => setQ(e.target.value)} placeholder={t(lang, "searchCity")} className="h-full flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-400" />
          </label>
        </div>
        <div className="scroll-area flex-1 overflow-y-auto px-5 pb-6">
          <div className="overflow-hidden rounded-2xl ring-1 ring-line-200">
            {list.map((c, i) => (
              <button
                key={c.en}
                onClick={() => onPick(c.en)}
                className={`flex h-12 w-full items-center justify-between px-4 text-left text-[15px] font-medium text-ink-900 hover:bg-surface-50 active:bg-brand-50 ${i ? "border-t border-line-100" : ""}`}
              >
                <span>
                  {cityLabel(c.en, lang)}
                  {lang !== "en" && <span className="ml-2 text-[13px] text-ink-400">{c.en}</span>}
                </span>
                <ChevronRight size={18} className="text-ink-400" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function useCalmFocus() {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (window.matchMedia("(pointer: coarse)").matches) return;
    const h = setTimeout(() => ref.current?.focus({ preventScroll: true }), 380);
    return () => clearTimeout(h);
  }, []);
  return ref;
}

function dataToProfile(d: Record<string, string | number | string[]>): Profile {
  return {
    segment: (d.segment as Segment) ?? "micro",
    business_type: d.business_type ? String(d.business_type) : undefined,
    employees: Number(d.employees ?? 1),
    num_sites: Number(d.num_sites ?? 1),
    city: String(d.city ?? ""),
    gstin_status: (d.gstin_status as GstinStatus) ?? "none",
    need_tags: Array.isArray(d.need_tags) ? (d.need_tags as string[]) : [],
  };
}
