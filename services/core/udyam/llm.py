from __future__ import annotations
import base64, json, os, re, urllib.request, urllib.error

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def _call(parts: list, system: str | None = None, json_mode: bool = False, temperature: float = 0.2,
          timeout: float = 25.0, max_tokens: int = 900) -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    req = urllib.request.Request(URL.format(model=MODEL), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except Exception:
        return None


def _json(text: str | None):
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        return None


DOC_PROMPT = {
    "gst": "gstin, legal_name, trade_name, constitution, address (principal place of business), date_of_liability (YYYY-MM-DD), type",
    "udyam": "udyam_number (format UDYAM-XX-00-0000000, empty string if absent), enterprise_name, major_activity, city, state, date_of_registration (YYYY-MM-DD)",
    "sig": "name, designation, business (the business the ID is issued for), id_no, valid_till (YYYY-MM-DD)",
    "bill": "consumer_no, billed_to, address (supply address), bill_date (YYYY-MM-DD), units, amount",
}


def extract_document(data: bytes, doctype: str, mime: str = "image/png") -> dict | None:
    """Read one document photo."""
    if not available() or doctype not in DOC_PROMPT:
        return None
    prompt = (f"This is a photo of an Indian business KYC document ({doctype}). Return JSON with exactly these keys: "
              f"{DOC_PROMPT[doctype]}. Copy values exactly as printed, do not correct or guess. Use an empty string for anything "
              "you cannot read clearly. If the image is not this kind of document, return {\"error\": \"wrong_document\"}.")
    out = _json(_call([{"text": prompt}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}],
                      json_mode=True, temperature=0.0, timeout=40))
    if not isinstance(out, dict) or out.get("error"):
        return None
    return {k: str(v) for k, v in out.items()}


PROFILE_SYSTEM = (
    "You turn what a small-business owner says into a structured profile for a telecom bundle advisor. "
    "Reply with JSON only. Never mention prices or products by id. Keys: business_type (one of the allowed keys or null), "
    "employees (integer or null), num_sites (integer or null), city (the city name in English, for example Kolkata, or null), gstin_status (\"active\" if they say they have "
    "a GST number, \"none\" if they say they do not, else null), need_tags (list from the allowed tags), summary (one short plain "
    "sentence in the owner's language confirming what you understood)."
)


def parse_profile(text: str, lang: str, business_types: list[str], need_tags: list[str]) -> dict | None:
    """Understand a free-text or spoken description of a business."""
    if not available() or not text.strip():
        return None
    prompt = (f"Owner said (language code {lang}): {text!r}\nAllowed business_type keys: {business_types}\nAllowed need_tags: {need_tags}")
    out = _json(_call([{"text": prompt}], system=PROFILE_SYSTEM, json_mode=True, temperature=0.0, timeout=15, max_tokens=400))
    return out if isinstance(out, dict) else None


def explain(facts: dict, lang: str) -> str | None:
    """Phrase a recommendation in the owner's language from facts we computed."""
    if not available():
        return None
    system = ("You are a friendly Indian business advisor. In 2 or 3 short sentences, explain in the requested language why this bundle suits "
              "this business. Use ONLY the facts given. Do not state any price, percentage, number or product code. Plain words, no jargon. "
              "Do not greet or say hello, namaste or similar; start directly with the reason.")
    return _call([{"text": f"Language code: {lang}\nFacts: {json.dumps(facts, ensure_ascii=False)}"}], system=system,
                 temperature=0.4, timeout=12, max_tokens=300)
