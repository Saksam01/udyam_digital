// Sarvam voice via the backend, with a browser-voice fallback.
import { API_BASE } from "./api";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface ListenResult {
  transcript: string;
  heardSpeech: boolean; // false when the mic picked up only silence/noise
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

// Probe TTS with a tiny phrase. Returns null when it works, else a short error string.
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

export async function sarvamSpeak(text: string, locale: string, onEnd?: () => void): Promise<void> {
  try {
    const r = await fetch(`${API_BASE}/api/v1/voice/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: locale }),
    });
    if (!r.ok) throw new Error("tts");
    const j = await r.json();
    const audio = new Audio(`data:${j.mime};base64,${j.audio_base64}`);
    audio.onended = () => onEnd?.();
    audio.onerror = () => onEnd?.();
    await audio.play();
  } catch {
    onEnd?.();
  }
}

// Listen for an answer. We watch the mic level: wait for speech to start, record until the
// speaker goes quiet, and report heardSpeech=false if nobody said anything, so the caller can
// drop back to text instead of looping on silence.
export async function sarvamListen(locale: string): Promise<ListenResult> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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

  const STEP = 50;          // ms between level checks
  const ONSET_WAIT = 5000;  // ms to wait for the person to start talking
  const END_SILENCE = 900;  // ms of quiet that ends the answer
  const MAX_UTTERANCE = 9000;

  // Calibrate the room for ~300ms, then set the speech threshold above it.
  let ambient = 0, n = 0;
  const calEnd = performance.now() + 300;
  while (performance.now() < calEnd) {
    ambient += level();
    n++;
    await sleep(STEP);
  }
  const threshold = Math.max(0.015, (n ? ambient / n : 0.01) * 2.5);

  let heardSpeech = false;
  const waitStart = performance.now();
  while (performance.now() - waitStart < ONSET_WAIT) {
    if (level() > threshold) {
      heardSpeech = true;
      break;
    }
    await sleep(STEP);
  }

  if (heardSpeech) {
    const uttStart = performance.now();
    let lastLoud = uttStart;
    while (performance.now() - uttStart < MAX_UTTERANCE) {
      if (level() > threshold) lastLoud = performance.now();
      else if (performance.now() - lastLoud > END_SILENCE) break;
      await sleep(STEP);
    }
  }

  rec.stop();
  await stopped;
  stream.getTracks().forEach((t) => t.stop());
  ctx.close().catch(() => {});

  if (!heardSpeech) return { transcript: "", heardSpeech: false };

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
  return { transcript: ((j.transcript as string) || "").trim(), heardSpeech: true };
}

// Decode whatever the browser recorded, resample to 16 kHz mono, and encode as 16-bit WAV.
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
