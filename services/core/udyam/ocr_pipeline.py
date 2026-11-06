"""GST certificate OCR (optional OpenCV and Tesseract)."""

import re, subprocess, tempfile, os
try:
    import cv2, numpy as np
    _CV2 = True
except Exception:
    _CV2 = False
from udyam.kyc_engine import validate_gstin
from udyam.gstin_repair import repair as repair_gstin

BLUR_MIN = 100

def available() -> bool:
    if not _CV2:
        return False
    try:
        subprocess.run(["tesseract", "--version"], capture_output=True)
        return True
    except Exception:
        return False

def quality(img_gray):
    return {"laplacian_var": float(cv2.Laplacian(img_gray, cv2.CV_64F).var()), "short_side": min(img_gray.shape)}

def remove_watermark(bgr):  # pink diagonal watermark -> white
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV); out = bgr.copy()
    out[(hsv[..., 1] > 40) & (hsv[..., 2] > 120)] = 255
    return cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)

def estimate_skew(gray):
    lines = cv2.HoughLinesP(cv2.Canny(gray, 50, 150), 1, np.pi / 720, 150, minLineLength=300, maxLineGap=10)
    angs = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in (lines.reshape(-1, 4) if lines is not None else [])]
    near = [a for a in angs if abs(a) < 15]
    return float(np.median(near)) if near else 0.0

def rotate(gray, deg):
    h, w = gray.shape; M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(gray, M, (w, h), borderValue=255)

def ocr(gray):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f: cv2.imwrite(f.name, gray)
    try: return subprocess.run(["tesseract", f.name, "-", "-l", "eng", "--psm", "6"], capture_output=True, text=True).stdout
    finally: os.unlink(f.name)

def extract_gst_certificate(path, registry_keys):
    if not available():
        raise RuntimeError("OCR path unavailable: install opencv-python-headless and the tesseract binary")
    bgr = cv2.imread(path); gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY); q = quality(gray)
    if q["laplacian_var"] < BLUR_MIN: return {"quality": q, "retake": True}
    clean = remove_watermark(bgr); est = estimate_skew(gray)
    tries = [0.0] if abs(est) < 0.5 else [est - d for d in (0, 1, 2, 3, -1, 4)]
    gstin, how, text, ang = None, "not_found", "", 0.0
    for ang in tries:
        text = ocr(rotate(clean, ang) if ang else clean)
        m = re.search(r"GSTIN\S*\s+([0-9A-Z][0-9A-Z ]{13,17})", text)
        if m:
            gstin, edits = repair_gstin(m.group(1), registry_keys)
            how = "exact" if edits == 0 else ("ocr_repaired" if edits else "no_valid_candidate")
            if how in ("exact", "ocr_repaired"): break
    return {"quality": q, "skew_deg": ang, "gstin": gstin, "gstin_source": how, "raw_text": text}
