"use client";
import { Globe } from "lucide-react";
import { Lang, LANGS } from "@/lib/i18n";

export default function LangPill({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  const current = LANGS.find((l) => l.code === lang)?.label ?? "English";
  return (
    <label className="press relative flex h-10 items-center gap-1.5 rounded-full bg-white/15 px-3 text-[13px] font-semibold text-white">
      <Globe size={16} strokeWidth={2} aria-hidden="true" />
      <span>{current}</span>
      <select
        value={lang}
        onChange={(e) => setLang(e.target.value as Lang)}
        aria-label="Language"
        className="absolute inset-0 cursor-pointer opacity-0"
      >
        {LANGS.map((l) => (
          <option key={l.code} value={l.code}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  );
}
