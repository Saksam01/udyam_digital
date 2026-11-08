"use client";
import { useEffect, useState } from "react";
import { ArrowRight, KeyRound, Loader2, MessageCircle, Smartphone } from "lucide-react";
import { api, Order } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";
import { Card, IconTile, btn } from "./ui";

export function savedCode(orderId: string): string {
  try {
    return window.localStorage.getItem(`udyam_code_${orderId}`) ?? "";
  } catch {
    return "";
  }
}

export function rememberCode(orderId: string, code: string) {
  try {
    window.localStorage.setItem(`udyam_code_${orderId}`, code);
  } catch {
    /* storage unavailable */
  }
}

const field =
  "h-12 w-full rounded-btn bg-surface-50 px-4 text-[15px] text-ink-900 outline-none ring-1 ring-line-200 placeholder:text-ink-400 focus:ring-2 focus:ring-brand-500";

export function ResumeCard({ lang, onOrder }: { lang: Lang; onOrder: (o: Order) => void }) {
  const [ref, setRef] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    try {
      const pre = window.sessionStorage.getItem("udyam_resume_ref");
      if (pre) setRef(pre);
    } catch {
      /* storage unavailable */
    }
  }, []);

  async function go() {
    setBusy(true);
    setErr("");
    try {
      const o = await api.resume(ref, code);
      rememberCode(o.order_id, code.replace(/\D/g, ""));
      onOrder(o);
    } catch (e) {
      setErr((e as { status?: number }).status === 429 ? t(lang, "resume_many") : t(lang, "resume_fail"));
    } finally {
      setBusy(false);
    }
  }

  const ready = ref.trim().length >= 10 && code.replace(/\D/g, "").length === 6;
  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <IconTile icon={KeyRound} tone="blue" size={44} />
        <div className="min-w-0">
          <h2 className="text-[17px] font-bold leading-snug text-ink-900">{t(lang, "resume_title")}</h2>
          <p className="mt-1 text-[13px] leading-snug text-ink-500">{t(lang, "resume_sub")}</p>
        </div>
      </div>
      <div className="mt-4 space-y-2.5">
        <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder={t(lang, "resume_ref")} autoCapitalize="characters" className={field} />
        <input
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
          onKeyDown={(e) => e.key === "Enter" && ready && go()}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder={t(lang, "resume_code")}
          className={`${field} tracking-[0.3em]`}
        />
      </div>
      {err && <p className="mt-2 text-[13px] font-medium text-danger-600">{err}</p>}
      <button onClick={go} disabled={!ready || busy} className={`${btn.dark} mt-3 w-full disabled:opacity-40`}>
        {busy ? <Loader2 size={18} className="animate-spin" /> : null}
        {t(lang, "resume_btn")}
        {!busy && <ArrowRight size={18} />}
      </button>
    </Card>
  );
}

export function SaveCard({ lang, order }: { lang: Lang; order: Order }) {
  const code = savedCode(order.order_id);
  const [phone, setPhone] = useState("");
  const [savedPhone, setSavedPhone] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    try {
      setSavedPhone(window.localStorage.getItem(`udyam_phone_${order.order_id}`) ?? "");
    } catch {
      /* storage unavailable */
    }
  }, [order.order_id]);
  const [busy, setBusy] = useState(false);
  if (!code) return null;

  const url = typeof window === "undefined" ? "" : `${window.location.origin}/?resume=${order.order_id}`;
  const share = t(lang, "share_text").replace("{id}", order.order_id).replace("{code}", code).replace("{url}", url);

  async function save() {
    setBusy(true);
    try {
      await api.savePhone(order.order_id, phone);
      const digits = phone.replace(/\D/g, "").slice(-10);
      try {
        window.localStorage.setItem(`udyam_phone_${order.order_id}`, digits);
      } catch {
        /* storage unavailable */
      }
      setSavedPhone(digits);
      setMsg({ ok: true, text: t(lang, "save_phone_ok") });
    } catch {
      setMsg({ ok: false, text: t(lang, "save_phone_bad") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="p-4">
      <div className="text-[15px] font-bold text-ink-900">{t(lang, "save_title")}</div>
      <p className="mt-1 text-[13px] leading-snug text-ink-500">{t(lang, "save_body")}</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-2xl bg-surface-50 px-3 py-2.5">
          <div className="text-[12px] font-semibold text-ink-500">{t(lang, "order_label")}</div>
          <div className="text-[15px] font-bold tabular-nums text-ink-900">{order.order_id}</div>
        </div>
        <div className="rounded-2xl bg-surface-50 px-3 py-2.5">
          <div className="text-[12px] font-semibold text-ink-500">{t(lang, "code_label")}</div>
          <div className="text-[15px] font-bold tracking-[0.2em] tabular-nums text-ink-900">{code}</div>
        </div>
      </div>
      <a
        href={`https://wa.me/?text=${encodeURIComponent(share)}`}
        target="_blank"
        rel="noreferrer"
        className="press mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-btn bg-[#1FAF5A] text-[14px] font-semibold text-white"
      >
        <MessageCircle size={17} />
        {t(lang, "save_share")}
      </a>
      {savedPhone && !msg ? (
        <p className="mt-3 text-[13px] font-medium text-success-600">{t(lang, "save_phone_ok")} (+91 ••••••{savedPhone.slice(-4)})</p>
      ) : (
      <div className="mt-3 flex items-center gap-2">
        <label className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-btn bg-surface-50 px-3 ring-1 ring-line-200 focus-within:ring-2 focus-within:ring-brand-500">
          <Smartphone size={16} className="shrink-0 text-ink-500" />
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/[^\d+ ]/g, "").slice(0, 15))}
            inputMode="tel"
            autoComplete="tel"
            placeholder={t(lang, "save_phone")}
            className="h-full min-w-0 flex-1 bg-transparent text-[14px] outline-none placeholder:text-ink-400"
          />
        </label>
        <button onClick={save} disabled={busy || phone.replace(/\D/g, "").length < 10} className={`${btn.secondary} h-11 shrink-0 px-4 disabled:opacity-40`}>
          {t(lang, "save_phone_btn")}
        </button>
      </div>
      )}
      {msg && <p className={`mt-2 text-[12px] font-medium ${msg.ok ? "text-success-600" : "text-danger-600"}`}>{msg.text}</p>}
    </Card>
  );
}
