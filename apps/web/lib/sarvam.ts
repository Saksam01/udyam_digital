import { API_BASE } from "./api";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface ListenResult {
  transcript: string;
  heardSpeech: boolean;
}

export async function sarvamOn(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/voice/status`);
    const j = await r.json();
    return !!j.enabled;
  } catch {
    return false;
  }
}

export async function sarvamTtsError(locale: string): Promise<string | null> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "परीक्षण", lang: locale }),
    });
    if (!r.ok) {
      let detail = "";
      try {
        detail = (await r.json()).detail ?? "";
      } catch {
        /* ignore */
      }
      return `${r.status} ${detail}`.trim();
    }
    return null;
  } catch (e) {
    return e instanceof Error ? e.message : String(e);
  }
}

function chunkText(text: string): string[] {
  const sentences = text.split(/(?<=[।.!?])\s+/).filter(Boolean);
  const out: string[] = [];
  let cur = "";
  for (const s of sentences) {
    const limit = out.length === 0 ? 90 : 220;
    if (cur && (cur + " " + s).length > limit) {
      out.push(cur);
      cur = s;
    } else {
      cur = cur ? `${cur} ${s}` : s;
    }
  }
  if (cur) out.push(cur);
  return out.length ? out : [text];
}

const clips = new Map<string, Promise<string>>();
let current: HTMLAudioElement | null = null;
let playToken = 0;

function clip(text: string, locale: string): Promise<string> {
  const key = `${locale}|${text}`;
  const hit = clips.get(key);
  if (hit) return hit;
  const p = (async () => {
    const r = await fetch(`${API_BASE}/api/v1/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: locale }),
    });
    if (!r.ok) throw new Error("tts");
    const j = await r.json();
    const bin = atob(j.audio_base64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return URL.createObjectURL(new Blob([bytes], { type: j.mime || "audio/wav" }));
  })();
  p.catch(() => clips.delete(key));
  clips.set(key, p);
  return p;
}

function play(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const a = new Audio(url);
    current = a;
    a.onended = () => resolve();
    a.onerror = () => reject(new Error("playback"));
    a.play().catch(reject);
  });
}

export function stopSarvam(): void {
  playToken++;
  if (current) {
    current.pause();
    current = null;
  }
}

export function sarvamWarm(texts: string[], locale: string): void {
  const flat = texts.flatMap(chunkText);
  flat.forEach((c) => clip(c, locale).catch(() => {}));
}

export async function sarvamSpeak(text: string, locale: string, onEnd?: () => void): Promise<boolean> {
  stopSarvam();
  const token = ++playToken;
  const parts = chunkText(text).map((c) => clip(c, locale));
  let played = false;
  try {
    for (const p of parts) {
      const url = await p;
      if (token !== playToken) return true;
      await play(url);
      played = true;
    }
  } catch {
    if (!played) return false;
  }
  if (token === playToken) onEnd?.();
  return true;
}

let mic: MediaStream | null = null;
let listenToken = 0;

export function cancelListen(): void {
  listenToken++;
}
let micTimer: ReturnType<typeof setTimeout> | null = null;

async function openMic(): Promise<MediaStream> {
  if (micTimer) clearTimeout(micTimer);
  if (!mic || !mic.active) {
    mic = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  }
  return mic;
}

export function releaseMic(): void {
  if (micTimer) clearTimeout(micTimer);
  mic?.getTracks().forEach((t) => t.stop());
  mic = null;
}

export async function sarvamListen(locale: string): Promise<ListenResult> {
  stopSarvam();
  const my = ++listenToken;
  const live = () => my === listenToken;
  const stream = await openMic();
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new AudioCtx();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const frame = new Float32Array(analyser.fftSize);
  const level = () => {
    analyser.getFloatTimeDomainData(frame);
    let sum = 0;
    for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
    return Math.sqrt(sum / frame.length);
  };

  const rec = new MediaRecorder(stream);
  const chunks: BlobPart[] = [];
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  const stopped = new Promise<void>((res) => {
    rec.onstop = () => res();
  });
  rec.start();

  const STEP = 50;
  const ONSET_WAIT = 6000;
  const END_SILENCE = 500;
  const MAX_UTTERANCE = 9000;

  let ambient = 0, n = 0;
  const calEnd = performance.now() + 150;
  while (performance.now() < calEnd) {
    ambient += level();
    n++;
    await sleep(STEP);
  }
  const threshold = Math.max(0.015, (n ? ambient / n : 0.01) * 2.5);

  let heardSpeech = false;
  const waitStart = performance.now();
  while (live() && performance.now() - waitStart < ONSET_WAIT) {
    if (level() > threshold) {
      heardSpeech = true;
      break;
    }
    await sleep(STEP);
  }

  if (heardSpeech) {
    const uttStart = performance.now();
    let lastLoud = uttStart;
    while (live() && performance.now() - uttStart < MAX_UTTERANCE) {
      if (level() > threshold) lastLoud = performance.now();
      else if (performance.now() - lastLoud > END_SILENCE) break;
      await sleep(STEP);
    }
  }

  rec.stop();
  await stopped;
  ctx.close().catch(() => {});
  micTimer = setTimeout(releaseMic, 30000);

  if (!heardSpeech || !live()) return { transcript: "", heardSpeech: false };

  const recorded = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
  const wav = await toWav(recorded);
  const fd = new FormData();
  fd.append("audio", wav, "answer.wav");
  fd.append("lang", locale);
  const r = await fetch(`${API_BASE}/api/v1/voice/stt`, { method: "POST", body: fd });
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json()).detail ?? "";
    } catch {
      /* ignore */
    }
    throw new Error(`STT ${r.status} ${detail}`);
  }
  const j = await r.json();
  if (!live()) return { transcript: "", heardSpeech: false };
  return { transcript: ((j.transcript as string) || "").trim(), heardSpeech: true };
}

async function toWav(blob: Blob): Promise<Blob> {
  const buf = await blob.arrayBuffer();
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const tmp = new Ctx();
  const decoded = await tmp.decodeAudioData(buf);
  tmp.close();

  const targetRate = 16000;
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * targetRate)), targetRate);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination);
  src.start();
  const rendered = await off.startRendering();
  const data = rendered.getChannelData(0);

  const out = new ArrayBuffer(44 + data.length * 2);
  const view = new DataView(out);
  const str = (o: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i));
  };
  str(0, "RIFF");
  view.setUint32(4, 36 + data.length * 2, true);
  str(8, "WAVE");
  str(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  str(36, "data");
  view.setUint32(40, data.length * 2, true);
  let pos = 44;
  for (let i = 0; i < data.length; i++) {
    const s = Math.max(-1, Math.min(1, data[i]));
    view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    pos += 2;
  }
  return new Blob([out], { type: "audio/wav" });
}
