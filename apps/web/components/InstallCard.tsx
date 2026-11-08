"use client";
import { useEffect, useState } from "react";
import { Download, Share } from "lucide-react";
import { Lang, t } from "@/lib/i18n";
import { Card, IconTile, btn } from "./ui";

type PromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

export default function InstallCard({ lang }: { lang: Lang }) {
  const [prompt, setPrompt] = useState<PromptEvent | null>(null);
  const [ios, setIos] = useState(false);
  const [installed, setInstalled] = useState(true);

  useEffect(() => {
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
    setInstalled(standalone);
    setIos(/iphone|ipad|ipod/i.test(navigator.userAgent));
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setPrompt(e as PromptEvent);
    };
    const onInstalled = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed || (!prompt && !ios)) return null;

  return (
    <Card className="flex items-center gap-3 p-4">
      <IconTile icon={ios ? Share : Download} tone="red" size={44} />
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-bold text-ink-900">{t(lang, "install_title")}</div>
        <div className="text-[13px] leading-snug text-ink-500">{ios ? t(lang, "install_ios") : t(lang, "install_sub")}</div>
      </div>
      {prompt && (
        <button
          onClick={async () => {
            await prompt.prompt();
            await prompt.userChoice.catch(() => null);
            setPrompt(null);
          }}
          className={`${btn.primary} h-10 shrink-0 px-4`}
        >
          {t(lang, "install_btn")}
        </button>
      )}
    </Card>
  );
}
