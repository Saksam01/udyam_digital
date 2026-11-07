"use client";
import { useState } from "react";
import { API_BASE } from "@/lib/api";

type Lead = {
  lead_id: string;
  business: string;
  segment: string;
  city: string;
  language: string;
  stage: string;
  drop_reason: string | null;
  p_activate: number;
  rule_points: number;
  reasons: string;
  monthly_spend: number | null;
};

export default function Admin() {
  const [pw, setPw] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function login() {
    setBusy(true);
    setErr("");
    try {
      const r = await fetch(`${API_BASE}/api/v1/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      if (!r.ok) {
        setErr("Wrong password.");
        return;
      }
      const { token: tk } = await r.json();
      setToken(tk);
      const lr = await fetch(`${API_BASE}/api/v1/admin/leads`, { headers: { Authorization: `Bearer ${tk}` } });
      setLeads(await lr.json());
    } catch {
      setErr("Backend not reachable on port 8000.");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <div className="flex items-baseline gap-1.5">
            <span className="text-lg font-extrabold tracking-tight text-[#ED1C24]">Accel</span>
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-white">Sales console</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">Back-office access for sales and channel partners.</p>
          <input
            type="password"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && login()}
            placeholder="Admin password"
            className="mt-4 h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none focus:border-[#ED1C24]"
          />
          {err && <p className="mt-2 text-xs text-rose-600">{err}</p>}
          <button
            onClick={login}
            disabled={busy || !pw}
            className="mt-3 w-full rounded-full bg-[#ED1C24] py-2.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </main>
    );
  }

  const callNow = leads.slice(0, 5);
  const pct = (p: number) => `${Math.round(p * 100)}%`;

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="bg-gradient-to-br from-[#ED1C24] to-[#B3121A] px-6 py-4 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-extrabold tracking-tight">Accel</span>
            <span className="rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase">Sales console</span>
          </div>
          <span className="text-xs text-red-100">{leads.length} open leads the advisor could not close</span>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-6">
        <h2 className="text-sm font-semibold text-slate-700">Call next — highest activation propensity</h2>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {callNow.map((l) => (
            <div key={l.lead_id} className="rounded-xl bg-white p-3 shadow-sm ring-1 ring-slate-200">
              <div className="flex items-baseline justify-between">
                <span className="text-lg font-bold text-[#ED1C24]">{pct(l.p_activate)}</span>
                <span className="text-[10px] text-slate-400">score {l.rule_points}/7</span>
              </div>
              <div className="mt-1 truncate text-sm font-medium text-slate-800">{l.business}</div>
              <div className="truncate text-[11px] text-slate-500">
                {l.city} · {l.language}
              </div>
            </div>
          ))}
        </div>

        <h2 className="mt-6 text-sm font-semibold text-slate-700">All open leads</h2>
        <div className="mt-2 overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Propensity</th>
                <th className="px-3 py-2 font-medium">Business</th>
                <th className="px-3 py-2 font-medium">Segment</th>
                <th className="px-3 py-2 font-medium">City</th>
                <th className="px-3 py-2 font-medium">Stalled at</th>
                <th className="px-3 py-2 font-medium">Why it dropped</th>
                <th className="px-3 py-2 font-medium">Top signals</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((l) => (
                <tr key={l.lead_id} className="border-t border-slate-100">
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-[#ED1C24]" style={{ width: pct(l.p_activate) }} />
                      </div>
                      <span className="tabular-nums font-semibold text-slate-700">{pct(l.p_activate)}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2 font-medium text-slate-800">{l.business}</td>
                  <td className="px-3 py-2 text-slate-600">{l.segment}</td>
                  <td className="px-3 py-2 text-slate-600">{l.city}</td>
                  <td className="px-3 py-2 text-slate-600">{l.stage}</td>
                  <td className="px-3 py-2 text-slate-500">{l.drop_reason ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-slate-500">{l.reasons}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-slate-400">
          Propensity and signals come from a leakage-free model trained on the leads data. Digital hands these scored,
          warm leads to the field force instead of competing with them.
        </p>
      </div>
    </main>
  );
}
