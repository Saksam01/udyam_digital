"use client";
import { useState } from "react";
import { api, Profile, Quote, SuitableResult, SuitableProduct, rupees } from "@/lib/api";
import { Lang, t } from "@/lib/i18n";

export default function QuoteCard({
  quote,
  catalog,
  profile,
  onQuote,
  onProceed,
  lang,
}: {
  quote: Quote;
  catalog: SuitableResult | null;
  profile: Profile;
  onQuote: (q: Quote) => void;
  onProceed: () => void;
  lang: Lang;
}) {
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const items = Object.fromEntries(quote.lines.map((l) => [l.product_id, l.qty]));
  const blocked = quote.status === "blocked";

  const detail: Record<string, SuitableProduct> = {};
  for (const p of catalog?.products ?? []) detail[p.product_id] = p;

  // Add-ons: suitable, eligible, not already in the bundle.
  const addons = (catalog?.products ?? []).filter((p) => p.eligible && !items[p.product_id]);

  async function setItems(next: Record<string, number>) {
    setBusy(true);
    try {
      const list = Object.entries(next).map(([product_id, qty]) => ({ product_id, qty }));
      onQuote(await api.quote(profile, list));
    } catch {
      /* keep current */
    } finally {
      setBusy(false);
    }
  }

  function addProduct(id: string) {
    setItems({ ...items, [id]: 1 });
  }
  function removeProduct(id: string) {
    const next = { ...items };
    delete next[id];
    setItems(next);
  }

  function toggleOpen(id: string) {
    setOpen((o) => (o === id ? null : id));
  }

  function Detail({ p }: { p: SuitableProduct }) {
    return (
      <div className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-[11px] leading-relaxed text-slate-600">
        <div>{p.description}</div>
        <div className="mt-1 text-slate-400">
          {rupees(p.price_inr)} / {p.unit} · {rupees(p.setup_inr)} {t(lang, "setup")} · {p.min_contract_months}{" "}
          {t(lang, "months")} · ~{p.install_days} {t(lang, "days")}
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="bg-gradient-to-br from-[#ED1C24] to-[#B3121A] px-4 py-3 text-white">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-2xl font-bold tracking-tight">{rupees(quote.monthly_inr)}</div>
            <div className="text-[11px] text-red-100">
              {t(lang, "perMonth")} · {t(lang, "exclGst")}
            </div>
          </div>
          <span className="rounded-full bg-white/20 px-2.5 py-1 text-[11px] font-semibold">
            {blocked ? t(lang, "needsChanges") : t(lang, "ready")}
          </span>
        </div>
      </div>

      <div className="px-4 pt-3">
        <div className="grid grid-cols-3 gap-2 text-center text-[11px]">
          <Stat big={rupees(quote.setup_total_inr)} small={t(lang, "setup")} />
          <Stat big={`${quote.contract_months} ${t(lang, "months")}`} small={t(lang, "contract")} />
          <Stat big={`~${quote.activation_eta_days} ${t(lang, "days")}`} small={t(lang, "toActivate")} />
        </div>

        <div className="mt-3 mb-1.5 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{t(lang, "inBundle")}</span>
          <span className="text-[10px] text-slate-400">{t(lang, "tapDetail")}</span>
        </div>
        <ul className="space-y-1">
          {quote.lines.map((l) => (
            <li key={l.product_id} className="rounded-lg ring-1 ring-slate-100">
              <button onClick={() => toggleOpen(l.product_id)} className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-sm">
                <span className="text-slate-700">
                  {l.name} <span className="text-slate-400">×{l.qty}</span>
                </span>
                <span className="tabular-nums text-slate-600">{rupees(l.line_monthly_list_inr)}</span>
              </button>
              {open === l.product_id && detail[l.product_id] && (
                <div className="px-2.5 pb-2">
                  <Detail p={detail[l.product_id]} />
                  {quote.lines.length > 1 && (
                    <button
                      disabled={busy}
                      onClick={() => removeProduct(l.product_id)}
                      className="mt-1.5 text-[11px] font-medium text-slate-400 underline"
                    >
                      {t(lang, "addedLabel")} ✕
                    </button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>

        {addons.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{t(lang, "addons")}</div>
            <ul className="space-y-1">
              {addons.map((p) => (
                <li key={p.product_id} className="rounded-lg ring-1 ring-slate-100">
                  <div className="flex items-center justify-between px-2.5 py-1.5">
                    <button onClick={() => toggleOpen(p.product_id)} className="min-w-0 flex-1 text-left text-sm">
                      <span className="text-slate-700">{p.name}</span>
                      <span className="ml-1 text-xs text-slate-400">{rupees(p.price_inr)}/{p.unit}</span>
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => addProduct(p.product_id)}
                      className="ml-2 shrink-0 rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-[#ED1C24] ring-1 ring-red-200 active:scale-95 disabled:opacity-40"
                    >
                      + {t(lang, "addLabel")}
                    </button>
                  </div>
                  {open === p.product_id && (
                    <div className="px-2.5 pb-2">
                      <Detail p={p} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {blocked && (
          <div className="mt-3 rounded-lg bg-red-50 p-2.5 text-xs text-[#B3121A]">
            {quote.violations
              .filter((v) => v.severity === "block")
              .map((v) => (
                <div key={v.rule + v.product}>• {v.message}</div>
              ))}
          </div>
        )}
      </div>

      <div className="p-4 pt-3">
        <button
          disabled={blocked}
          onClick={onProceed}
          className="w-full rounded-full bg-[#ED1C24] py-3 text-sm font-semibold text-white disabled:opacity-40"
        >
          {t(lang, "proceed")}
        </button>
      </div>
    </div>
  );
}

function Stat({ big, small }: { big: string; small: string }) {
  return (
    <div className="rounded-lg bg-slate-50 py-2">
      <div className="font-semibold text-slate-800">{big}</div>
      <div className="text-slate-500">{small}</div>
    </div>
  );
}
