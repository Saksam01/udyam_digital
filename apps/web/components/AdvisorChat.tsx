"use client";
import { useEffect, useRef, useState } from "react";
import { api, Profile, Quote, Segment, GstinStatus, SuitableResult } from "@/lib/api";
import { FLOW, Lang, label, question, matchOption, parseNumber, t, localeFor } from "@/lib/i18n";
import { sttSupported, listenOnce, speak, stopSpeaking } from "@/lib/speech";
import { sarvamOn, sarvamSpeak, sarvamListen, sarvamTtsError, ListenResult } from "@/lib/sarvam";
import QuoteCard from "./QuoteCard";

type Msg = { id: number; role: "bot" | "user"; text: string };
type Mode = "text" | "voice" | null;

export default function AdvisorChat({
  lang,
  quote,
  setQuote,
  setProfile,
  onProceed,
}: {
  lang: Lang;
  quote: Quote | null;
  setQuote: (q: Quote | null) => void;
  setProfile: (p: Profile) => void;
  onProceed: () => void;
}) {
  const locale = localeFor(lang);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [, setStep] = useState(0);
  const [data, setData] = useState<Record<string, string | number | string[]>>({});
  const [listening, setListening] = useState(false);
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const [mode, setMode] = useState<Mode>(null);
  const [mounted, setMounted] = useState(false);
  const [picks, setPicks] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<SuitableResult | null>(null);

  const idRef = useRef(0);
  const initRef = useRef(false);
  const stepRef = useRef(0);
  const modeRef = useRef<Mode>(null);
  const sarvamRef = useRef(false);
  const dataRef = useRef<Record<string, string | number | string[]>>({});
  const endRef = useRef<HTMLDivElement>(null);

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
    sarvamOn().then((on) => (sarvamRef.current = on));
  }, []);
  useEffect(() => () => stopSpeaking(), []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, quote, listening]);

  function speakQ(text: string, onEnd?: () => void) {
    if (sarvamRef.current) sarvamSpeak(text, locale, onEnd);
    else speak(text, locale, onEnd);
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
    setListening(true);
    listen()
      .then((res) => {
        setListening(false);
        if (res.transcript) {
          handleText(res.transcript);
        } else if (!res.heardSpeech) {
          fallbackToText("noVoiceHeard");
        } else {
          fallbackToText("notUnderstood");
        }
      })
      .catch((e: unknown) => {
        setListening(false);
        console.warn("voice error:", e);
        fallbackToText("voiceUnavailable");
      });
  }

  function chooseMode(m: Exclude<Mode, null>) {
    modeRef.current = m;
    setMode(m);
    add("user", m === "voice" ? t(lang, "opt_speak") : t(lang, "opt_type"));

    if (m === "voice" && sarvamRef.current) {
      sarvamTtsError(locale).then((err) => {
        if (err) {
          console.warn("TTS unavailable:", err);
          modeRef.current = "text";
          setMode("text");
          add("bot", t(lang, "voiceUnavailable"));
        }
        askStep(0);
      });
      return;
    }
    askStep(0);
  }

  function askStep(i: number) {
    stepRef.current = i;
    setStep(i);
    if (i >= FLOW.length) {
      recommend();
      return;
    }
    if (FLOW[i].kind === "multi") setPicks([]);
    const q = question(FLOW[i], lang);
    add("bot", q);
    // Voice auto-listens on single-answer steps; dropdown and multi-select are tapped.
    if (modeRef.current === "voice") {
      if (FLOW[i].kind === "multi" || FLOW[i].kind === "select") speakQ(q);
      else speakQ(q, () => startListen());
    }
  }

  function record(field: string, value: string | number | string[]) {
    dataRef.current = { ...dataRef.current, [field]: value };
    setData(dataRef.current);
  }

  function answer(display: string, value: string | number) {
    const i = stepRef.current;
    add("user", display);
    record(FLOW[i].field, value);
    setText("");
    setTimeout(() => askStep(i + 1), 350);
  }

  function chooseSelect(value: string) {
    const i = stepRef.current;
    const opt = FLOW[i].options!.find((o) => o.value === value);
    if (!opt) return;
    answer(label(opt, lang), opt.seg ?? value);
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
    setTimeout(() => askStep(i + 1), 350);
  }

  async function recommend() {
    add("bot", t(lang, "recommending"));
    const d = dataRef.current;
    const prof: Profile = {
      segment: (d.segment as Segment) ?? "micro",
      employees: Number(d.employees ?? 1),
      num_sites: Number(d.num_sites ?? 1),
      city: String(d.city ?? ""),
      gstin_status: (d.gstin_status as GstinStatus) ?? "none",
    };
    setProfile(prof);
    const categories = Array.isArray(d.needs) ? (d.needs as string[]) : [];
    try {
      const r = await api.advisor("web-demo", { ...prof, needs: [] }, "", lang);
      add("bot", r.text);
      if (modeRef.current === "voice") speakQ(r.text);
      setQuote(r.quote_card);
      try {
        setCatalog(await api.suitable(prof, categories, []));
      } catch {
        /* product detail is optional */
      }
    } catch {
      add("bot", "Could not reach the advisor. Is the backend running on port 8000?");
    }
    setDone(true);
  }

  function handleText(raw: string) {
    const input = raw.trim();
    if (!input) return;
    const s = FLOW[stepRef.current];
    if (s.kind === "multi") return; // answered by tapping chips
    if (s.kind === "text") return answer(input, input);
    if (s.kind === "number") {
      const n = parseNumber(input);
      if (n != null) return answer(String(n), n);
    }
    const v = matchOption(s, input, lang);
    if (v) {
      const opt = s.options!.find((o) => o.value === v)!;
      return answer(label(opt, lang), s.kind === "select" ? opt.seg ?? v : opt.num ?? v);
    }
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

  return (
    <div className="flex h-full flex-col">
      <div className="scroll-area flex-1 space-y-2.5 overflow-y-auto px-1 pb-2">
        {msgs.map((m) => (
          <div key={m.id} className={`rise flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "rounded-br-md bg-[#ED1C24] text-white"
                  : "rounded-bl-md bg-white text-slate-800 shadow-sm ring-1 ring-slate-100"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}

        {quote && (
          <div className="rise pt-1">
            <QuoteCard quote={quote} catalog={catalog} profile={dataToProfile(data)} onQuote={setQuote} onProceed={onProceed} lang={lang} />
          </div>
        )}
        <div ref={endRef} />
      </div>

      {!done && (
        <div className="border-t border-slate-200 bg-white px-3 pb-3 pt-2.5">
          {mode === null ? (
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => chooseMode("text")}
                disabled={!mounted}
                className="flex items-center justify-center gap-2 rounded-xl bg-slate-800 py-3 text-sm font-semibold text-white disabled:opacity-40"
              >
                <ChatGlyph /> {t(lang, "opt_type")}
              </button>
              <button
                onClick={() => chooseMode("voice")}
                disabled={!mounted}
                className="flex items-center justify-center gap-2 rounded-xl bg-[#ED1C24] py-3 text-sm font-semibold text-white disabled:opacity-40"
              >
                <MicIcon /> {t(lang, "opt_speak")}
              </button>
            </div>
          ) : (
            <>
              {listening && (
                <div className="mb-2 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-[#B3121A]">
                  <span className="mic-live inline-block h-2.5 w-2.5 rounded-full bg-[#ED1C24]" />
                  {t(lang, "speakPrompt")}
                </div>
              )}

              {isSelect && s?.options ? (
                <select
                  defaultValue=""
                  onChange={(e) => e.target.value && chooseSelect(e.target.value)}
                  className="mb-2 h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-[#ED1C24]"
                >
                  <option value="" disabled>
                    {t(lang, "selectBiz")}
                  </option>
                  {s.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {label(o, lang)}
                    </option>
                  ))}
                </select>
              ) : isMulti && s?.options ? (
                <div className="mb-2">
                  <div className="flex flex-wrap gap-2">
                    {s.options.map((o) => {
                      const on = picks.includes(o.value);
                      return (
                        <button
                          key={o.value}
                          onClick={() => togglePick(o.value)}
                          className={`rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition active:scale-95 ${
                            on ? "bg-[#ED1C24] text-white ring-[#ED1C24]" : "bg-red-50 text-[#B3121A] ring-red-200"
                          }`}
                        >
                          {on ? "✓ " : ""}
                          {label(o, lang)}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    onClick={submitMulti}
                    className="mt-2 w-full rounded-full bg-slate-800 py-2 text-xs font-semibold text-white"
                  >
                    {t(lang, "continueBtn")}
                  </button>
                </div>
              ) : s?.options ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {s.options.map((o) => (
                    <button
                      key={o.value}
                      onClick={() => answer(label(o, lang), o.num ?? o.value)}
                      className="rounded-full bg-red-50 px-3 py-1.5 text-xs font-medium text-[#B3121A] ring-1 ring-red-200 active:scale-95"
                    >
                      {label(o, lang)}
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="flex items-center gap-2">
                <button
                  onClick={() => startListen()}
                  aria-label="speak"
                  disabled={!mounted || listening || isMulti || isSelect}
                  className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white disabled:opacity-40 ${
                    listening ? "mic-live bg-[#ED1C24]" : "bg-[#ED1C24]"
                  }`}
                >
                  <MicIcon />
                </button>
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleText(text)}
                  placeholder={listening ? t(lang, "speakPrompt") : t(lang, "type_here")}
                  className="h-11 flex-1 rounded-full border border-slate-200 bg-slate-50 px-4 text-sm outline-none focus:border-[#ED1C24]"
                />
                <button
                  onClick={() => handleText(text)}
                  className="h-11 shrink-0 rounded-full bg-slate-800 px-4 text-xs font-semibold text-white"
                >
                  {t(lang, "send")}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function dataToProfile(d: Record<string, string | number | string[]>): Profile {
  return {
    segment: (d.segment as Segment) ?? "micro",
    employees: Number(d.employees ?? 1),
    num_sites: Number(d.num_sites ?? 1),
    city: String(d.city ?? ""),
    gstin_status: (d.gstin_status as GstinStatus) ?? "none",
  };
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
function ChatGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}
