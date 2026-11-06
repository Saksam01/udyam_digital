"use client";
import { useEffect, useRef, useState } from "react";
import { api, KycCase, KycResult, KycExtract } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";

const VERDICT: Record<string, string> = {
  PASS: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  REVIEW: "bg-amber-50 text-amber-700 ring-amber-200",
  REJECT: "bg-rose-50 text-rose-700 ring-rose-200",
};

const SLOTS: { key: string; labelKey: string }[] = [
  { key: "gst", labelKey: "docGst" },
  { key: "udyam", labelKey: "docUdyam" },
  { key: "sig", labelKey: "docSig" },
  { key: "bill", labelKey: "docBill" },
];

export default function KycPanel({ lang }: { lang: Lang }) {
  const [consented, setConsented] = useState(false);
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [extract, setExtract] = useState<KycExtract | null>(null);
  const [cases, setCases] = useState<KycCase[]>([]);
  const [result, setResult] = useState<KycResult | null>(null);
  const [grid, setGrid] = useState<KycResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    api.kycCases().then(setCases).catch(() => setErr("Backend not reachable on port 8000."));
  }, []);

  async function verify() {
    const gst = files.gst;
    if (!gst) return;
    setBusy(true);
    setExtract(null);
    try {
      setExtract(await api.kycExtract(gst));
    } catch {
      setExtract({ ocr_available: false, message: "Could not reach the server." });
    } finally {
      setBusy(false);
    }
  }

  async function assess(id: string) {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.assess(id));
    } finally {
      setBusy(false);
    }
  }

  if (!consented) {
    return (
      <div className="space-y-4 overflow-y-auto pb-2">
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="text-sm font-semibold text-slate-800">{t(lang, "consentTitle")}</h2>
          <p className="mt-2 text-xs leading-relaxed text-slate-600">{t(lang, "consentBody")}</p>
          <button
            onClick={() => setConsented(true)}
            className="mt-4 w-full rounded-full bg-[#ED1C24] py-2.5 text-sm font-semibold text-white"
          >
            {t(lang, "consentAgree")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 overflow-y-auto pb-2">
      <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold text-slate-800">{t(lang, "uploadTitle")}</h2>
        <p className="mt-1 text-xs text-slate-500">{t(lang, "uploadHint")}</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {SLOTS.map((sl) => (
            <div key={sl.key}>
              <input
                ref={(el) => { inputs.current[sl.key] = el; }}
                type="file"
                accept="image/*,application/pdf"
                capture="environment"
                className="hidden"
                onChange={(e) => setFiles((f) => ({ ...f, [sl.key]: e.target.files?.[0] ?? null }))}
              />
              <button
                onClick={() => inputs.current[sl.key]?.click()}
                className={`flex h-16 w-full flex-col items-center justify-center rounded-lg border border-dashed px-2 text-center text-[11px] ${
                  files[sl.key] ? "border-emerald-300 bg-emerald-50 text-emerald-700" : "border-slate-300 bg-slate-50 text-slate-500"
                }`}
              >
                <span className="font-medium">{t(lang, sl.labelKey)}</span>
                <span className="mt-0.5 truncate text-[10px] opacity-70">
                  {files[sl.key]?.name ?? "+"}
                </span>
              </button>
            </div>
          ))}
        </div>
        <button
          onClick={verify}
          disabled={busy || !files.gst}
          className="mt-3 w-full rounded-full bg-[#ED1C24] py-2.5 text-sm font-semibold text-white disabled:opacity-40"
        >
          {busy ? t(lang, "verifying") : t(lang, "uploadCta")}
        </button>

        {extract && !extract.ocr_available && (
          <p className="mt-3 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-700">{extract.message ?? t(lang, "ocrOff")}</p>
        )}
        {extract?.ocr_available && extract.message && !extract.validation && (
          <p className="mt-3 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-700">{extract.message}</p>
        )}
        {extract?.validation && (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs">
            <div className="text-[11px] text-slate-400">{t(lang, "readFrom")}</div>
            <div className="mt-0.5 font-mono text-sm font-semibold tracking-tight text-slate-800">{extract.extracted?.gstin}</div>
            {extract.validation.legal_name && <div className="mt-0.5 text-slate-600">{extract.validation.legal_name}</div>}
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Pill ok={extract.validation.checksum_ok} text="Checksum" />
              <Pill ok={extract.validation.in_registry} text={t(lang, "inRegistry")} />
              <span
                className={`rounded px-2 py-0.5 text-[10px] font-semibold ring-1 ${
                  extract.validation.registry_status === "Active"
                    ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                    : "bg-rose-50 text-rose-700 ring-rose-200"
                }`}
              >
                {t(lang, "statusLbl")}: {extract.validation.registry_status ?? "-"}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="text-xs font-semibold text-slate-500">{t(lang, "orSamples")}</div>
        {err && <p className="mt-2 text-xs text-rose-600">{err}</p>}
        <div className="mt-3 grid grid-cols-3 gap-2">
          {cases.map((c) => (
            <button
              key={c.case_id}
              onClick={() => assess(c.case_id)}
              className="rounded-lg bg-slate-50 px-2 py-2 text-xs ring-1 ring-slate-200 active:scale-95"
            >
              <div className="font-semibold text-slate-800">{c.case_id}</div>
              <div className="truncate text-[10px] text-slate-400">{c.business}</div>
            </button>
          ))}
        </div>
        <button
          onClick={async () => {
            setBusy(true);
            try {
              setGrid(await api.assessAll());
            } finally {
              setBusy(false);
            }
          }}
          className="mt-3 w-full rounded-full bg-slate-800 py-2 text-xs font-semibold text-white"
        >
          {t(lang, "kyc_runall")}
        </button>
      </div>

      {result && (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-800">{result.business}</div>
              <div className="text-xs text-slate-400">{result.case_id}</div>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${VERDICT[result.verdict]}`}>{result.verdict}</span>
          </div>
          <ul className="mt-3 space-y-2">
            {result.findings.length === 0 && <li className="text-xs text-emerald-700">{t(lang, "kyc_allpass")}</li>}
            {result.findings.map((f) => (
              <li key={f.code} className="text-xs">
                <span
                  className={`mr-2 rounded px-1.5 py-0.5 font-mono text-[10px] ${
                    f.severity === "HARD"
                      ? "bg-rose-100 text-rose-700"
                      : f.severity === "REVIEW"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {f.code}
                </span>
                <span className="text-slate-700">{f.message}</span>
                {f.customer_action && <div className="ml-10 text-[11px] text-slate-400">→ {f.customer_action}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {grid.length > 0 && (
        <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <div className="mb-2 text-xs font-semibold text-slate-500">{t(lang, "kyc_applicants")}</div>
          <div className="grid grid-cols-2 gap-2">
            {grid.map((r) => (
              <div key={r.case_id} className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5 text-xs">
                <span className="font-mono text-slate-600">{r.case_id}</span>
                <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ring-1 ${VERDICT[r.verdict]}`}>{r.verdict}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Pill({ ok, text }: { ok: boolean; text: string }) {
  return (
    <span
      className={`rounded px-2 py-0.5 text-[10px] font-semibold ring-1 ${
        ok ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-rose-50 text-rose-700 ring-rose-200"
      }`}
    >
      {ok ? "✓" : "✕"} {text}
    </span>
  );
}
