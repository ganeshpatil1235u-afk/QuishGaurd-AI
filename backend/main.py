# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from services.vision_service import vision_engine
from services.hf_service import hf_engine
from services.upi_service import upi_engine
from services.threat_api_service import threat_api_service

app = FastAPI(title="QuishGuard AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScanRequest(BaseModel):
    qr_image_base64: Optional[str] = None
    qr_decoded_text: Optional[str] = None
    context_text: Optional[str] = None
    scan_source: str = "unknown"

@app.get("/")
def root():
    return {
        "service": "QuishGuard AI",
        "health": "/api/health",
        "docs": "/docs"
    }

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "QuishGuard AI",
        "stack": [
            "FastAPI",
            "OpenCV",
            "HuggingFace",
            "VirusTotal",
            "WHOIS"
        ],
        "version": "2.0.0",
    }

@app.post("/api/scan")
async def scan(request: ScanRequest):
    decoded_text = request.qr_decoded_text
    vision_meta = None

    # Step 1: OpenCV decode if image provided
    if not decoded_text and request.qr_image_base64:
        v = vision_engine.preprocess_and_decode(request.qr_image_base64)
        if not v.get("success"):
            raise HTTPException(
                status_code=400,
                detail=v.get("error", "QR decode failed")
            )
        decoded_text = v["decoded_text"]
        vision_meta = v

    if not decoded_text or not str(decoded_text).strip():
        raise HTTPException(
            status_code=400,
            detail="Provide qr_decoded_text or qr_image_base64"
        )

    decoded_text = str(decoded_text).strip()
    is_upi = decoded_text.lower().startswith("upi://")
    is_url = decoded_text.lower().startswith(("http://", "https://")) or (
        "." in decoded_text
        and " " not in decoded_text
        and not is_upi
    )

    url_for_intel = decoded_text
    if is_url and not decoded_text.lower().startswith("http"):
        url_for_intel = "https://" + decoded_text

    # Step 2: Run all engines
    upi_res = (
        upi_engine.analyze_upi_payload(
            decoded_text, request.context_text
        )
        if is_upi
        else {"is_upi": False}
    )
    hf_res = (
        hf_engine.predict_url_threat(url_for_intel)
        if is_url
        else {
            "phishing_probability": 0.0,
            "is_phishing": False,
            "model": "skipped"
        }
    )
    vt_res = (
        threat_api_service.check_virustotal(url_for_intel)
        if is_url
        else {
            "threat_score": 0.0,
            "flagged": False,
            "service": "skipped"
        }
    )
    whois_res = (
        threat_api_service.check_whois(url_for_intel)
        if is_url
        else {
            "risk_score": 0.0,
            "age_days": None,
            "is_zero_day": False
        }
    )

    # Step 3: Composite score
    if is_upi and not is_url:
        score = float(upi_res.get("upi_risk_score", 0))
    elif is_url and not is_upi:
        score = (
            float(hf_res.get("phishing_probability", 0)) * 40.0
            + float(whois_res.get("risk_score", 0)) * 0.35
            + float(vt_res.get("threat_score", 0)) * 0.25
        )
    else:
        score = max(
            float(upi_res.get("upi_risk_score", 0)),
            float(hf_res.get("phishing_probability", 0)) * 50.0,
        )

    score = round(min(max(score, 0.0), 100.0), 1)

    if score >= 75:
        risk = "CRITICAL"
        verdict = "🚨 CRITICAL THREAT. Do NOT proceed."
    elif score >= 45:
        risk = "HIGH"
        verdict = "⚠️ HIGH RISK. Suspicious signals detected."
    elif score >= 20:
        risk = "MEDIUM"
        verdict = "⚡ MEDIUM RISK. Verify source before continuing."
    else:
        risk = "SAFE"
        verdict = "✅ SAFE. No strong malicious indicators."

    if is_upi and upi_res.get("risks"):
        crit = [
            r for r in upi_res["risks"]
            if r.get("severity") == "CRITICAL"
        ]
        if crit:
            verdict = "🚨 " + crit[0]["detail"]

    return {
        "scan_id": str(uuid.uuid4()),
        "threat_score": score,
        "risk_level": risk,
        "decoded_payload": decoded_text,
        "payload_type": (
            "UPI" if is_upi else ("URL" if is_url else "TEXT")
        ),
        "verdict": verdict,
        "recommendation": (
            "DO NOT PROCEED. Report this QR."
            if risk in ("CRITICAL", "HIGH")
            else "Proceed with normal caution."
        ),
        "analysis": {
            "opencv_vision": vision_meta,
            "upi_analysis": upi_res,
            "huggingface_ai": hf_res,
            "virustotal_api": vt_res,
            "whois_api": whois_res,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "scan_source": request.scan_source,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
