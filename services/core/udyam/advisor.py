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

# The spoken/printed reply is built from these per-language blocks. Only PRICE carries figures, and
# only its English form is validated, so the guardrail still reasons about every number shown.
PRICE = {
    "en": "For your business I recommend the {bundle} bundle: ₹{monthly}/month, ₹{setup} one-time setup, a {contract}-month contract, live in about {eta} days.",
    "hi": "आपके व्यवसाय के लिए मैं {bundle} बंडल सुझाता हूँ: ₹{monthly}/माह, ₹{setup} एकमुश्त सेटअप, {contract} महीने का अनुबंध, और लगभग {eta} दिनों में चालू।",
    "ta": "உங்கள் வணிகத்திற்கு நான் {bundle} தொகுப்பை பரிந்துரைக்கிறேன்: ₹{monthly}/மாதம், ₹{setup} ஒருமுறை அமைப்புக் கட்டணம், {contract} மாத ஒப்பந்தம், சுமார் {eta} நாட்களில் செயல்படும்.",
    "te": "మీ వ్యాపారానికి నేను {bundle} బండిల్‌ను సిఫార్సు చేస్తున్నాను: ₹{monthly}/నెల, ₹{setup} ఒకసారి సెటప్, {contract} నెలల ఒప్పందం, సుమారు {eta} రోజుల్లో యాక్టివేషన్.",
    "bn": "আপনার ব্যবসার জন্য আমি {bundle} বান্ডল সুপারিশ করছি: ₹{monthly}/মাস, ₹{setup} এককালীন সেটআপ, {contract} মাসের চুক্তি, প্রায় {eta} দিনে চালু।",
    "mr": "तुमच्या व्यवसायासाठी मी {bundle} बंडलची शिफारस करतो: ₹{monthly}/महिना, ₹{setup} एकवेळ सेटअप, {contract} महिन्यांचा करार, सुमारे {eta} दिवसांत सुरू.",
    "kn": "ನಿಮ್ಮ ವ್ಯಾಪಾರಕ್ಕೆ ನಾನು {bundle} ಬಂಡಲ್ ಅನ್ನು ಶಿಫಾರಸು ಮಾಡುತ್ತೇನೆ: ₹{monthly}/ತಿಂಗಳು, ₹{setup} ಒಂದು ಬಾರಿ ಸೆಟಪ್, {contract} ತಿಂಗಳ ಒಪ್ಪಂದ, ಸುಮಾರು {eta} ದಿನಗಳಲ್ಲಿ ಸಕ್ರಿಯ.",
    "pa": "ਤੁਹਾਡੇ ਕਾਰੋਬਾਰ ਲਈ ਮੈਂ {bundle} ਬੰਡਲ ਦੀ ਸਿਫ਼ਾਰਸ਼ ਕਰਦਾ ਹਾਂ: ₹{monthly}/ਮਹੀਨਾ, ₹{setup} ਇੱਕ-ਵਾਰ ਸੈੱਟਅੱਪ, {contract} ਮਹੀਨੇ ਦਾ ਇਕਰਾਰਨਾਮਾ, ਲਗਭਗ {eta} ਦਿਨਾਂ ਵਿੱਚ ਚਾਲੂ।",
}

WHY = {
    "en": {
        "micro": "As a shop, your priority is reliable internet for UPI and card payments, so this keeps your billing and customer reach always online.",
        "prof": "For a professional office this focuses on uptime, business email and keeping your client data secure.",
        "multi": "Across your locations this gives you one bill, central management and backup internet so no site goes offline.",
        "mfg": "For a manufacturing unit this prioritises dedicated, reliable bandwidth with security and room for machine monitoring.",
    },
    "hi": {
        "micro": "दुकान के लिए सबसे ज़रूरी है UPI और कार्ड पेमेंट के लिए भरोसेमंद इंटरनेट, ताकि आपकी बिलिंग और ग्राहकों तक पहुँच हमेशा चालू रहे।",
        "prof": "प्रोफेशनल ऑफिस के लिए यह अपटाइम, बिज़नेस ईमेल और आपके क्लाइंट डेटा की सुरक्षा पर केंद्रित है।",
        "multi": "आपकी सभी लोकेशनों के लिए यह एक बिल, केंद्रीय प्रबंधन और बैकअप इंटरनेट देता है ताकि कोई भी साइट बंद न हो।",
        "mfg": "मैन्युफैक्चरिंग यूनिट के लिए यह समर्पित, भरोसेमंद बैंडविड्थ, सुरक्षा और मशीन मॉनिटरिंग की सुविधा को प्राथमिकता देता है।",
    },
    "ta": {
        "micro": "கடைக்கு முக்கியமானது UPI மற்றும் கார்டு பணப்பரிவர்த்தனைக்கு நம்பகமான இணையம்; இது உங்கள் பில்லிங் மற்றும் வாடிக்கையாளர் தொடர்பை எப்போதும் இயங்கச் செய்கிறது.",
        "prof": "தொழில்முறை அலுவலகத்திற்கு இது இயக்க நேரம், வணிக மின்னஞ்சல் மற்றும் உங்கள் வாடிக்கையாளர் தரவின் பாதுகாப்பில் கவனம் செலுத்துகிறது.",
        "multi": "உங்கள் அனைத்து இடங்களுக்கும் இது ஒரே பில், மைய மேலாண்மை மற்றும் காப்பு இணையத்தை வழங்குகிறது, எந்த இடமும் செயலிழக்காது.",
        "mfg": "உற்பத்தி அலகுக்கு இது பிரத்யேக, நம்பகமான அலைவரிசை, பாதுகாப்பு மற்றும் இயந்திர கண்காணிப்புக்கு இடம் தருகிறது.",
    },
    "te": {
        "micro": "దుకాణానికి ముఖ్యమైనది UPI మరియు కార్డు చెల్లింపులకు నమ్మకమైన ఇంటర్నెట్; ఇది మీ బిల్లింగ్ మరియు కస్టమర్ చేరువను ఎప్పుడూ ఆన్‌లైన్‌లో ఉంచుతుంది.",
        "prof": "ప్రొఫెషనల్ ఆఫీస్ కోసం ఇది అప్‌టైమ్, బిజినెస్ ఇమెయిల్ మరియు మీ క్లయింట్ డేటా భద్రతపై దృష్టి పెడుతుంది.",
        "multi": "మీ అన్ని లొకేషన్లకు ఇది ఒకే బిల్లు, కేంద్ర నిర్వహణ మరియు బ్యాకప్ ఇంటర్నెట్ ఇస్తుంది, ఏ సైట్ కూడా ఆఫ్‌లైన్ కాదు.",
        "mfg": "తయారీ యూనిట్ కోసం ఇది అంకితమైన, నమ్మకమైన బ్యాండ్‌విడ్త్, భద్రత మరియు మెషిన్ మానిటరింగ్‌కు అవకాశం ఇస్తుంది.",
    },
    "bn": {
        "micro": "দোকানের জন্য সবচেয়ে জরুরি UPI ও কার্ড পেমেন্টের জন্য নির্ভরযোগ্য ইন্টারনেট, যাতে আপনার বিলিং ও গ্রাহকের নাগাল সবসময় চালু থাকে।",
        "prof": "পেশাদার অফিসের জন্য এটি আপটাইম, বিজনেস ইমেল এবং আপনার ক্লায়েন্ট ডেটার নিরাপত্তায় মনোযোগ দেয়।",
        "multi": "আপনার সব লোকেশনের জন্য এটি একটি বিল, কেন্দ্রীয় ব্যবস্থাপনা এবং ব্যাকআপ ইন্টারনেট দেয়, যাতে কোনো সাইট বন্ধ না হয়।",
        "mfg": "উৎপাদন ইউনিটের জন্য এটি নিবেদিত, নির্ভরযোগ্য ব্যান্ডউইথ, নিরাপত্তা এবং মেশিন মনিটরিংয়ের সুযোগ অগ্রাধিকার দেয়।",
    },
    "mr": {
        "micro": "दुकानासाठी सर्वात महत्त्वाचे म्हणजे UPI आणि कार्ड पेमेंटसाठी विश्वासार्ह इंटरनेट, जेणेकरून तुमची बिलिंग आणि ग्राहकांपर्यंत पोहोच नेहमी सुरू राहील.",
        "prof": "प्रोफेशनल ऑफिससाठी हे अपटाइम, बिझनेस ईमेल आणि तुमच्या क्लायंट डेटाच्या सुरक्षेवर लक्ष केंद्रित करते.",
        "multi": "तुमच्या सर्व ठिकाणांसाठी हे एक बिल, केंद्रीय व्यवस्थापन आणि बॅकअप इंटरनेट देते, जेणेकरून कोणतेही ठिकाण बंद पडणार नाही.",
        "mfg": "उत्पादन युनिटसाठी हे समर्पित, विश्वासार्ह बँडविड्थ, सुरक्षा आणि मशीन मॉनिटरिंगला प्राधान्य देते.",
    },
    "kn": {
        "micro": "ಅಂಗಡಿಗೆ ಮುಖ್ಯವಾದದ್ದು UPI ಮತ್ತು ಕಾರ್ಡ್ ಪಾವತಿಗಳಿಗೆ ವಿಶ್ವಾಸಾರ್ಹ ಇಂಟರ್ನೆಟ್; ಇದು ನಿಮ್ಮ ಬಿಲ್ಲಿಂಗ್ ಮತ್ತು ಗ್ರಾಹಕರ ತಲುಪುವಿಕೆಯನ್ನು ಯಾವಾಗಲೂ ಆನ್‌ಲೈನ್‌ನಲ್ಲಿ ಇರಿಸುತ್ತದೆ.",
        "prof": "ವೃತ್ತಿಪರ ಕಚೇರಿಗೆ ಇದು ಅಪ್‌ಟೈಮ್, ಬಿಸಿನೆಸ್ ಇಮೇಲ್ ಮತ್ತು ನಿಮ್ಮ ಕ್ಲೈಂಟ್ ಡೇಟಾದ ಭದ್ರತೆಯ ಮೇಲೆ ಗಮನಹರಿಸುತ್ತದೆ.",
        "multi": "ನಿಮ್ಮ ಎಲ್ಲಾ ಸ್ಥಳಗಳಿಗೆ ಇದು ಒಂದೇ ಬಿಲ್, ಕೇಂದ್ರ ನಿರ್ವಹಣೆ ಮತ್ತು ಬ್ಯಾಕಪ್ ಇಂಟರ್ನೆಟ್ ನೀಡುತ್ತದೆ, ಯಾವುದೇ ಸ್ಥಳ ಆಫ್‌ಲೈನ್ ಆಗುವುದಿಲ್ಲ.",
        "mfg": "ಉತ್ಪಾದನಾ ಘಟಕಕ್ಕೆ ಇದು ಮೀಸಲಾದ, ವಿಶ್ವಾಸಾರ್ಹ ಬ್ಯಾಂಡ್‌ವಿಡ್ತ್, ಭದ್ರತೆ ಮತ್ತು ಯಂತ್ರ ಮೇಲ್ವಿಚಾರಣೆಗೆ ಅವಕಾಶ ನೀಡುತ್ತದೆ.",
    },
    "pa": {
        "micro": "ਦੁਕਾਨ ਲਈ ਸਭ ਤੋਂ ਜ਼ਰੂਰੀ ਹੈ UPI ਅਤੇ ਕਾਰਡ ਭੁਗਤਾਨ ਲਈ ਭਰੋਸੇਯੋਗ ਇੰਟਰਨੈੱਟ, ਤਾਂ ਜੋ ਤੁਹਾਡੀ ਬਿਲਿੰਗ ਅਤੇ ਗਾਹਕਾਂ ਤੱਕ ਪਹੁੰਚ ਹਮੇਸ਼ਾ ਚਾਲੂ ਰਹੇ।",
        "prof": "ਪ੍ਰੋਫੈਸ਼ਨਲ ਦਫ਼ਤਰ ਲਈ ਇਹ ਅਪਟਾਈਮ, ਬਿਜ਼ਨਸ ਈਮੇਲ ਅਤੇ ਤੁਹਾਡੇ ਕਲਾਇੰਟ ਡਾਟਾ ਦੀ ਸੁਰੱਖਿਆ 'ਤੇ ਧਿਆਨ ਦਿੰਦਾ ਹੈ।",
        "multi": "ਤੁਹਾਡੀਆਂ ਸਾਰੀਆਂ ਥਾਵਾਂ ਲਈ ਇਹ ਇੱਕ ਬਿੱਲ, ਕੇਂਦਰੀ ਪ੍ਰਬੰਧਨ ਅਤੇ ਬੈਕਅੱਪ ਇੰਟਰਨੈੱਟ ਦਿੰਦਾ ਹੈ, ਤਾਂ ਜੋ ਕੋਈ ਵੀ ਥਾਂ ਬੰਦ ਨਾ ਹੋਵੇ।",
        "mfg": "ਨਿਰਮਾਣ ਯੂਨਿਟ ਲਈ ਇਹ ਸਮਰਪਿਤ, ਭਰੋਸੇਯੋਗ ਬੈਂਡਵਿਡਥ, ਸੁਰੱਖਿਆ ਅਤੇ ਮਸ਼ੀਨ ਨਿਗਰਾਨੀ ਨੂੰ ਤਰਜੀਹ ਦਿੰਦਾ ਹੈ।",
    },
}

UPGRADE = {
    "en": "It is a proper business-grade step up from your current setup.",
    "hi": "यह आपके मौजूदा सेटअप से एक बेहतर, बिज़नेस-ग्रेड अपग्रेड है।",
    "ta": "இது உங்கள் தற்போதைய அமைப்பை விட சிறந்த, வணிக-தர மேம்பாடு.",
    "te": "ఇది మీ ప్రస్తుత సెటప్ కంటే మెరుగైన, బిజినెస్-గ్రేడ్ అప్‌గ్రేడ్.",
    "bn": "এটি আপনার বর্তমান সেটআপের চেয়ে ভালো, বিজনেস-গ্রেড আপগ্রেড।",
    "mr": "हे तुमच्या सध्याच्या सेटअपपेक्षा चांगले, बिझनेस-ग्रेड अपग्रेड आहे.",
    "kn": "ಇದು ನಿಮ್ಮ ಪ್ರಸ್ತುತ ಸೆಟಪ್‌ಗಿಂತ ಉತ್ತಮ, ಬಿಸಿನೆಸ್-ಗ್ರೇಡ್ ಅಪ್‌ಗ್ರೇಡ್.",
    "pa": "ਇਹ ਤੁਹਾਡੇ ਮੌਜੂਦਾ ਸੈੱਟਅੱਪ ਤੋਂ ਵਧੀਆ, ਬਿਜ਼ਨਸ-ਗ੍ਰੇਡ ਅਪਗ੍ਰੇਡ ਹੈ।",
}

NEEDS_ADDED = {
    "en": "I've included the extras you asked for.",
    "hi": "आपने जो अतिरिक्त चीज़ें चाहीं, वे मैंने जोड़ दी हैं।",
    "ta": "நீங்கள் கேட்ட கூடுதல் சேவைகளை நான் சேர்த்துள்ளேன்.",
    "te": "మీరు అడిగిన అదనపు సేవలను నేను చేర్చాను.",
    "bn": "আপনি যে অতিরিক্ত সেবাগুলি চেয়েছেন, সেগুলি আমি যোগ করেছি।",
    "mr": "तुम्ही मागितलेल्या अतिरिक्त सेवा मी जोडल्या आहेत.",
    "kn": "ನೀವು ಕೇಳಿದ ಹೆಚ್ಚುವರಿ ಸೇವೆಗಳನ್ನು ನಾನು ಸೇರಿಸಿದ್ದೇನೆ.",
    "pa": "ਤੁਸੀਂ ਜੋ ਵਾਧੂ ਸੇਵਾਵਾਂ ਮੰਗੀਆਂ, ਉਹ ਮੈਂ ਜੋੜ ਦਿੱਤੀਆਂ ਹਨ।",
}

NEEDS_SKIPPED = {
    "en": "A couple of extras need an active GST number, so I left those out for now.",
    "hi": "कुछ अतिरिक्त सेवाओं के लिए एक्टिव GST नंबर चाहिए, इसलिए उन्हें अभी छोड़ दिया है।",
    "ta": "சில கூடுதல் சேவைகளுக்கு செயலில் உள்ள GST எண் தேவை, எனவே அவற்றை இப்போது விட்டுவிட்டேன்.",
    "te": "కొన్ని అదనపు సేవలకు యాక్టివ్ GST నంబర్ అవసరం, కాబట్టి వాటిని ప్రస్తుతం వదిలేశాను.",
    "bn": "কিছু অতিরিক্ত সেবার জন্য সক্রিয় GST নম্বর দরকার, তাই সেগুলি আপাতত বাদ দিয়েছি।",
    "mr": "काही अतिरिक्त सेवांसाठी सक्रिय GST नंबर आवश्यक आहे, म्हणून त्या सध्या वगळल्या आहेत.",
    "kn": "ಕೆಲವು ಹೆಚ್ಚುವರಿ ಸೇವೆಗಳಿಗೆ ಸಕ್ರಿಯ GST ಸಂಖ್ಯೆ ಅಗತ್ಯ, ಆದ್ದರಿಂದ ಅವುಗಳನ್ನು ಸದ್ಯ ಬಿಟ್ಟಿದ್ದೇನೆ.",
    "pa": "ਕੁਝ ਵਾਧੂ ਸੇਵਾਵਾਂ ਲਈ ਸਰਗਰਮ GST ਨੰਬਰ ਚਾਹੀਦਾ ਹੈ, ਇਸ ਲਈ ਉਹ ਹੁਣ ਲਈ ਛੱਡ ਦਿੱਤੀਆਂ।",
}

TRUST = {
    "en": "Every figure comes from our live pricing engine, and you can toggle add-ons to update the total.",
    "hi": "हर आँकड़ा हमारे लाइव प्राइसिंग इंजन से आता है, और आप ऐड-ऑन टॉगल करके कुल राशि बदल सकते हैं।",
    "ta": "ஒவ்வொரு எண்ணும் எங்கள் நேரடி விலை இயந்திரத்திலிருந்து வருகிறது; கூடுதல் சேவைகளை மாற்றி மொத்தத் தொகையை புதுப்பிக்கலாம்.",
    "te": "ప్రతి సంఖ్య మా లైవ్ ప్రైసింగ్ ఇంజిన్ నుండి వస్తుంది; యాడ్-ఆన్‌లను మార్చి మొత్తాన్ని అప్‌డేట్ చేయవచ్చు.",
    "bn": "প্রতিটি সংখ্যা আমাদের লাইভ প্রাইসিং ইঞ্জিন থেকে আসে, এবং আপনি অ্যাড-অন টগল করে মোট পরিবর্তন করতে পারেন।",
    "mr": "प्रत्येक आकडा आमच्या लाइव्ह प्राइसिंग इंजिनमधून येतो, आणि तुम्ही अ‍ॅड-ऑन टॉगल करून एकूण रक्कम बदलू शकता.",
    "kn": "ಪ್ರತಿ ಅಂಕಿಯೂ ನಮ್ಮ ಲೈವ್ ಪ್ರೈಸಿಂಗ್ ಎಂಜಿನ್‌ನಿಂದ ಬರುತ್ತದೆ, ಮತ್ತು ಆಡ್-ಆನ್‌ಗಳನ್ನು ಟಾಗಲ್ ಮಾಡಿ ಒಟ್ಟು ಮೊತ್ತ ಬದಲಾಯಿಸಬಹುದು.",
    "pa": "ਹਰ ਅੰਕੜਾ ਸਾਡੇ ਲਾਈਵ ਪ੍ਰਾਈਸਿੰਗ ਇੰਜਣ ਤੋਂ ਆਉਂਦਾ ਹੈ, ਅਤੇ ਤੁਸੀਂ ਐਡ-ਆਨ ਟੌਗਲ ਕਰਕੇ ਕੁੱਲ ਰਕਮ ਬਦਲ ਸਕਦੇ ਹੋ।",
}

CONSUMER_GRADE = {"hotspot", "broadband"}


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
    # No rounding; a rounded figure would be a number the engine never returned.
    f = float(x)
    return f"{f:,.0f}" if f == int(f) else f"{f:,.2f}"


def _t(table: dict, lang: str):
    return table.get(lang, table["en"])


def recommend(profile: dict) -> dict:
    cat = data_loader.catalogue()
    needs = profile.get("needs") or []
    name, items, eng_profile, quote, extras = recommender.pick(cat, profile, data_loader.city_tiers(), needs)
    return {"bundle": name, "items": items, "profile": eng_profile, "quote": quote, "extras": extras}


def deterministic_reply(profile: dict, lang: str = "en") -> dict:
    r = recommend(profile)
    q = r["quote"]
    seg = r["profile"]["segment"]
    extras = r["extras"]
    figures = {"bundle": r["bundle"], "monthly": _money(q["monthly_inr"]), "setup": _money(q["setup_total_inr"]),
               "contract": q["contract_months"], "eta": q["activation_eta_days"]}

    canonical = PRICE["en"].format(**figures)
    problems = validate_reply(canonical, [q], {int(r["profile"]["employees"]), int(r["profile"]["num_sites"])})

    parts = [_t(PRICE, lang).format(**figures), _t(WHY, lang).get(seg, WHY["en"][seg])]
    if (profile.get("current_tools") or "") in CONSUMER_GRADE:
        parts.append(_t(UPGRADE, lang))
    if extras["included_needs"]:
        parts.append(_t(NEEDS_ADDED, lang))
    if extras["skipped_needs"]:
        parts.append(_t(NEEDS_SKIPPED, lang))
    parts.append(_t(TRUST, lang))
    text = " ".join(parts)

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
