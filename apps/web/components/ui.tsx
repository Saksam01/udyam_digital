"use client";
import { useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Cloud,
  MonitorSmartphone,
  Package,
  Phone,
  Router,
  ShieldCheck,
  Smartphone,
  Wifi,
  MessageCircle,
} from "lucide-react";

export type Tone = "red" | "blue" | "green" | "teal" | "amber" | "slate";

export const TONE: Record<Tone, { tile: string; icon: string; tint: string; ring: string; solid: string }> = {
  red: { tile: "bg-brand-100/70", icon: "text-brand-600", tint: "bg-brand-50", ring: "ring-brand-100", solid: "bg-brand-600" },
  blue: { tile: "bg-info-50", icon: "text-info-600", tint: "bg-info-50/70", ring: "ring-info-50", solid: "bg-info-600" },
  green: { tile: "bg-success-50", icon: "text-success-600", tint: "bg-success-50/70", ring: "ring-success-50", solid: "bg-success-600" },
  teal: { tile: "bg-aqua-50", icon: "text-aqua-600", tint: "bg-aqua-50/70", ring: "ring-aqua-50", solid: "bg-aqua-600" },
  amber: { tile: "bg-warning-50", icon: "text-warning-600", tint: "bg-warning-50/70", ring: "ring-warning-50", solid: "bg-warning-600" },
  slate: { tile: "bg-slate2-50", icon: "text-slate2-600", tint: "bg-slate2-50", ring: "ring-slate2-50", solid: "bg-slate2-600" },
};

export function IconTile({ icon: Icon, tone = "slate", size = 40, className = "" }: { icon: LucideIcon; tone?: Tone; size?: number; className?: string }) {
  const t = TONE[tone];
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center ${t.tile} ${t.icon} ${className}`}
      style={{ width: size, height: size, borderRadius: size >= 48 ? 16 : 12 }}
      aria-hidden="true"
    >
      <Icon size={Math.round(size * 0.5)} strokeWidth={1.9} />
    </span>
  );
}

export function productLook(category?: string, name?: string): { tone: Tone; icon: LucideIcon } {
  const s = `${category ?? ""} ${name ?? ""}`.toLowerCase();
  if (/cctv|camera|secur|firewall|antivirus|protect/.test(s)) return { tone: "green", icon: ShieldCheck };
  if (/cloud|backup|email|storage|microsoft|google|workspace|saas/.test(s)) return { tone: "teal", icon: Cloud };
  if (/\bsim\b|mobile|postpaid|4g|5g/.test(s)) return { tone: "blue", icon: Smartphone };
  if (/\bpos\b|payment|\bpay\b|billing|\bqr\b|soundbox/.test(s)) return { tone: "amber", icon: MonitorSmartphone };
  if (/voice|sip|pbx|phone|call|toll|number/.test(s)) return { tone: "blue", icon: Phone };
  if (/sms|whatsapp|messag/.test(s)) return { tone: "blue", icon: MessageCircle };
  if (/leased|ill|dedicated|sd-wan|mpls/.test(s)) return { tone: "red", icon: Router };
  if (/broadband|fiber|fibre|internet|wifi|wi-fi|connect/.test(s)) return { tone: "red", icon: Wifi };
  return { tone: "slate", icon: Package };
}

function useReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    setR(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  }, []);
  return r;
}

export function CountUp({ value, format, duration = 750 }: { value: number; format: (n: number) => string; duration?: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const from = useRef(0);
  useEffect(() => {
    if (reduce || !Number.isFinite(value)) {
      setShown(value);
      return;
    }
    const start = from.current;
    let raf = 0;
    let t0: number | null = null;
    const step = (ts: number) => {
      if (t0 === null) t0 = ts;
      const p = Math.min((ts - t0) / duration, 1);
      const e = 1 - Math.pow(1 - p, 3);
      setShown(p < 1 ? start + (value - start) * e : value);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    from.current = value;
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduce]);
  return <>{format(shown)}</>;
}

export const inr = (n: number, decimals = 0) =>
  "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
export const num = (x: string | number) => (typeof x === "string" ? parseFloat(x) : x);
export const hasPaise = (x: string | number) => !Number.isInteger(Math.round(num(x) * 100) / 100);

export function Money({ value, className = "" }: { value: string | number; className?: string }) {
  const n = num(value);
  const d = hasPaise(n) ? 2 : 0;
  return (
    <span className={`tabular-nums ${className}`}>
      <CountUp value={n} format={(v) => inr(v, d)} />
    </span>
  );
}

export function Ring({
  pct,
  size = 96,
  stroke = 8,
  color = "#ED1C24",
  track = "#F0F0F3",
  children,
}: {
  pct: number;
  size?: number;
  stroke?: number;
  color?: string;
  track?: string;
  children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const [p, setP] = useState(0);
  useEffect(() => {
    const h = requestAnimationFrame(() => setP(Math.max(0, Math.min(100, pct))));
    return () => cancelAnimationFrame(h);
  }, [pct]);
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c - (c * p) / 100}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.8,.2,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>
    </div>
  );
}

export function Segments({ labels, done, current }: { labels: string[]; done: number; current: number | null }) {
  return (
    <div>
      <div className="flex gap-1">
        {labels.map((l, i) => (
          <div key={l} className="h-1.5 flex-1 overflow-hidden rounded-full bg-line-100">
            {(i < done || i === current) && (
              <div className={`bar-in h-full rounded-full ${i < done ? "bg-success-600" : "bg-brand-500"}`} style={{ animationDelay: `${150 + i * 120}ms` }} />
            )}
          </div>
        ))}
      </div>
      <div className="mt-1.5 grid gap-1 text-[12px] font-semibold leading-tight" style={{ gridTemplateColumns: `repeat(${labels.length}, minmax(0, 1fr))` }}>
        {labels.map((l, i) => (
          <span key={l} className={i < done ? "text-success-600" : i === current ? "text-brand-600" : "text-ink-400"}>
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

export function LiveDot({ color = "bg-success-600" }: { color?: string }) {
  return (
    <span className="relative inline-flex h-2 w-2">
      <span className={`ping absolute inline-flex h-full w-full rounded-full ${color}`} />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  );
}

export type ChipTone = "success" | "warning" | "danger" | "info" | "neutral" | "brand";
const CHIP: Record<ChipTone, string> = {
  success: "bg-success-50 text-success-600",
  warning: "bg-warning-50 text-warning-600",
  danger: "bg-danger-50 text-danger-600",
  info: "bg-info-50 text-info-600",
  neutral: "bg-line-100 text-ink-700",
  brand: "bg-brand-50 text-brand-600",
};
export function Chip({ tone = "neutral", icon: Icon, children, className = "" }: { tone?: ChipTone; icon?: LucideIcon; children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] font-semibold leading-none ${CHIP[tone]} ${className}`}>
      {Icon && <Icon size={13} strokeWidth={2.2} aria-hidden="true" />}
      {children}
    </span>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-card bg-white shadow-soft ${className}`}>{children}</div>;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between px-1">
      <h2 className="text-[15px] font-semibold text-ink-900">{children}</h2>
      {right}
    </div>
  );
}

export { AccelMark } from "./Logo";

export function Hero({ children, overlap, tall = false }: { children: React.ReactNode; overlap?: React.ReactNode; tall?: boolean }) {
  return (
    <section className="relative">
      <div className={`hero-band absolute inset-x-0 top-0 rounded-b-hero ${overlap ? "bottom-16" : "bottom-0"}`} />
      <div className={`relative px-4 pt-4 text-white ${overlap ? "" : tall ? "pb-10" : "pb-6"}`}>{children}</div>
      {overlap && <div className="enter relative mt-5 px-4">{overlap}</div>}
    </section>
  );
}

export function HeroButton({ children, onClick, label }: { children: React.ReactNode; onClick?: () => void; label: string }) {
  return (
    <button onClick={onClick} aria-label={label} className="press flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white">
      {children}
    </button>
  );
}

function initials(name: string) {
  return name
    .split(" ")
    .map((x) => x[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function PersonCard({ label, name, sub, phone, callLabel }: { label: string; name: string; sub?: string; phone: string; callLabel: string }) {
  const tel = phone.replace(/[^\d+]/g, "");
  const wa = tel.replace(/^\+/, "");
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-info-50 text-[15px] font-bold text-info-600">{initials(name)}</span>
      <div className="min-w-0 flex-1">
        <div className="text-[12px] font-semibold text-ink-500">{label}</div>
        <div className="truncate text-[16px] font-semibold text-ink-900">{name}</div>
        {sub && <div className="truncate text-[13px] text-ink-500">{sub}</div>}
      </div>
      <a
        href={`https://wa.me/${wa}`}
        target="_blank"
        rel="noreferrer"
        aria-label="WhatsApp"
        className="press flex h-11 w-11 items-center justify-center rounded-full bg-success-50 text-success-600"
      >
        <MessageCircle size={20} strokeWidth={2} />
      </a>
      <a href={`tel:${tel}`} aria-label={callLabel} className="press flex h-11 items-center gap-1.5 rounded-full bg-brand-600 px-4 text-[14px] font-semibold text-white">
        <Phone size={16} strokeWidth={2.2} />
        {callLabel}
      </a>
    </div>
  );
}

export const btn = {
  primary:
    "press inline-flex min-h-[48px] items-center justify-center gap-2 rounded-btn bg-brand-600 px-5 py-2 text-center text-[15px] font-semibold leading-tight text-white disabled:opacity-40 disabled:active:scale-100",
  secondary:
    "press inline-flex min-h-[44px] items-center justify-center gap-2 rounded-btn bg-white px-4 py-2 text-center text-[14px] font-semibold leading-tight text-ink-900 ring-1 ring-line-200 disabled:opacity-40",
  dark: "press inline-flex min-h-[48px] items-center justify-center gap-2 rounded-btn bg-ink-900 px-5 py-2 text-center text-[15px] font-semibold leading-tight text-white disabled:opacity-40",
};
