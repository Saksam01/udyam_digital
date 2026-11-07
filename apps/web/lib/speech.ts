export function sttSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return !!(w.webkitSpeechRecognition || w.SpeechRecognition);
}

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string, locale: string, onEnd?: () => void): void {
  if (!ttsSupported()) {
    onEnd?.();
    return;
  }
  try {
    const u = new SpeechSynthesisUtterance(text);
    u.lang = locale;
    const base = locale.split("-")[0];
    const voices = window.speechSynthesis.getVoices();
    const v = voices.find((x) => x.lang === locale) || voices.find((x) => x.lang.startsWith(base));
    if (v) u.voice = v;
    if (onEnd) {
      u.onend = () => onEnd();
      u.onerror = () => onEnd();
    }
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  } catch {
    onEnd?.();
  }
}

export function stopSpeaking(): void {
  if (ttsSupported()) {
    try {
      window.speechSynthesis.cancel();
    } catch {
      /* ignore */
    }
  }
}

export function listenOnce(locale: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const w = window as unknown as Record<string, any>;
    const SR = w.webkitSpeechRecognition || w.SpeechRecognition;
    if (!SR) {
      reject(new Error("speech recognition not supported"));
      return;
    }
    const r = new SR();
    r.lang = locale;
    r.interimResults = false;
    r.maxAlternatives = 1;
    let done = false;
    r.onresult = (e: any) => {
      done = true;
      resolve(String(e.results[0][0].transcript || "").trim());
    };
    r.onerror = (e: any) => reject(new Error(e.error || "speech error"));
    r.onend = () => {
      if (!done) reject(new Error("no-speech"));
    };
    try {
      r.start();
    } catch (e) {
      reject(e as Error);
    }
  });
}
