from __future__ import annotations
import re
from udyam.quote_engine import build_quote
from udyam.validator import validate_reply
from udyam import data_loader, recommender, llm, profiles

PATTERNS = [
    ("GSTIN", r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"),
    ("UDYAM", r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b"),
    ("PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    ("AADHAAR", r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    ("PHONE", r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
]

PRICE = {
    "en": "For your business I recommend the {bundle}: ₹{monthly}/month, ₹{setup} one-time setup, a {contract}-month contract, live in about {eta} days.",
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
    "en": "It also covers what you asked for.",
    "hi": "आपने जो माँगा था, वह भी इसमें शामिल है।",
    "ta": "நீங்கள் கேட்டவையும் இதில் அடங்கும்.",
    "te": "మీరు అడిగినవి కూడా ఇందులో ఉన్నాయి.",
    "bn": "আপনি যা চেয়েছিলেন, সেটাও এতে আছে।",
    "mr": "तुम्ही जे मागितले, तेही यात आहे.",
    "kn": "ನೀವು ಕೇಳಿದ್ದೂ ಇದರಲ್ಲಿ ಸೇರಿದೆ.",
    "pa": "ਤੁਸੀਂ ਜੋ ਮੰਗਿਆ ਸੀ, ਉਹ ਵੀ ਇਸ ਵਿੱਚ ਸ਼ਾਮਲ ਹੈ।",
}

NEEDS_SKIPPED = {
    "en": "Some of what you asked for needs an active GST number or a larger setup, so it is not in the plan yet.",
    "hi": "आपकी माँगी कुछ सेवाओं के लिए एक्टिव GST नंबर या बड़ा सेटअप चाहिए, इसलिए वे अभी प्लान में नहीं हैं।",
    "ta": "நீங்கள் கேட்ட சிலவற்றுக்கு செயலில் உள்ள GST எண் அல்லது பெரிய அமைப்பு தேவை, எனவே அவை இப்போது திட்டத்தில் இல்லை.",
    "te": "మీరు అడిగిన కొన్నింటికి యాక్టివ్ GST నంబర్ లేదా పెద్ద సెటప్ అవసరం, కాబట్టి అవి ఇప్పుడు ప్లాన్‌లో లేవు.",
    "bn": "আপনার চাওয়া কিছু জিনিসের জন্য সক্রিয় GST নম্বর বা বড় সেটআপ দরকার, তাই সেগুলি এখন প্ল্যানে নেই।",
    "mr": "तुम्ही मागितलेल्या काही गोष्टींसाठी सक्रिय GST क्रमांक किंवा मोठा सेटअप लागतो, म्हणून त्या सध्या प्लॅनमध्ये नाहीत.",
    "kn": "ನೀವು ಕೇಳಿದ ಕೆಲವಕ್ಕೆ ಸಕ್ರಿಯ GST ಸಂಖ್ಯೆ ಅಥವಾ ದೊಡ್ಡ ಸೆಟಪ್ ಬೇಕು, ಆದ್ದರಿಂದ ಅವು ಈಗ ಪ್ಲಾನ್‌ನಲ್ಲಿ ಇಲ್ಲ.",
    "pa": "ਤੁਹਾਡੀਆਂ ਮੰਗੀਆਂ ਕੁਝ ਚੀਜ਼ਾਂ ਲਈ ਸਰਗਰਮ GST ਨੰਬਰ ਜਾਂ ਵੱਡਾ ਸੈੱਟਅੱਪ ਚਾਹੀਦਾ ਹੈ, ਇਸ ਲਈ ਉਹ ਹਾਲੇ ਪਲਾਨ ਵਿੱਚ ਨਹੀਂ ਹਨ।",
}

ADJUST = {
    "en": "On the next screen you can change the number of lines, cameras or seats, and switch add-ons on or off. The price updates as you go.",
    "hi": "अगली स्क्रीन पर आप लाइन, कैमरे या सीटों की संख्या बदल सकते हैं और ऐड-ऑन चालू या बंद कर सकते हैं। कीमत साथ-साथ बदलती है।",
    "ta": "அடுத்த திரையில் இணைப்புகள், கேமராக்கள் அல்லது இருக்கைகளின் எண்ணிக்கையை மாற்றலாம், கூடுதல் சேவைகளை சேர்க்கலாம் அல்லது நீக்கலாம். விலை உடனே மாறும்.",
    "te": "తదుపరి స్క్రీన్‌లో లైన్లు, కెమెరాలు లేదా సీట్ల సంఖ్యను మార్చవచ్చు, యాడ్-ఆన్‌లను ఆన్ లేదా ఆఫ్ చేయవచ్చు. ధర వెంటనే మారుతుంది.",
    "bn": "পরের স্ক্রিনে লাইন, ক্যামেরা বা সিটের সংখ্যা বদলাতে পারবেন, আর অ্যাড-অন চালু বা বন্ধ করতে পারবেন। দাম সঙ্গে সঙ্গে বদলাবে।",
    "mr": "पुढच्या स्क्रीनवर तुम्ही लाइन, कॅमेरे किंवा सीट्सची संख्या बदलू शकता आणि ॲड-ऑन चालू किंवा बंद करू शकता. किंमत लगेच बदलते.",
    "kn": "ಮುಂದಿನ ಪರದೆಯಲ್ಲಿ ಲೈನ್‌ಗಳು, ಕ್ಯಾಮೆರಾಗಳು ಅಥವಾ ಸೀಟುಗಳ ಸಂಖ್ಯೆ ಬದಲಿಸಬಹುದು, ಆಡ್-ಆನ್‌ಗಳನ್ನು ಆನ್ ಅಥವಾ ಆಫ್ ಮಾಡಬಹುದು. ಬೆಲೆ ತಕ್ಷಣ ಬದಲಾಗುತ್ತದೆ.",
    "pa": "ਅਗਲੀ ਸਕ੍ਰੀਨ 'ਤੇ ਤੁਸੀਂ ਲਾਈਨਾਂ, ਕੈਮਰਿਆਂ ਜਾਂ ਸੀਟਾਂ ਦੀ ਗਿਣਤੀ ਬਦਲ ਸਕਦੇ ਹੋ ਅਤੇ ਐਡ-ਆਨ ਚਾਲੂ ਜਾਂ ਬੰਦ ਕਰ ਸਕਦੇ ਹੋ। ਕੀਮਤ ਨਾਲ-ਨਾਲ ਬਦਲਦੀ ਹੈ।",
}

TRUST = {
    "en": "Tap any item to see what it includes, and add or remove options to adjust your plan.",
    "hi": "किसी भी आइटम पर टैप करके देखें उसमें क्या शामिल है, और विकल्प जोड़कर या हटाकर अपना प्लान बदलें।",
    "ta": "ஒவ்வொரு உருப்படியையும் தட்டி அதில் என்ன உள்ளது என்று பாருங்கள், விருப்பங்களை சேர்த்தோ நீக்கியோ உங்கள் திட்டத்தை மாற்றுங்கள்.",
    "te": "ప్రతి అంశంపై ట్యాప్ చేసి అందులో ఏమి ఉందో చూడండి, ఎంపికలను జోడించడం లేదా తీసివేయడం ద్వారా మీ ప్లాన్‌ను సర్దుబాటు చేయండి.",
    "bn": "যেকোনো আইটেমে ট্যাপ করে দেখুন তাতে কী আছে, এবং অপশন যোগ বা বাদ দিয়ে আপনার প্ল্যান সাজান।",
    "mr": "कोणत्याही आयटमवर टॅप करून त्यात काय आहे ते पाहा, आणि पर्याय जोडून किंवा काढून तुमचा प्लॅन समायोजित करा.",
    "kn": "ಯಾವುದೇ ಐಟಂ ಮೇಲೆ ಟ್ಯಾಪ್ ಮಾಡಿ ಅದರಲ್ಲಿ ಏನಿದೆ ಎಂದು ನೋಡಿ, ಆಯ್ಕೆಗಳನ್ನು ಸೇರಿಸಿ ಅಥವಾ ತೆಗೆದು ನಿಮ್ಮ ಪ್ಲಾನ್ ಹೊಂದಿಸಿ.",
    "pa": "ਕਿਸੇ ਵੀ ਆਈਟਮ 'ਤੇ ਟੈਪ ਕਰਕੇ ਵੇਖੋ ਉਸ ਵਿੱਚ ਕੀ ਸ਼ਾਮਲ ਹੈ, ਅਤੇ ਵਿਕਲਪ ਜੋੜ ਕੇ ਜਾਂ ਹਟਾ ਕੇ ਆਪਣਾ ਪਲਾਨ ਵਿਵਸਥਿਤ ਕਰੋ।",
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
    f = float(x)
    return f"{f:,.0f}" if f == int(f) else f"{f:,.2f}"


def _t(table: dict, lang: str):
    return table.get(lang, table["en"])


def recommend(profile: dict) -> dict:
    cat = data_loader.catalogue()
    raw = data_loader.catalogue_raw()
    categories = profile.get("categories") or profile.get("needs") or []
    name, items, eng_profile, quote, extras = recommender.pick(cat, raw, profile, data_loader.city_tiers(), categories, profile.get("need_tags"))
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

    why = extras["why"] if lang == "en" and extras.get("why") else _t(WHY, lang).get(seg, WHY["en"][seg])
    if lang != "en":
        why = _localized_why(r, lang) or why
    parts = [_t(PRICE, lang).format(**figures), why]
    if (profile.get("current_tools") or "") in CONSUMER_GRADE:
        parts.append(_t(UPGRADE, lang))
    if extras.get("asked") and extras["included_needs"]:
        parts.append(_t(NEEDS_ADDED, lang))
    if extras.get("asked") and extras["skipped_needs"]:
        parts.append(_t(NEEDS_SKIPPED, lang))
    parts.append(_t(ADJUST, lang))
    text = " ".join(parts)

    chips = ["See full price breakdown", "Add CCTV", "Add POS", "Talk to a person"]
    return {"text": text, "quote_card": q, "bundle": r["bundle"],
            "chips": chips, "validator": "deterministic" if not problems else f"blocked:{problems}"}


_NUMERIC = re.compile(r"[\d\u0966-\u096f\u09e6-\u09ef\u0a66-\u0a6f\u0be6-\u0bef\u0c66-\u0c6f\u0ce6-\u0cef₹%]")


def _localized_why(r: dict, lang: str) -> str | None:
    if not llm.available():
        return None
    facts = {"business": r["extras"].get("business"), "bundle": r["bundle"],
             "services": [i.get("label") or i.get("name") for i in r["quote"].get("items", [])][:7]}
    text = llm.explain(facts, lang)
    if not text or _NUMERIC.search(text) or len(text) > 400:
        return None
    text = _GREETING.sub("", text.strip()).strip()
    return (text[:1].upper() + text[1:]) if text else None


_GREETING = re.compile(r"^\s*(namaste|namaskar|hello|hi|vanakkam|नमस्ते|नमस्कार|வணக்கம்|నమస్తే|నమస్కారం|নমস্কার|নমস্তে|ನಮಸ್ಕಾರ|ನಮಸ್ತೆ|ਸਤ ਸ੍ਰੀ ਅਕਾਲ|ਨਮਸਤੇ)(\s*ji|\s*जी)?\s*[!,.।]*\s*", re.I)


_MISSING_Q = {
    "employees": "Got it, a {name}. Roughly how many people work in the business?",
    "type": "Tell me what kind of business it is (for example a salon, clinic, kirana store or software company) and how many people work there.",
}


KEYWORDS = {
    "kirana": ["kirana", "grocery", "general store", "किराना", "মুদি", "கிராணா", "మళిగ", "किराणा", "ಕಿರಾಣಿ", "ਕਰਿਆਨਾ"],
    "salon": ["salon", "parlour", "parlor", "beauty", "सैलून", "পার্লার", "সেলুন", "சலூன்", "సెలూన్", "ಸಲೂನ್", "ਸੈਲੂਨ"],
    "pharmacy": ["pharmacy", "chemist", "medical store", "फार्मेसी", "दवा", "ফার্মেসি", "மருந்தகம்", "ఫార్మసీ", "ಫಾರ್ಮಸಿ", "ਫਾਰਮੇਸੀ"],
    "bakery": ["bakery", "bake", "बेकरी", "বেকারি", "பேக்கரி", "బేకరీ", "ಬೇಕರಿ", "ਬੇਕਰੀ"],
    "apparel": ["boutique", "garment shop", "clothing", "कपड़े"],
    "mobile_repair": ["mobile repair", "phone repair", "मोबाइल रिपेयर", "மொபைல் ரிப்பேர்", "మొబైల్ రిపేర్"],
    "dental": ["dental", "dentist", "डेंटल", "ডেন্টাল", "பல் மருத்துவ"],
    "clinic": ["clinic", "doctor", "क्लिनिक", "ক্লিনিক", "கிளினிக்", "క్లినిక్", "ಕ್ಲಿನಿಕ್", "ਕਲੀਨਿਕ"],
    "diagnostic": ["diagnostic", "pathology", "lab", "डायग्नोस्टिक", "ডায়াগনস্টিক", "ಡಯಾಗ್ನೋಸ್ಟಿಕ್"],
    "ca": ["ca firm", "chartered accountant", "accountant", "सीए", "চার্টার্ড"],
    "coaching": ["coaching", "tuition", "institute", "कोचिंग", "কোচিং", "கோச்சிங்"],
    "law": ["law", "lawyer", "advocate", "legal", "वकील", "লয়্যার", "ஆலோசகர்", "लॉ"],
    "software": ["software", "it company", "saas", "सॉफ्टवेयर"],
    "consulting": ["consulting", "consultancy", "consultant"],
    "agency": ["agency", "marketing agency", "design studio"],
    "restaurant": ["restaurant", "cafe", "dhaba", "रेस्टोरेंट", "রেস্তোরাঁ", "உணவகம்", "రెస్టారెంట్", "ਰੈਸਟੋਰੈਂਟ"],
    "hotel": ["hotel", "guest house", "homestay", "होटल", "হোটেল", "ஹோட்டல்", "హోటల్", "ಹೋಟೆಲ್", "ਹੋਟਲ"],
    "gym": ["gym", "fitness", "जिम", "জিম", "ஜிம்", "జిమ్", "ಜಿಮ್", "ਜਿਮ"],
    "preschool": ["preschool", "play school", "playschool", "nursery", "प्ले स्कूल"],
    "autoparts": ["auto parts", "autoparts", "spare parts", "ऑटो पार्ट्स", "ਆਟੋ ਪਾਰਟਸ"],
    "textile": ["textile", "weaving", "कपड़ा मिल"],
    "factory": ["factory", "manufacturing", "plant", "फैक्ट्री", "কারখানা"],
    "printing": ["printing", "press", "प्रिंटिंग"],
    "packaging": ["packaging"],
    "food_processing": ["food processing"],
    "retail": ["retail", "shop", "store", "दुकान", "দোকান", "கடை", "దుకాణం", "ದುಕಾನ", "ਦੁਕਾਨ"],
}
_INDIC_DIGITS = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯೦೧೨೩೪೫೬೭೮೯੦੧੨੩੪੫੬੭੮੯", "0123456789" * 6)
_NO_GST = re.compile(r"\b(no|not|without|nahi|nahin)\b[^.]{0,20}\bgst|gst\b[^.]{0,20}\b(no|nahi|nahin|not)\b|नहीं|নেই|இல்லை|లేదు", re.I)


NEED_WORDS = {
    "internet": ["internet", "wifi", "wi-fi", "broadband", "fibre", "fiber", "इंटरनेट", "ইন্টারনেট", "இணையம்", "ఇంటర్నెట్", "ಇಂಟರ್ನೆಟ್", "ਇੰਟਰਨੈੱਟ"],
    "backup_internet": ["backup internet", "backup line", "failover", "never goes down"],
    "static_ip": ["static ip", "fixed ip"],
    "branch_network": ["connect branches", "connect our branches", "branch network", "vpn"],
    "mobile_lines": ["sim", "sims", "mobile line", "mobile lines", "phone line", "postpaid"],
    "phone_system": ["phone system", "ivr", "landline", "intercom", "reception phone"],
    "toll_free": ["toll free", "toll-free", "1800"],
    "sms": ["sms", "text message", "text reminder"],
    "whatsapp": ["whatsapp", "व्हाट्सएप", "হোয়াটসঅ্যাপ", "வாட்ஸ்அப்", "వాట్సాప్", "ವಾಟ್ಸಾಪ್", "ਵਟਸਐਪ"],
    "email": ["email", "e-mail", "emails", "mail id"],
    "cloud_backup": ["cloud backup", "data backup", "backup of data"],
    "website": ["website", "web site", "online store"],
    "billing": ["billing", "pos", "upi", "invoice", "invoicing", "बिलिंग"],
    "device_security": ["antivirus", "device security", "laptop security"],
    "firewall": ["firewall", "cyber security", "cybersecurity"],
    "guest_wifi": ["guest wifi", "guest wi-fi", "wifi for customers", "wi-fi for customers", "wifi for guests"],
    "cctv": ["cctv", "camera", "cameras", "कैमरा", "সিসিটিভি"],
    "machine_monitoring": ["machine monitoring", "machines", "machine"],
    "vehicle_tracking": ["vehicle", "vehicles", "gps", "fleet", "delivery van"],
}
NEED_GROUP = {"internet": "internet", "backup_internet": "internet", "static_ip": "internet", "branch_network": "internet",
              "mobile_lines": "calls", "phone_system": "calls", "toll_free": "calls", "sms": "customer_chat", "whatsapp": "customer_chat",
              "email": "cloud", "cloud_backup": "cloud", "website": "cloud", "billing": "payments", "device_security": "security",
              "firewall": "security", "cctv": "security", "guest_wifi": "wifi", "machine_monitoring": "tracking", "vehicle_tracking": "tracking"}
STAFF_WORDS = r"people|persons?|staff|employees?|workers?|doctors?|dentists?|engineers?|trainers?|teachers?|lawyers?|advocates?|members?|log|लोग|कर्मचारी|स्टाफ|জন|কর্মী|பேர்|ஊழியர்|మంది|సిబ్బంది|ಜನ|ಸಿಬ್ಬಂದಿ|ਲੋਕ|ਕਰਮਚਾਰੀ|लोक"
SITE_WORDS = r"outlets|branches|locations|sites|stores|shops|offices|clinics|centres|centers|units|warehouses|ब्रांच|शाखा|आउटलेट"
CITY_ALIASES = {"bangalore": "Bengaluru", "bombay": "Mumbai", "calcutta": "Kolkata", "madras": "Chennai", "gurgaon": "Gurugram",
                "trivandrum": "Thiruvananthapuram", "baroda": "Vadodara", "poona": "Pune"}


def _has(low: str, w: str) -> bool:
    return bool(re.search(rf"\b{re.escape(w)}(?:s|es)?\b", low)) if w.isascii() else w in low


def canon_city(city) -> str | None:
    if not city:
        return None
    low = str(city).strip().lower()
    for c in data_loader.city_tiers():
        if c.lower() == low:
            return c
    return CITY_ALIASES.get(low) or (str(city).strip().title() if str(city).isascii() and re.search(r"[a-z]{3}", low) else None)


def keyword_profile(text: str) -> dict:
    """Reads type, size, sites, city, GST and needs from one sentence without the language model."""
    low = text.lower().translate(_INDIC_DIGITS)
    out: dict = {}
    for key, words in KEYWORDS.items():
        if any(_has(low, w) for w in words):
            out["business_type"] = key
            break
    sites = re.search(rf"(\d{{1,3}})\s*-?\s*(?:{SITE_WORDS})\b", low)
    if sites:
        out["num_sites"] = int(sites.group(1))
    staff = re.search(rf"(\d{{1,4}})\s*-?\s*(?:{STAFF_WORDS})", low)
    if staff:
        out["employees"] = int(staff.group(1))
        out["_staff_explicit"] = True
    else:
        nums = [m for m in re.finditer(r"(?<![\w\[])\d{1,4}(?![\w\]])", low) if not (sites and m.start() == sites.start(1))]
        if nums:
            out["employees"] = int(nums[0].group(0))
    for c in data_loader.city_tiers():
        if re.search(rf"\b{re.escape(c.lower())}\b", low):
            out["city"] = c
            break
    else:
        for a, c in CITY_ALIASES.items():
            if a in low:
                out["city"] = c
                break
    if "gst" in low or "जीएसटी" in low:
        out["gstin_status"] = "none" if _NO_GST.search(low) else "active"
    tags = [t for t, words in NEED_WORDS.items() if any(_has(low, w) for w in words)]
    if "guest_wifi" in tags and not any(_has(low, w) for w in ("internet", "broadband", "fibre", "fiber", "fast wifi", "fast wi-fi")):
        tags.remove("internet")
    out["need_tags"] = tags
    return out


def understand(text: str, lang: str, vault: dict | None = None) -> dict:
    """Everything one message says about the business, merged from the language model and the keyword reader."""
    clean = redact(text, vault if vault is not None else {})
    kw = keyword_profile(clean)
    ai = llm.parse_profile(clean, lang, list(profiles.SPECS), list(profiles.NEED_TAGS)) or {}
    out: dict = {}
    bt = ai.get("business_type") if ai.get("business_type") in profiles.SPECS else kw.get("business_type")
    if bt:
        out["business_type"] = bt
        out["segment"] = profiles.SPECS[bt].segment
    for key, lo, hi in (("employees", 1, 500), ("num_sites", 1, 50)):
        v = kw.get(key) if (key == "employees" and kw.get("_staff_explicit")) or key == "num_sites" and kw.get(key) else ai.get(key)
        if v in (None, ""):
            v = kw.get(key)
        try:
            if v not in (None, ""):
                out[key] = max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            pass
    city = canon_city(ai.get("city")) or kw.get("city")
    if city:
        out["city"] = city
    gst = ai.get("gstin_status") if ai.get("gstin_status") in ("active", "none", "unverified") else kw.get("gstin_status")
    if gst:
        out["gstin_status"] = gst
    tags = sorted({t for t in (ai.get("need_tags") or []) if t in profiles.NEED_TAGS} | set(kw.get("need_tags") or []))
    if tags:
        out["need_tags"] = tags
        out["need_groups"] = sorted({NEED_GROUP[t] for t in tags if t in NEED_GROUP})
    return out


def profile_from_text(session: dict, text: str, lang: str) -> dict | None:
    """Free text or speech to a profile."""
    parsed = understand(text, lang, session.setdefault("vault", {}))
    part = session.setdefault("partial", {})
    part.update(parsed)
    spec = profiles.SPECS.get(part.get("business_type") or "")
    if not spec:
        return {"text": _MISSING_Q["type"], "quote_card": None, "bundle": None, "chips": [], "validator": "deterministic"}
    if not part.get("employees"):
        return {"text": _MISSING_Q["employees"].format(name=spec.name), "quote_card": None, "bundle": None, "chips": [],
                "validator": "deterministic"}
    session["profile"] = {"segment": spec.segment, "business_type": spec.key, "employees": int(part["employees"]),
                          "num_sites": int(part.get("num_sites") or 1), "city": part.get("city"),
                          "gstin_status": part.get("gstin_status") or "none", "need_tags": part.get("need_tags") or []}
    session.pop("partial", None)
    return None


NEEDS_PROFILE = {
    "en": "Tell me a little about your business and I'll size a bundle: what do you run, roughly how many staff and locations, which city, and do you have a GST number?",
    "hi": "अपने व्यवसाय के बारे में थोड़ा बताइए, मैं सही बंडल तय कर दूँगा: आप क्या चलाते हैं, लगभग कितने कर्मचारी और कितनी लोकेशन हैं, कौन-सा शहर है, और क्या आपके पास GST नंबर है?",
    "ta": "உங்கள் வணிகம் பற்றி கொஞ்சம் சொல்லுங்கள், சரியான தொகுப்பை நான் பரிந்துரைக்கிறேன்: நீங்கள் என்ன நடத்துகிறீர்கள், சுமார் எத்தனை ஊழியர்கள், எத்தனை இடங்கள், எந்த நகரம், உங்களிடம் GST எண் உள்ளதா?",
    "te": "మీ వ్యాపారం గురించి కొంచెం చెప్పండి, సరైన బండిల్‌ను నేను సూచిస్తాను: మీరు ఏమి నడుపుతున్నారు, సుమారు ఎంత మంది సిబ్బంది, ఎన్ని లొకేషన్లు, ఏ నగరం, మీకు GST నంబర్ ఉందా?",
    "bn": "আপনার ব্যবসা সম্পর্কে একটু বলুন, আমি সঠিক বান্ডেল ঠিক করে দেব: আপনি কী চালান, আনুমানিক কতজন কর্মী ও কতগুলি লোকেশন, কোন শহর, আর আপনার কি GST নম্বর আছে?",
    "mr": "तुमच्या व्यवसायाबद्दल थोडे सांगा, मी योग्य बंडल ठरवतो: तुम्ही काय चालवता, साधारण किती कर्मचारी आणि किती ठिकाणे आहेत, कोणते शहर, आणि तुमच्याकडे GST क्रमांक आहे का?",
    "kn": "ನಿಮ್ಮ ವ್ಯಾಪಾರದ ಬಗ್ಗೆ ಸ್ವಲ್ಪ ಹೇಳಿ, ಸರಿಯಾದ ಬಂಡಲ್ ಅನ್ನು ನಾನು ಸೂಚಿಸುತ್ತೇನೆ: ನೀವು ಏನು ನಡೆಸುತ್ತೀರಿ, ಸುಮಾರು ಎಷ್ಟು ಸಿಬ್ಬಂದಿ ಮತ್ತು ಎಷ್ಟು ಸ್ಥಳಗಳು, ಯಾವ ನಗರ, ಮತ್ತು ನಿಮ್ಮ ಬಳಿ GST ಸಂಖ್ಯೆ ಇದೆಯೇ?",
    "pa": "ਆਪਣੇ ਕਾਰੋਬਾਰ ਬਾਰੇ ਥੋੜ੍ਹਾ ਦੱਸੋ, ਮੈਂ ਸਹੀ ਬੰਡਲ ਤੈਅ ਕਰ ਦਿਆਂਗਾ: ਤੁਸੀਂ ਕੀ ਚਲਾਉਂਦੇ ਹੋ, ਲਗਭਗ ਕਿੰਨੇ ਕਰਮਚਾਰੀ ਅਤੇ ਕਿੰਨੀਆਂ ਥਾਵਾਂ, ਕਿਹੜਾ ਸ਼ਹਿਰ, ਅਤੇ ਕੀ ਤੁਹਾਡੇ ਕੋਲ GST ਨੰਬਰ ਹੈ?",
}


def needs_profile_reply(lang: str = "en") -> dict:
    return {"text": NEEDS_PROFILE.get(lang, NEEDS_PROFILE["en"]),
            "quote_card": None, "bundle": None,
            "chips": ["Micro / retail shop", "Professional office", "Multi-site chain", "Manufacturer"],
            "validator": "deterministic"}


def run_turn(session: dict, user_text: str) -> dict:
    profile = session.get("profile")
    if profile and profile.get("segment"):
        return deterministic_reply(profile, session.get("lang", "en"))
    lang = session.get("lang", "en")
    if user_text.strip():
        asked = profile_from_text(session, user_text, lang)
        if session.get("profile"):
            return deterministic_reply(session["profile"], lang)
        if asked:
            return asked
    return needs_profile_reply(lang)
