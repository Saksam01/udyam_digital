
const GLYPH = (
  <>
    <path d="M6.5 24.5 V19.5" />
    <path d="M12 24.5 V13.5" />
    <path d="M17.5 24.5 V7.5 L25.5 24.5" />
  </>
);

export function AccelMark({ size = 36, variant = "light" }: { size?: number; variant?: "solid" | "light" }) {
  const solid = variant === "solid";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Accel Business" className="shrink-0">
      <rect width="32" height="32" rx="9" fill={solid ? "#E4141B" : "#FFFFFF"} />
      <g fill="none" stroke={solid ? "#FFFFFF" : "#E4141B"} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        {GLYPH}
      </g>
    </svg>
  );
}

export function AccelLogo({ size = 36, onDark = false, variant }: { size?: number; onDark?: boolean; variant?: "solid" | "light" }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <AccelMark size={size} variant={variant ?? (onDark ? "light" : "solid")} />
      <span className={`leading-none ${onDark ? "text-white" : "text-ink-900"}`}>
        <span className="block text-[17px] font-bold tracking-[-0.01em]">Accel</span>
        <span className={`mt-0.5 block text-[12px] font-medium tracking-[0.02em] ${onDark ? "text-white/75" : "text-ink-500"}`}>Business</span>
      </span>
    </span>
  );
}
