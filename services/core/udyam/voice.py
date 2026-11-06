"""Sarvam voice proxy; the API key stays on the server."""

from __future__ import annotations
import base64
import hashlib
import io
import os
import re
import tempfile
import wave

# Sarvam retired bulbul:v2; v3 is the current natural-voice model. Override via .env if needed.
TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saarika:v2.5")
SPEAKER = os.getenv("SARVAM_SPEAKER", "anushka")

# If the chosen speaker isn't valid for the model, fall through these before giving up.
SPEAKER_FALLBACKS = ["anushka", "manisha", "vidya", "shubh", "abhilash", "karun", "hitesh"]

# Sarvam caps a single TTS request; long replies are split and stitched back together.
TTS_CHAR_LIMIT = 450

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.normpath(os.path.join(HERE, "..", "data", "tts_cache"))


def _key() -> str | None:
    return os.getenv("SARVAM_API_KEY") or None


def _sdk_ok() -> bool:
    try:
        import sarvamai  # noqa: F401
        return True
    except Exception:
        return False


def enabled() -> bool:
    return bool(_key()) and _sdk_ok()


def status() -> dict:
    return {"enabled": enabled(), "has_key": bool(_key()), "sdk_installed": _sdk_ok(),
            "tts_model": TTS_MODEL, "stt_model": STT_MODEL, "speaker": SPEAKER}


def _client():
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=_key())


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
    # Try the configured speaker, then a few known-good ones, then the model's default.
    speakers: list[str | None] = [SPEAKER] + [s for s in SPEAKER_FALLBACKS if s != SPEAKER] + [None]
    last = None
    for sp in speakers:
        kw: dict = {"text": text, "language_code": lang_code, "model": TTS_MODEL}
        if sp:
            kw["speaker"] = sp
        try:
            return client.text_to_speech.convert(**kw)
        except TypeError:
            # Older SDKs used target_language_code instead of language_code.
            kw["target_language_code"] = kw.pop("language_code")
            try:
                return client.text_to_speech.convert(**kw)
            except Exception as e:
                last = e
        except Exception as e:
            last = e
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


def tts(text: str, lang_code: str) -> bytes:
    """WAV bytes for `text` spoken in `lang_code` (e.g. 'hi-IN'), cached by content."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("no text to speak")
    os.makedirs(CACHE_DIR, exist_ok=True)
    h = hashlib.sha256(f"{TTS_MODEL}|{SPEAKER}|{lang_code}|{text}".encode()).hexdigest()[:24]
    path = os.path.join(CACHE_DIR, f"{h}.wav")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()

    client = _client()
    parts = []
    for chunk in _split(text):
        resp = _convert(client, chunk, lang_code)
        audios = getattr(resp, "audios", None)
        if not audios:
            raise RuntimeError("Sarvam TTS returned no audio")
        parts.append(base64.b64decode(audios[0]))
    data = _stitch(parts)
    with open(path, "wb") as f:
        f.write(data)
    return data


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
