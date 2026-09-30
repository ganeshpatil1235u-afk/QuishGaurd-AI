# backend/main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid

from services.vision_service import vision_engine
from services.hf_service import hf_engine
from services.upi_service import upi_engine
from services.threat_api_service import threat_api_service
from services.redirect_service import follow_redirects
from services.domain_utils import is_trusted, get_host
import time, collections

ENGINE_VERSION = "3.0.0"

app = FastAPI(title="QuishGuard AI", version=ENGINE_VERSION)

# FIX: "*" with allow_credentials=True is rejected by browsers -> credentials=False
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_B64_CHARS = 6_000_000  # FIX: ~4.5MB cap, unbounded base64 = crash


class ScanRequest(BaseModel):
    qr_image_base64: Optional[str] = None
    qr_decoded_text: Optional[str] = None
    context_text: Optional[str] = None
    scan_source: str = "unknown"


@app.get("/")
def root():
    return {"service": "QuishGuard AI", "health": "/api/health", "docs": "/docs"}


# NOTE: the Flutter app now calls the /api/v2/* routes. An OLD backend does not
# have them, so the app will show "old backend" instead of silently using old logic.
@app.get("/api/health")
@app.get("/api/v2/health")
def health():
    return {
        "status": "healthy",
        "service": "QuishGuard AI",
        "stack": ["FastAPI", "OpenCV", "HuggingFace", "VirusTotal", "WHOIS"],
        "version": ENGINE_VERSION,
    }


_HITS = collections.defaultdict(list)


def rate_limit(ip: str, limit: int = 30, window: int = 60):
    now = time.time()
    _HITS[ip] = [t for t in _HITS[ip] if now - t < window]
    if len(_HITS[ip]) >= limit:
        raise HTTPException(status_code=429, detail="Too many scans. Wait a minute.")
    _HITS[ip].append(now)


# ---- which app should open this QR? (the Flutter app just obeys these fields) ----
_APP_BY_DOMAIN = {
    "whatsapp": ("WhatsApp", {"wa.me", "whatsapp.com"}),
    "telegram": ("Telegram", {"t.me", "telegram.me", "telegram.org"}),
    "instagram": ("Instagram", {"instagram.com"}),
    "facebook": ("Facebook", {"facebook.com", "fb.com", "fb.me"}),
    "youtube": ("YouTube", {"youtube.com", "youtu.be"}),
    "linkedin": ("LinkedIn", {"linkedin.com"}),
    "playstore": ("Play Store", {"play.google.com"}),
    "form": ("Form", {"forms.gle"}),
}


def classify_target(payload: str, is_upi: bool, is_url: bool):
    low = payload.lower().strip()
    if is_upi:
        return {"category": "payment", "label": "Payment App"}
    if low.startswith("mailto:"):
        return {"category": "email", "label": "Email"}
    if low.startswith("tel:"):
        return {"category": "phone", "label": "Phone"}
    if low.startswith(("sms:", "smsto:")):
        return {"category": "sms", "label": "Messages"}
    if is_url:
        host = get_host(low if "//" in low else "https://" + low)
        reg = ".".join(host.split(".")[-2:])
        for cat, (label, domains) in _APP_BY_DOMAIN.items():
            if reg in domains:
                return {"category": cat, "label": label}
        if "google." in host and ("/maps" in low or host.startswith("maps.")):
            return {"category": "maps", "label": "Maps"}
        if host == "docs.google.com" and "/forms" in low:
            return {"category": "form", "label": "Form"}
        return {"category": "browser", "label": "Browser"}
    return {"category": "text", "label": "Text"}


@app.post("/api/scan")
@app.post("/api/v2/scan")
def scan(request: ScanRequest, http_request: Request):
    rate_limit(http_request.client.host if http_request.client else "x")
    # FIX: plain `def` (NOT async) — FastAPI runs sync endpoints in a
    # threadpool, so slow WHOIS/VirusTotal calls don't freeze the server.
    if request.qr_image_base64 and len(request.qr_image_base64) > MAX_B64_CHARS:
        raise HTTPException(status_code=413, detail="Image too large (max ~4MB)")

    decoded_text = request.qr_decoded_text
    vision_meta = None

    if not decoded_text and request.qr_image_base64:
        v = vision_engine.preprocess_and_decode(request.qr_image_base64)
        if not v.get("success"):
            raise HTTPException(status_code=400, detail=v.get("error", "QR decode failed"))
        decoded_text = v["decoded_text"]
        vision_meta = v

    if not decoded_text or not str(decoded_text).strip():
        raise HTTPException(status_code=400, detail="Provide qr_decoded_text or qr_image_base64")

    decoded_text = str(decoded_text).strip()
    lower = decoded_text.lower()
    is_upi = lower.startswith("upi://")
    is_url = lower.startswith(("http://", "https://")) or (
        "." in decoded_text and " " not in decoded_text and not is_upi
    )

    url_for_intel = decoded_text
    if is_url and not lower.startswith("http"):
        url_for_intel = "https://" + decoded_text

    redirect_res = {"hops": 0, "final_url": url_for_intel, "chain": [url_for_intel]}
    if is_url and not is_upi:
        redirect_res = follow_redirects(url_for_intel)
        url_for_intel = redirect_res["final_url"]      # judge the REAL destination

    upi_res = (upi_engine.analyze_upi_payload(decoded_text, request.context_text)
               if is_upi else {"is_upi": False})
    hf_res = (hf_engine.predict_url_threat(url_for_intel)
              if is_url else {"phishing_probability": 0.0, "is_phishing": False, "model": "skipped"})
    vt_res = (threat_api_service.check_virustotal(url_for_intel)
              if is_url else {"threat_score": 0.0, "flagged": False, "service": "skipped"})
    whois_res = (threat_api_service.check_whois(url_for_intel)
                 if is_url else {"risk_score": 0.0, "age_days": None, "is_zero_day": False})

    # FIX: normalize HF probability to 0-100 FIRST, then weight (old code
    # mixed a 0-1 value *40 with 0-100 values *0.35 — confusing & fragile)
    hf_pct = float(hf_res.get("phishing_probability", 0)) * 100.0

    if is_upi and not is_url:
        score = float(upi_res.get("upi_risk_score", 0))
    elif is_url and not is_upi:
        score = hf_pct * 0.45 + float(whois_res.get("risk_score", 0)) * 0.30 \
              + float(vt_res.get("threat_score", 0)) * 0.25
    else:
        score = max(float(upi_res.get("upi_risk_score", 0)), hf_pct * 0.50)

    # tampered-QR signals from OpenCV push the score up
    tamper = (vision_meta or {}).get("tamper_signals", [])
    if tamper:
        score = max(score, 50.0) + 10.0 * len(tamper)
    if redirect_res.get("hops", 0) >= 3:
        score += 10.0
    score = round(min(max(score, 0.0), 100.0), 1)

    if score >= 75:
        risk, verdict = "CRITICAL", "🚨 CRITICAL THREAT. Do NOT proceed."
    elif score >= 45:
        risk, verdict = "HIGH", "⚠️ HIGH RISK. Suspicious signals detected."
    elif score >= 20:
        risk, verdict = "MEDIUM", "⚡ MEDIUM RISK. Verify source before continuing."
    else:
        risk, verdict = "SAFE", "✅ SAFE. No strong malicious indicators."

    if is_upi and upi_res.get("risks"):
        crit = [r for r in upi_res["risks"] if r.get("severity") == "CRITICAL"]
        if crit:
            verdict = "🚨 " + crit[0]["detail"]

    # Safe UPI payment QR -> app is allowed to hand off to PhonePe
    safe_upi = is_upi and not is_url and risk == "SAFE"
    if safe_upi:
        who = upi_res.get("payee_name", "Unknown")
        via = upi_res.get("known_psp")
        verdict = (f"✅ SAFE. Payee: {who} ({upi_res.get('payee_vpa')})"
                   + (f" on {via}." if via else "."))

    target_app = classify_target(decoded_text, is_upi, is_url)
    openable = target_app["category"] != "text"
    auto_open = openable and risk == "SAFE"        # SAFE   -> normal button
    manual_open = openable and risk == "MEDIUM"    # MEDIUM -> "anyway, at your risk"
    # HIGH / CRITICAL -> neither: the app shows no open button at all

    print(f"[SCAN] type={'UPI' if is_upi else 'OTHER'} score={score} "
          f"risk={risk} payload={decoded_text[:80]}")

    return {
        "engine_version": ENGINE_VERSION,
        "scan_id": str(uuid.uuid4()),
        "threat_score": score,
        "risk_level": risk,
        "decoded_payload": decoded_text,
        "payload_type": "UPI" if is_upi else ("URL" if is_url else "TEXT"),
        "verdict": verdict,
        "recommendation": ("DO NOT PROCEED. Report this QR."
                           if risk in ("CRITICAL", "HIGH")
                           else ("Verify the payee name in PhonePe before entering your PIN."
                                 if safe_upi else "Proceed with normal caution.")),
        # Flutter app uses this flag to decide whether to open PhonePe
        "redirect_to_phonepe": safe_upi,      # kept for older app versions
        "target_app": target_app,
        "auto_open_allowed": auto_open,
        "manual_open_allowed": manual_open,
        "reasons": (hf_res.get("reasons", []) + [t["detail"] for t in tamper]),
        "analysis": {
            "opencv_vision": vision_meta,
            "redirects": redirect_res,
            "upi_analysis": upi_res,
            "huggingface_ai": hf_res,
            "virustotal_api": vt_res,
            "whois_api": whois_res,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),  # FIX: utcnow() deprecated
        "scan_source": request.scan_source,
    }


if __name__ == "__main__":
    import uvicorn
    print(f"[QuishGuard] main.py v{ENGINE_VERSION} loaded from: {__file__}")
    # reload=False so no background reloader process can keep serving old code
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)