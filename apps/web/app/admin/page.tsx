"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  Eye,
  EyeOff,
  Info,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Package,
  ScanText,
  Search,
  ShieldCheck,
  Smartphone,
  Truck,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AdminLead, AdminOrder, AdminOverview, ModelCard, Role, api, rupees, subscribe } from "@/lib/api";
import { Chip, ChipTone, CountUp, IconTile, LiveDot, Tone } from "@/components/ui";
import { AccelLogo, AccelMark } from "@/components/Logo";
import { LeadDrawer, ORDER_STATUS, OrderControls, OrdersView, QuickActions, RoleContext, ScoreTip } from "@/components/AdminPanels";
import { KycSamplesView, ReviewDesk } from "@/components/VerifyDesk";

type View = "today" | "review" | "fulfilment" | "orders" | "pipeline" | "kyc" | "desk" | "privacy";

const SIGNAL: Record<string, ChipTone> = { good: "success", warn: "warning", bad: "danger" };

const STATUS = ORDER_STATUS;

const AV_TONES: Tone[] = ["blue", "teal", "amber", "green", "red"];
function avatarTone(s: string): Tone {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AV_TONES[h % AV_TONES.length];
}
const AV: Record<Tone, string> = {
  blue: "bg-info-50 text-info-600",
  teal: "bg-aqua-50 text-aqua-600",
  amber: "bg-warning-50 text-warning-600",
  green: "bg-success-50 text-success-600",
  red: "bg-brand-50 text-brand-600",
  slate: "bg-slate2-50 text-slate2-600",
};
function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const ini = name
    .split(" ")
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span className={`flex shrink-0 items-center justify-center rounded-[12px] text-[13px] font-bold ${AV[avatarTone(name)]}`} style={{ width: size, height: size }}>
      {ini}
    </span>
  );
}

function ago(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Admin() {
  const [pw, setPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role>("sales");
  const [data, setData] = useState<AdminOverview | null>(null);
  const [view, setView] = useState<View>("today");
  const [q, setQ] = useState("");
  const [liveOnly, setLiveOnly] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [help, setHelp] = useState(false);
  const [leadStatus, setLeadStatus] = useState("open");
  const [openLead, setOpenLead] = useState<string | null>(null);

  useEffect(() => {
    try {
      setToken(window.sessionStorage.getItem("udyam_admin"));
      const r = window.sessionStorage.getItem("udyam_role") as Role | null;
      if (r) {
        setRole(r);
        if (r === "verifier") setView("desk");
      }
    } catch {
      /* storage unavailable */
    }
  }, []);

  const [table, setTable] = useState<{ leads: AdminLead[]; matched: number } | null>(null);
  const [tableBusy, setTableBusy] = useState(false);
  const tableReq = useRef(0);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setData(await api.overview(token, "", "", false, "open", 20));
      setErr("");
    } catch {
      setErr("Could not refresh. Retrying.");
    }
  }, [token]);

  const loadTable = useCallback(async () => {
    if (!token || role !== "sales") return;
    const id = ++tableReq.current;
    setTableBusy(true);
    try {
      const r = await api.leads(token, leadStatus, liveOnly, q);
      if (id === tableReq.current) setTable(r);
    } catch {
      /* keep the last result */
    } finally {
      if (id === tableReq.current) setTableBusy(false);
    }
  }, [token, role, leadStatus, liveOnly, q]);

  useEffect(() => {
    if (view !== "pipeline") return;
    const h = setTimeout(loadTable, q ? 250 : 0);
    return () => clearTimeout(h);
  }, [view, loadTable, q]);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshTable = useRef<() => void>(() => {});
  refreshTable.current = () => {
    if (view === "pipeline") loadTable();
  };
  useEffect(() => {
    if (!token) return;
    load();
    const stop = subscribe(`/api/v1/admin/stream?t=${token}`, () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        load();
        refreshTable.current();
      }, 250);
    });
    return () => {
      stop();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [token, load]);

  async function login() {
    setBusy(true);
    setErr("");
    try {
      const { token: tk, role: r } = await api.adminLogin(pw);
      try {
        window.sessionStorage.setItem("udyam_admin", tk);
        window.sessionStorage.setItem("udyam_role", r);
      } catch {
        /* storage unavailable */
      }
      setRole(r);
      setView(r === "verifier" ? "desk" : "today");
      setToken(tk);
    } catch {
      setErr("Wrong password.");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    try {
      window.sessionStorage.removeItem("udyam_admin");
      window.sessionStorage.removeItem("udyam_role");
    } catch {
      /* storage unavailable */
    }
    setToken(null);
    setData(null);
  }

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface-50 px-4">
        <div className="enter w-full max-w-[400px]">
          <div className="rounded-[24px] bg-white p-7 shadow-soft">
            <AccelLogo size={40} />
            <h1 className="mt-6 text-[24px] font-bold leading-tight text-ink-900">Accel Business back office</h1>
            <p className="mt-1 text-[14px] text-ink-500">
              Your password opens your desk: the sales console for leads and setups, or the verification desk for documents. Sales never sees customer documents.
            </p>
            <label className="mt-6 block text-[13px] font-semibold text-ink-700" htmlFor="pw">
              Password
            </label>
            <div className="mt-1.5 flex h-12 items-center rounded-btn bg-surface-50 px-4 ring-1 ring-line-200 focus-within:ring-2 focus-within:ring-brand-500">
              <input
                id="pw"
                type={showPw ? "text" : "password"}
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && login()}
                className="h-full flex-1 bg-transparent text-[15px] outline-none"
              />
              <button onClick={() => setShowPw((s) => !s)} aria-label={showPw ? "Hide password" : "Show password"} className="text-ink-500">
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            <button
              onClick={login}
              disabled={busy || !pw}
              className="press mt-4 h-12 w-full rounded-btn bg-brand-600 text-[15px] font-semibold text-white disabled:opacity-40"
            >
              Sign in
            </button>
            {err && <p className="mt-3 text-[13px] font-medium text-danger-600">{err}</p>}
          </div>
          <p className="mt-4 text-center text-[12px] text-ink-400">Udyam Digital · internal tool</p>
        </div>
      </main>
    );
  }

  const k = data?.kpi;
  const nav: { id: View; label: string; icon: LucideIcon; n?: number; alert?: boolean }[] =
    role === "verifier"
      ? [
          { id: "desk", label: "Review desk", icon: ShieldCheck, n: data?.review_queue.length, alert: true },
          { id: "kyc", label: "KYC samples", icon: ScanText, n: 12 },
          { id: "privacy", label: "Data and privacy", icon: Database },
        ]
      : [
          { id: "today", label: "Today", icon: LayoutDashboard },
          { id: "review", label: "Document checks", icon: ShieldCheck, n: data?.review_queue.length },
          { id: "fulfilment", label: "Fulfilment", icon: Truck, n: data?.fulfilment.length },
          { id: "orders", label: "All orders", icon: Package },
          { id: "pipeline", label: "All leads", icon: ListChecks, n: k?.open_leads },
        ];
  const title = nav.find((n) => n.id === view)?.label ?? "";

  return (
    <RoleContext.Provider value={role}>
    <div className="flex min-h-screen bg-surface-50">
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col bg-sidebar-900 px-3 py-5 text-white lg:flex">
        <div className="flex items-center gap-2.5 px-2">
          <AccelMark size={38} variant="solid" />
          <div>
            <div className="text-[15px] font-bold leading-tight">Accel Business</div>
            <div className="text-[12px] text-white/50">{role === "verifier" ? "Verification desk" : "Sales console"}</div>
          </div>
        </div>
        <div className="mt-8 px-3 text-[12px] font-semibold text-white/40">Overview</div>
        <nav className="mt-2 space-y-1">
          {nav.map((n) => {
            const on = view === n.id;
            const Icon = n.icon;
            return (
              <button
                key={n.id}
                onClick={() => setView(n.id)}
                className={`relative flex h-11 w-full items-center gap-3 rounded-xl px-3 text-[14px] font-medium transition-colors ${
                  on ? "bg-sidebar-700 text-white" : "text-white/65 hover:bg-sidebar-800 hover:text-white"
                }`}
              >
                {on && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-500" />}
                <Icon size={19} strokeWidth={1.9} className={on ? "text-brand-500" : ""} />
                <span className="flex-1 text-left">{n.label}</span>
                {n.n != null && n.n > 0 && (
                  <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-bold ${n.alert ? "bg-brand-600 text-white" : "bg-white/10 text-white/70"}`}>
                    {n.n.toLocaleString("en-IN")}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-white/10 pt-4">
          <button onClick={logout} className="flex h-11 w-full items-center gap-3 rounded-xl px-3 text-[14px] font-semibold text-brand-500 hover:bg-sidebar-800">
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 border-b border-line-200 bg-white/95 px-5 py-3 backdrop-blur lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-[20px] font-bold text-ink-900">{view === "today" ? `${greeting()}` : title}</h1>
              <div className="flex items-center gap-2 text-[12px] text-ink-500">
                <LiveDot />
                Live · updates the moment anything changes
                {err && <span className="font-semibold text-danger-600">· {err}</span>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              {view === "pipeline" && (
                <label className="flex h-10 w-64 items-center gap-2 rounded-xl bg-surface-50 px-3 ring-1 ring-line-200 focus-within:ring-2 focus-within:ring-brand-500">
                  <Search size={16} className="text-ink-400" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search business, type or city" className="h-full flex-1 bg-transparent text-[13px] outline-none" />
                </label>
              )}
              <button onClick={logout} className="flex h-10 items-center gap-2 rounded-xl px-3 text-[13px] font-semibold text-ink-700 ring-1 ring-line-200 lg:hidden">
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          </div>
          <nav className="no-scrollbar -mx-1 mt-3 flex gap-1 overflow-x-auto lg:hidden">
            {nav.map((n) => (
              <button
                key={n.id}
                onClick={() => setView(n.id)}
                className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-[13px] font-semibold ${view === n.id ? "bg-ink-900 text-white" : "text-ink-500 ring-1 ring-line-200"}`}
              >
                {n.label}
                {n.n != null && n.n > 0 && <span className="ml-1.5 opacity-70">{n.n.toLocaleString("en-IN")}</span>}
              </button>
            ))}
          </nav>
        </header>

        <main className="space-y-6 px-5 py-6 lg:px-8">
          {role === "sales" && (
          <section className="stagger grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            <Kpi icon={UserPlus} tone="blue" label="Open leads" value={k?.open_leads} />
            <Kpi icon={Smartphone} tone="red" label="New from the app today" value={k?.live_today} />
            <Kpi icon={Eye} tone="amber" label="With the verification desk" value={k?.awaiting_review} onClick={() => setView("review")} />
            <Kpi icon={Truck} tone="teal" label="In fulfilment" value={k?.in_fulfilment} onClick={() => setView("fulfilment")} />
            <Kpi icon={CheckCircle2} tone="green" label="Activated" value={k?.activated} />
          </section>
          )}

          {!data && (
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="skeleton h-64 rounded-card lg:col-span-2" />
              <div className="skeleton h-64 rounded-card" />
            </div>
          )}
          {data && !data.ready && (
            <p className="flex items-center gap-2 rounded-2xl bg-warning-50 p-3 text-[13px] text-warning-600">
              <Info size={16} />
              Loading the historical pipeline. New app activity is already shown.
            </p>
          )}

          {data && view === "today" && (
            <div className="grid gap-6 xl:grid-cols-3">
              <div className="space-y-6 xl:col-span-2">
                <Block title="Live from the app" hint="Customers using the app right now and what they chose" icon={Smartphone} tone="red">
                  {data.live_leads.length === 0 && <Empty text="Nobody has used the app yet. Leads appear here the moment a customer gets a recommendation." />}
                  {data.live_leads.map((l) => (
                    <LeadCard key={l.lead_id} lead={l} token={token} onDone={load} onOpen={setOpenLead} />
                  ))}
                </Block>
                <Block
                  title="Call these next"
                  hint="Highest chance of activating among open leads"
                  icon={Users}
                  tone="blue"
                  right={
                    <button onClick={() => setHelp((h) => !h)} className="flex items-center gap-1 text-[12px] font-semibold text-brand-600">
                      <Info size={14} />
                      How is the % calculated?
                    </button>
                  }
                >
                  {help && <Explainer card={data.model_card} />}
                  {data.call_next.map((l) => (
                    <LeadCard key={l.lead_id} lead={l} token={token} onDone={load} onOpen={setOpenLead} />
                  ))}
                </Block>
              </div>
              <Block title="Activity" hint="Everything that just happened" icon={Activity} tone="teal">
                <ol className="relative">
                  {data.activity.map((a, i) => (
                    <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                      {i < data.activity.length - 1 && <span className="absolute left-[5px] top-4 h-full w-0.5 bg-line-100" aria-hidden="true" />}
                      <span className={`relative mt-1 h-3 w-3 shrink-0 rounded-full ring-4 ring-white ${i === 0 ? "bg-brand-500" : "bg-line-200"}`} />
                      <div className="min-w-0 text-[13px]">
                        <div className="leading-snug text-ink-900">{a.text}</div>
                        <div className="mt-0.5 text-[12px] text-ink-400">
                          {a.business ? `${a.business} · ` : ""}
                          {ago(a.ts)}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              </Block>
            </div>
          )}

          {data && view === "review" && (
            <div className="space-y-4">
              <p className="flex items-start gap-2 rounded-2xl bg-white p-4 text-[13px] leading-relaxed text-ink-700 shadow-soft">
                <Info size={16} className="mt-0.5 shrink-0 text-info-600" />
                Orders whose documents a person has to check. The verification desk decides; you see the outcome and what is blocking it, never the documents
                themselves.
              </p>
              {data.review_queue.length === 0 && <Empty text="No documents are waiting for a person to check them." />}
              {data.review_queue.map((o) => (
                <OrderCard key={o.order_id} order={o} token={token} onDone={load} mode="review" onOpen={setOpenLead} />
              ))}
              {data.awaiting_customer.length > 0 && (
                <Block title="Waiting on the customer" hint="Order created, documents not yet accepted" icon={ListChecks} tone="slate">
                  {data.awaiting_customer.map((o) => (
                    <OrderCard key={o.order_id} order={o} token={token} onDone={load} mode="waiting" onOpen={setOpenLead} />
                  ))}
                </Block>
              )}
            </div>
          )}

          {data && view === "fulfilment" && (
            <div className="space-y-4">
              {data.fulfilment.length === 0 && <Empty text="No orders are being set up right now." />}
              {data.fulfilment.map((o) => (
                <OrderCard key={o.order_id} order={o} token={token} onDone={load} mode="fulfilment" onOpen={setOpenLead} />
              ))}
            </div>
          )}

          {view === "orders" && <OrdersView token={token} onOpenLead={setOpenLead} />}
          {view === "kyc" && <KycSamplesView token={token} />}
          {view === "desk" && <ReviewDesk token={token} />}
          {view === "privacy" && <PrivacyView token={token} />}

          {view === "pipeline" && (
            <div className="rounded-card bg-white shadow-soft">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line-100 px-5 py-4">
                <div>
                  <h2 className="text-[16px] font-semibold text-ink-900">All leads</h2>
                  <p className="text-[12px] text-ink-500">
                    Showing {(table?.leads.length ?? 0).toLocaleString("en-IN")} of {(table?.matched ?? 0).toLocaleString("en-IN")}, sorted by chance to
                    activate. Search by name, city, type or lead ID, and click any lead to see and change its status.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {[
                    ["open", "Open"],
                    ["won", "Won"],
                    ["lost", "Lost"],
                    ["all", "All"],
                  ].map(([v, l]) => (
                    <button
                      key={v}
                      onClick={() => setLeadStatus(v)}
                      className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${leadStatus === v ? "bg-ink-900 text-white" : "text-ink-700 ring-1 ring-line-200"}`}
                    >
                      {l}
                    </button>
                  ))}
                  <button
                    onClick={() => setLiveOnly((v) => !v)}
                    aria-pressed={liveOnly}
                    className={`rounded-full px-3.5 py-1.5 text-[13px] font-semibold transition-colors ${liveOnly ? "bg-brand-600 text-white" : "text-ink-700 ring-1 ring-line-200"}`}
                  >
                    Only from the app
                  </button>
                </div>
              </div>
              <div className={`overflow-x-auto transition-opacity ${tableBusy ? "opacity-50" : ""}`} aria-busy={tableBusy}>
                <table className="w-full min-w-[860px] text-[13px]">
                  <thead>
                    <tr className="bg-surface-50 text-left text-[12px] font-semibold text-ink-500">
                      <th className="px-5 py-3">Business</th>
                      <th className="px-3 py-3">Type · city</th>
                      <th className="px-3 py-3">Stage</th>
                      <th className="px-3 py-3">Chance to activate</th>
                      <th className="px-3 py-3">Bundle</th>
                      <th className="px-5 py-3 text-right">Next action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(table?.leads ?? []).map((l) => (
                      <LeadRow key={l.lead_id} lead={l} token={token} onDone={loadTable} onOpen={setOpenLead} />
                    ))}
                  </tbody>
                </table>
                {table && table.leads.length === 0 && !tableBusy && <div className="p-8 text-center text-[14px] text-ink-500">No leads match.</div>}
                {!table && <div className="skeleton m-5 h-40 rounded-card" />}
              </div>
            </div>
          )}
        </main>
      </div>
      {openLead && <LeadDrawer leadId={openLead} token={token} onClose={() => setOpenLead(null)} onChanged={() => (load(), loadTable())} />}
    </div>
    </RoleContext.Provider>
  );
}

function PrivacyView({ token }: { token: string }) {
  const [r, setR] = useState<Record<string, string | number> | null>(null);
  useEffect(() => {
    api.storage(token).then(setR).catch(() => setR(null));
  }, [token]);
  const tiles: [string, string, string][] = [
    ["Database", "SQLite on disk", "services/core/data/udyam.db"],
    ["Document photos", "Not stored", `Only review cases, encrypted, max ${r?.vault_max_days ?? 30} days · ${r?.orders_with_documents_held ?? 0} held now`],
    ["KYC record", `${r?.record_retention_days ?? 180} days`, "Masked fields, verdict and audit trail"],
    ["Consents", `${r?.consents ?? "–"} recorded`, `${r?.consents_withdrawn ?? 0} withdrawn`],
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map(([k, v, sub]) => (
        <div key={k} className="rounded-card bg-white p-5 shadow-soft">
          <div className="text-[12px] font-semibold text-ink-500">{k}</div>
          <div className="mt-1 text-[18px] font-bold text-ink-900">{v}</div>
          <div className="mt-1 text-[12px] leading-snug text-ink-500">{sub}</div>
        </div>
      ))}
    </div>
  );
}

function Kpi({
  icon,
  tone,
  label,
  value,
  highlight,
  onClick,
}: {
  icon: LucideIcon;
  tone: Tone;
  label: string;
  value?: number;
  highlight?: boolean;
  onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      className={`press rounded-card bg-white p-5 text-left shadow-soft ${highlight ? "ring-2 ring-warning-600/40" : ""} ${onClick ? "cursor-pointer" : ""}`}
    >
      <IconTile icon={icon} tone={tone} size={40} />
      <div className="mt-4 text-[28px] font-bold leading-none tabular-nums text-ink-900">
        {value == null ? <span className="skeleton inline-block h-7 w-14 rounded-md" /> : <CountUp value={value} format={(v) => Math.round(v).toLocaleString("en-IN")} />}
      </div>
      <div className="mt-1.5 text-[13px] font-medium text-ink-500">{label}</div>
    </Tag>
  );
}

function Block({
  title,
  hint,
  right,
  icon,
  tone,
  children,
}: {
  title: string;
  hint?: string;
  right?: React.ReactNode;
  icon: LucideIcon;
  tone: Tone;
  children: React.ReactNode;
}) {
  return (
    <section className="enter rounded-card bg-white p-5 shadow-soft">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <IconTile icon={icon} tone={tone} size={36} />
          <div>
            <h2 className="text-[16px] font-semibold text-ink-900">{title}</h2>
            {hint && <p className="text-[12px] text-ink-500">{hint}</p>}
          </div>
        </div>
        {right}
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="rounded-2xl bg-surface-50 p-6 text-center text-[14px] text-ink-500">{text}</p>;
}

function Explainer({ card }: { card?: ModelCard }) {
  if (!card) return null;
  const pc = (x: number) => `${Math.round(x * 1000) / 10}%`;
  return (
    <div className="fade-in space-y-3 rounded-2xl bg-surface-50 p-4 text-[13px] leading-relaxed text-ink-700">
      <p>
        <b>Chance to activate = odds that leads at this stage activated × how this lead compares with the average lead.</b> The comparison comes from a{" "}
        {card.model.toLowerCase()} trained on all {card.rows.toLocaleString("en-IN")} leads in {card.trained_on} ({card.activated} activated). Checked on leads it had
        not seen: AUC {card.auc_held_out}, and the top 10% of scores activate {card.lift_top_decile}× as often as average. Hover any percentage to see that lead&apos;s
        working.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="mb-1 text-[12px] font-semibold text-ink-500">Base rate by stage (from the data)</div>
          {Object.entries(card.stage_rates)
            .filter(([s]) => s !== "KYC review")
            .map(([s, r]) => (
              <div key={s} className="flex justify-between">
                <span>{s}</span>
                <span className="font-semibold tabular-nums text-ink-900">{pc(r)}</span>
              </div>
            ))}
          <div className="mt-1 text-[12px] text-ink-500">
            With a GSTIN {pc(card.gstin_activation.with)} activate, without {pc(card.gstin_activation.without)}.
          </div>
        </div>
        <div>
          <div className="mb-1 text-[12px] font-semibold text-ink-500">What moves the odds most (10th to 90th percentile)</div>
          {card.weights.map((w) => (
            <div key={w.feature} className="flex justify-between">
              <span>{w.feature}</span>
              <span className="font-semibold tabular-nums text-ink-900">up to +{w.odds_swing_pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Likelihood({ value, lead }: { value: number; lead: AdminLead }) {
  return <ScoreTip value={value} score={lead.score} setup={lead.setup} />;
}

function useLeadAction(lead: AdminLead, token: string, onDone: () => void) {
  const [busy, setBusy] = useState(false);
  async function act() {
    if (!lead.action) return;
    setBusy(true);
    try {
      await api.adminAction(token, lead.lead_id, lead.action.id);
      onDone();
    } finally {
      setBusy(false);
    }
  }
  return { busy, act };
}

function LeadAction({ lead, busy, act }: { lead: AdminLead; busy: boolean; act: () => void }) {
  if (lead.action_done)
    return (
      <Chip tone="success" icon={CheckCircle2}>
        {lead.action_done.text}
      </Chip>
    );
  if (!lead.action) return null;
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        act();
      }}
      disabled={busy}
      className="press h-9 rounded-xl bg-brand-600 px-4 text-[13px] font-semibold text-white disabled:opacity-40"
    >
      {lead.action.label}
    </button>
  );
}

function LeadDetail({ lead }: { lead: AdminLead }) {
  const b = lead.bundle;
  return (
    <>
      {lead.drop_reason && <p className="mt-3 text-[13px] text-ink-700">Stalled because: {lead.drop_reason}</p>}
      {lead.signals.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {lead.signals.map((s, i) => (
            <Chip key={i} tone={SIGNAL[s.tone] ?? "success"}>
              {s.text}
            </Chip>
          ))}
        </div>
      )}
      {b && (
        <div className="mt-3 rounded-2xl bg-surface-50 p-3.5 text-[13px]">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-semibold text-ink-900">{b.name}</span>
            <span className="tabular-nums text-ink-700">
              {rupees(b.monthly_ex)}/month + GST <span className="text-ink-400">({rupees(b.monthly_incl)} with GST)</span>
            </span>
          </div>
          <ul className="mt-2 space-y-1">
            {b.lines.map((l, i) => (
              <li key={i} className="flex justify-between gap-3 text-ink-700">
                <span>
                  {l.label}
                  {l.qty > 1 ? ` ×${l.qty}` : ""} <span className="text-ink-400">{l.spec}</span>
                </span>
                <span className="tabular-nums">{rupees(l.monthly)}</span>
              </li>
            ))}
            {(b.dropped ?? []).map((l, i) => (
              <li key={"d" + i} className="flex justify-between gap-3 text-danger-600">
                <span className="line-through">{l.label}</span>
                <span className="text-[12px]">dropped by customer, {rupees(l.monthly)}/month</span>
              </li>
            ))}
          </ul>
          {(b.added ?? []).length > 0 && <div className="mt-1.5 text-success-600">Added by customer: {(b.added ?? []).join(", ")}</div>}
          <div className="mt-1.5 text-ink-500">
            {rupees(b.setup)} one-time setup · {b.contract} month contract
          </div>
        </div>
      )}
    </>
  );
}

function LeadCard({ lead, token, onDone, onOpen }: { lead: AdminLead; token: string; onDone: () => void; onOpen: (id: string) => void }) {
  const { busy, act } = useLeadAction(lead, token, onDone);
  return (
    <article className="rounded-2xl p-4 ring-1 ring-line-200 transition-shadow hover:shadow-soft">
      <div className="flex items-start gap-3">
        <Avatar name={lead.business} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => onOpen(lead.lead_id)} className="truncate text-left text-[15px] font-semibold text-ink-900 hover:text-brand-600">
              {lead.business}
            </button>
            {lead.live && <Chip tone="brand">From the app</Chip>}
            <Chip>{lead.stage}</Chip>
          </div>
          <div className="mt-0.5 text-[13px] text-ink-500">
            {lead.business_type} · {lead.city || "City not shared"} · {lead.language} · {lead.source}
          </div>
        </div>
        <Likelihood value={lead.likelihood} lead={lead} />
      </div>
      <LeadDetail lead={lead} />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[12px] text-ink-500">
          {lead.partner ? `${lead.partner.kind}: ${lead.partner.name}, ${lead.partner.phone}` : lead.contact ? `Contact: ${lead.contact}` : ""}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {lead.status !== "won" && <QuickActions lead={lead} token={token} onDone={onDone} />}
          {(lead.action_done || lead.action?.id !== "whatsapp_quote") && <LeadAction lead={lead} busy={busy} act={act} />}
        </div>
      </div>
    </article>
  );
}

function LeadRow({ lead, token, onDone, onOpen }: { lead: AdminLead; token: string; onDone: () => void; onOpen: (id: string) => void }) {
  const { busy, act } = useLeadAction(lead, token, onDone);
  return (
    <>
      <tr onClick={() => onOpen(lead.lead_id)} className="cursor-pointer border-t border-line-100 hover:bg-surface-50">
        <td className="px-5 py-3">
          <div className="flex items-center gap-3">
            <Avatar name={lead.business} size={36} />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 font-semibold text-ink-900">
                {lead.business}
                <span className="text-[11px] font-medium text-ink-400">{lead.lead_id}</span>
              </div>
              {lead.live && <span className="text-[12px] font-semibold text-brand-600">From the app</span>}
            </div>
          </div>
        </td>
        <td className="px-3 py-3 text-ink-700">
          {lead.business_type}
          <div className="text-[12px] text-ink-400">{lead.city || "—"}</div>
        </td>
        <td className="px-3 py-3">
          <Chip>{lead.stage}</Chip>
        </td>
        <td className="px-3 py-3">
          <Likelihood value={lead.likelihood} lead={lead} />
        </td>
        <td className="px-3 py-3 tabular-nums text-ink-700">{lead.bundle ? `${rupees(lead.bundle.monthly_ex)}/mo` : "—"}</td>
        <td className="px-5 py-3 text-right">
          <LeadAction lead={lead} busy={busy} act={act} />
        </td>
      </tr>
    </>
  );
}

function OrderCard({ order, token, onDone, mode, onOpen }: { order: AdminOrder; token: string; onDone: () => void; mode: "review" | "fulfilment" | "waiting"; onOpen: (id: string) => void }) {
  const [busy, setBusy] = useState(false);
  const st = STATUS[order.status] ?? STATUS.awaiting_kyc;

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      onDone();
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="enter rounded-card bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <Avatar name={order.business ?? "Customer"} size={44} />
          <div>
            <button onClick={() => onOpen(order.lead_id)} className="text-left text-[16px] font-semibold text-ink-900 hover:text-brand-600">
              {order.business ?? "Customer"}
            </button>
            <div className="text-[13px] text-ink-500">
              {order.order_id} · {order.city || "—"} · {order.bundle_name} · {rupees(order.tax.monthly_incl_gst)}/month with GST · {ago(order.updated_at)}
            </div>
          </div>
        </div>
        <Chip tone={st.tone}>{st.text}</Chip>
      </div>

      {mode === "review" && order.kyc && (
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div>
            <div className="text-[13px] font-semibold text-ink-500">Why it needs a person</div>
            <ul className="mt-2 space-y-2 text-[13px]">
              {(order.kyc.raw_findings ?? []).map((f, i) => (
                <li key={i} className="flex gap-2">
                  <span
                    className={`h-fit shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold ${
                      f.severity === "HARD" ? "bg-danger-50 text-danger-600" : f.severity === "REVIEW" ? "bg-warning-50 text-warning-600" : "bg-line-100 text-ink-500"
                    }`}
                  >
                    {f.code}
                  </span>
                  <span className="text-ink-700">{f.message}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-[13px] font-semibold text-ink-500">Checks</div>
            <ul className="mt-2 space-y-1.5 text-[13px]">
              {(order.kyc.checklist ?? []).map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-ink-700">
                  {c.state === "ok" ? (
                    <CheckCircle2 size={15} className="text-success-600" />
                  ) : c.state === "check" ? (
                    <Eye size={15} className="text-warning-600" />
                  ) : (
                    <XCircle size={15} className="text-danger-600" />
                  )}
                  {c.label}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-[12px] text-ink-500">Documents and personal details are visible only to the verification desk.</p>
          </div>
        </div>
      )}

      {mode !== "review" && (
        <ul className="mt-4 divide-y divide-line-100">
          {order.lines.map((l) => (
            <li key={l.product_id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-[13px]">
              <div>
                <div className="font-semibold text-ink-900">
                  {l.label}
                  {l.qty > 1 ? ` ×${l.qty}` : ""} <span className="font-normal text-ink-400">{l.spec}</span>
                </div>
                <div className="text-ink-500">
                  {l.kind === "field" ? "Engineer visit" : "Remote activation"} · {l.status_text}
                </div>
              </div>
              {mode === "fulfilment" && l.state !== "live" && l.state !== "queued" && (
                <button
                  disabled={busy}
                  onClick={() => run(() => api.adminAdvance(token, order.order_id, l.product_id))}
                  className="press h-9 rounded-xl bg-ink-900 px-3.5 text-[12px] font-semibold text-white disabled:opacity-40"
                >
                  {l.state === "scheduled" ? "Engineer started" : "Mark live"}
                </button>
              )}
              {l.state === "live" && (
                <Chip tone="success" icon={CheckCircle2}>
                  Live
                </Chip>
              )}
            </li>
          ))}
        </ul>
      )}

      <OrderControls order={order} token={token} onDone={onDone} />

      {order.engineer && mode === "fulfilment" && (
        <div className="mt-2 text-[12px] text-ink-500">
          {order.engineer.role}: {order.engineer.name}, {order.engineer.phone}, {order.engineer.city}
        </div>
      )}
    </article>
  );
}
