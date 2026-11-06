"""Turns a profile into a validated, localized bundle recommendation."""

from __future__ import annotations
import re
from udyam.quote_engine import build_quote
from udyam.validator import validate_reply
from udyam import data_loader, recommender

# Identifiers are tokenised before any free text is logged or sent to an external service.
PATTERNS = [
    ("GSTIN", r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"),
    ("UDYAM", r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b"),
    ("PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    ("AADHAAR", r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    ("PHONE", r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
]

# Recommendation text per language. Figures are interpolated from the quote engine, so every number
# shown is one the engine returned. {bundle} is a product name and stays as-is.
REPLY_TEMPLATES = {
    "en": ("Based on your profile I recommend the {bundle} bundle: ₹{monthly}/month, ₹{setup} one-time "
           "setup, a {contract}-month contract, with activation in about {eta} days. Every figure comes "
           "from the live pricing engine, and you can toggle add-ons to see the total update."),
    "hi": ("आपकी प्रोफ़ाइल के आधार पर मैं {bundle} बंडल सुझाता हूँ: ₹{monthly}/माह, ₹{setup} एकमुश्त सेटअप, "
           "{contract} महीने का अनुबंध, और लगभग {eta} दिनों में चालू। हर आँकड़ा लाइव प्राइसिंग इंजन से आता है, "
           "और आप ऐड-ऑन टॉगल करके कुल राशि बदलते देख सकते हैं।"),
    "ta": ("உங்கள் விவரத்தின் அடிப்படையில் {bundle} தொகுப்பை பரிந்துரைக்கிறேன்: ₹{monthly}/மாதம், ₹{setup} "
           "ஒருமுறை அமைப்புக் கட்டணம், {contract} மாத ஒப்பந்தம், சுமார் {eta} நாட்களில் செயல்படுத்தப்படும். "
           "ஒவ்வொரு எண்ணும் நேரடி விலை இயந்திரத்திலிருந்து வருகிறது; கூடுதல் சேவைகளை மாற்றி மொத்தத் தொகையை பார்க்கலாம்."),
    "te": ("మీ ప్రొఫైల్ ఆధారంగా {bundle} బండిల్‌ను సిఫార్సు చేస్తున్నాను: ₹{monthly}/నెల, ₹{setup} ఒకసారి సెటప్, "
           "{contract} నెలల ఒప్పందం, సుమారు {eta} రోజుల్లో యాక్టివేషన్. ప్రతి సంఖ్య లైవ్ ప్రైసింగ్ ఇంజిన్ నుండి వస్తుంది; "
           "యాడ్-ఆన్‌లను మార్చి మొత్తం మారడాన్ని చూడవచ్చు."),
    "bn": ("আপনার প্রোফাইল অনুযায়ী আমি {bundle} বান্ডল সুপারিশ করছি: ₹{monthly}/মাস, ₹{setup} এককালীন সেটআপ, "
           "{contract} মাসের চুক্তি, প্রায় {eta} দিনে চালু। প্রতিটি সংখ্যা লাইভ প্রাইসিং ইঞ্জিন থেকে আসে, এবং আপনি "
           "অ্যাড-অন টগল করে মোট পরিবর্তন দেখতে পারেন।"),
    "mr": ("तुमच्या प्रोफाइलनुसार मी {bundle} बंडलची शिफारस करतो: ₹{monthly}/महिना, ₹{setup} एकवेळ सेटअप, "
           "{contract} महिन्यांचा करार, आणि सुमारे {eta} दिवसांत सुरू. प्रत्येक आकडा थेट प्राइसिंग इंजिनमधून येतो, "
           "आणि तुम्ही अ‍ॅड-ऑन टॉगल करून एकूण रक्कम बदलताना पाहू शकता."),
    "kn": ("ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಆಧಾರದ ಮೇಲೆ {bundle} ಬಂಡಲ್ ಅನ್ನು ಶಿಫಾರಸು ಮಾಡುತ್ತೇನೆ: ₹{monthly}/ತಿಂಗಳು, ₹{setup} "
           "ಒಂದು ಬಾರಿ ಸೆಟಪ್, {contract} ತಿಂಗಳ ಒಪ್ಪಂದ, ಸುಮಾರು {eta} ದಿನಗಳಲ್ಲಿ ಸಕ್ರಿಯ. ಪ್ರತಿ ಅಂಕಿಯೂ ಲೈವ್ "
           "ಪ್ರೈಸಿಂಗ್ ಎಂಜಿನ್‌ನಿಂದ ಬರುತ್ತದೆ; ಆಡ್-ಆನ್‌ಗಳನ್ನು ಬದಲಾಯಿಸಿ ಒಟ್ಟು ಮೊತ್ತವನ್ನು ನೋಡಬಹುದು."),
    "pa": ("ਤੁਹਾਡੀ ਪ੍ਰੋਫਾਈਲ ਦੇ ਆਧਾਰ 'ਤੇ ਮੈਂ {bundle} ਬੰਡਲ ਦੀ ਸਿਫ਼ਾਰਸ਼ ਕਰਦਾ ਹਾਂ: ₹{monthly}/ਮਹੀਨਾ, ₹{setup} "
           "ਇੱਕ-ਵਾਰ ਸੈੱਟਅੱਪ, {contract} ਮਹੀਨੇ ਦਾ ਇਕਰਾਰਨਾਮਾ, ਅਤੇ ਲਗਭਗ {eta} ਦਿਨਾਂ ਵਿੱਚ ਚਾਲੂ। ਹਰ ਅੰਕੜਾ ਲਾਈਵ "
           "ਪ੍ਰਾਈਸਿੰਗ ਇੰਜਣ ਤੋਂ ਆਉਂਦਾ ਹੈ, ਅਤੇ ਤੁਸੀਂ ਐਡ-ਆਨ ਟੌਗਲ ਕਰਕੇ ਕੁੱਲ ਰਕਮ ਬਦਲਦੀ ਵੇਖ ਸਕਦੇ ਹੋ।"),
}


def redact(text: str, vault: dict) -> str:
    for kind, pat in PATTERNS:
        for m in re.findall(pat, text, flags=re.I):
            if kind == "AADHAAR":
                text = text.replace(m, "[AADHAAR_REMOVED]")
                continue
            token = vault.setdefault(m.upper(), f"[{kind}_{sum(t.startswith('[' + kind + '_') for t in vault.values()) + 1}]")
            text = text.replace(m, token)
    return text


def _money(x) -> str:
    # No rounding, a rounded figure would be a number the engine never returned.
    f = float(x)
    return f"{f:,.0f}" if f == int(f) else f"{f:,.2f}"


def recommend(profile: dict) -> dict:
    cat = data_loader.catalogue()
    name, items, eng_profile, quote = recommender.pick(cat, profile, data_loader.city_tiers())
    return {"bundle": name, "items": items, "profile": eng_profile, "quote": quote}


def deterministic_reply(profile: dict, lang: str = "en") -> dict:
    r = recommend(profile)
    q = r["quote"]
    figures = {"bundle": r["bundle"], "monthly": _money(q["monthly_inr"]), "setup": _money(q["setup_total_inr"]),
               "contract": q["contract_months"], "eta": q["activation_eta_days"]}

    canonical = REPLY_TEMPLATES["en"].format(**figures)
    problems = validate_reply(canonical, [q], {int(r["profile"]["employees"]), int(r["profile"]["num_sites"])})
    text = REPLY_TEMPLATES.get(lang, REPLY_TEMPLATES["en"]).format(**figures)

    chips = ["See full price breakdown", "Add CCTV", "Add POS", "Talk to a person"]
    return {"text": text, "quote_card": q, "bundle": r["bundle"],
            "chips": chips, "validator": "deterministic" if not problems else f"blocked:{problems}"}


def needs_profile_reply(lang: str = "en") -> dict:
    return {"text": "Tell me a little about your business and I'll size a bundle: what do you run, "
                    "roughly how many staff and locations, which city, and do you have a GST number?",
            "quote_card": None, "bundle": None,
            "chips": ["Micro / retail shop", "Professional office", "Multi-site chain", "Manufacturer"],
            "validator": "deterministic"}


def run_turn(session: dict, user_text: str) -> dict:
    profile = session.get("profile")
    if profile and profile.get("segment"):
        return deterministic_reply(profile, session.get("lang", "en"))
    return needs_profile_reply(session.get("lang", "en"))
