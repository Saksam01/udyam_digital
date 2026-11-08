from __future__ import annotations
import base64
import hashlib
import io
import os
import re
import tempfile
import threading
import wave
from concurrent.futures import ThreadPoolExecutor

TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5")
SPEAKER = os.getenv("SARVAM_SPEAKER", "anushka")

SPEAKER_FALLBACKS = ["anushka", "manisha", "vidya", "shubh", "abhilash", "karun", "hitesh"]

TTS_CHAR_LIMIT = 450

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.normpath(os.path.join(HERE, "..", "data", "tts_cache"))


def _key() -> str | None:
    return os.getenv("SARVAM_API_KEY") or None


def _sdk_ok() -> bool:
    try:
        import sarvamai
        return True
    except Exception:
        return False


def enabled() -> bool:
    return bool(_key()) and _sdk_ok()


def status() -> dict:
    return {"enabled": enabled(), "has_key": bool(_key()), "sdk_installed": _sdk_ok(),
            "tts_model": TTS_MODEL, "stt_model": STT_MODEL, "speaker": SPEAKER}


_client_obj = None
_good_speaker: str | None = None
_mem: dict[str, bytes] = {}
_pool = ThreadPoolExecutor(max_workers=6)
_lock = threading.Lock()


def _client():
    global _client_obj
    if _client_obj is None:
        from sarvamai import SarvamAI
        _client_obj = SarvamAI(api_subscription_key=_key())
    return _client_obj


def _split(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= TTS_CHAR_LIMIT:
        return [text]
    out, cur = [], ""
    for sentence in re.split(r"(?<=[।.!?])\s+", text):
        if len(cur) + len(sentence) + 1 <= TTS_CHAR_LIMIT:
            cur = f"{cur} {sentence}".strip()
        else:
            if cur:
                out.append(cur)
            if len(sentence) <= TTS_CHAR_LIMIT:
                cur = sentence
            else:
                out += [sentence[i:i + TTS_CHAR_LIMIT] for i in range(0, len(sentence), TTS_CHAR_LIMIT)]
                cur = ""
    if cur:
        out.append(cur)
    return out or [text[:TTS_CHAR_LIMIT]]


def _convert(client, text: str, lang_code: str):
    global _good_speaker
    first = _good_speaker or SPEAKER
    speakers: list[str | None] = [first] + [s for s in [SPEAKER] + SPEAKER_FALLBACKS if s != first] + [None]
    last = None
    for sp in speakers:
        kw: dict = {"text": text, "language_code": lang_code, "model": TTS_MODEL}
        if sp:
            kw["speaker"] = sp
        try:
            resp = client.text_to_speech.convert(**kw)
        except TypeError:
            kw["target_language_code"] = kw.pop("language_code")
            try:
                resp = client.text_to_speech.convert(**kw)
            except Exception as e:
                last = e
                continue
        except Exception as e:
            last = e
            continue
        _good_speaker = sp
        return resp
    raise last


def _stitch(wavs: list[bytes]) -> bytes:
    if len(wavs) == 1:
        return wavs[0]
    params, frames = None, b""
    for w in wavs:
        with wave.open(io.BytesIO(w), "rb") as r:
            if params is None:
                params = r.getparams()
            frames += r.readframes(r.getnframes())
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(frames)
    return buf.getvalue()


def _key_for(text: str, lang_code: str) -> str:
    return hashlib.sha256(f"{TTS_MODEL}|{SPEAKER}|{lang_code}|{text}".encode()).hexdigest()[:24]


def _one(client, chunk: str, lang_code: str) -> bytes:
    resp = _convert(client, chunk, lang_code)
    audios = getattr(resp, "audios", None)
    if not audios:
        raise RuntimeError("Sarvam TTS returned no audio")
    return base64.b64decode(audios[0])


_inflight: dict[str, threading.Event] = {}


def tts(text: str, lang_code: str) -> bytes:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("no text to speak")
    h = _key_for(text, lang_code)
    with _lock:
        hit = _mem.get(h)
        waiter = _inflight.get(h) if not hit else None
        if not hit and not waiter:
            _inflight[h] = threading.Event()
    if hit:
        return hit
    if waiter:
        waiter.wait(timeout=30)
        with _lock:
            hit = _mem.get(h)
        if hit:
            return hit
        return tts(text, lang_code)
    try:
        return _synthesise(text, lang_code, h)
    finally:
        with _lock:
            ev = _inflight.pop(h, None)
        if ev:
            ev.set()


def _synthesise(text: str, lang_code: str, h: str) -> bytes:
    path = os.path.join(CACHE_DIR, f"{h}.wav")
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
    else:
        os.makedirs(CACHE_DIR, exist_ok=True)
        client = _client()
        chunks = _split(text)
        if len(chunks) == 1:
            parts = [_one(client, chunks[0], lang_code)]
        else:
            parts = list(_pool.map(lambda c: _one(client, c, lang_code), chunks))
        data = _stitch(parts)
        with open(path, "wb") as f:
            f.write(data)
    with _lock:
        if len(_mem) > 200:
            _mem.pop(next(iter(_mem)))
        _mem[h] = data
    return data


def warm(items: list[tuple[str, str]]) -> None:
    def run(text: str, lang: str):
        try:
            tts(text, lang)
        except Exception:
            pass
    for text, lang in items[:12]:
        _pool.submit(run, text, lang)


def stt(audio_bytes: bytes, filename: str = "audio.wav", lang_code: str = "unknown") -> str:
    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tf.write(audio_bytes)
        tmp = tf.name
    try:
        client = _client()
        with open(tmp, "rb") as fh:
            try:
                resp = client.speech_to_text.transcribe(file=fh, model=STT_MODEL, language_code=lang_code)
            except TypeError:
                fh.seek(0)
                resp = client.speech_to_text.transcribe(file=fh, model=STT_MODEL)
        return getattr(resp, "transcript", "") or ""
    finally:
        os.unlink(tmp)
