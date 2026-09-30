# backend/tests/test_engine.py   run:  python -m pytest tests -q   (or: python tests/test_engine.py)
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.hf_service import hf_engine
from services.upi_service import upi_engine

BAD = ["https://accounts.google.com.evil.io/verify", "https://paytm-kyc-verify.xyz/login",
       "https://xn--pypal-4ve.com", "http://192.168.5.4/pay", "https://paytmm.com/offer",
       "https://g00gle.com/login", "https://sbi-website.info", "http://bit.ly/claim-reward"]
GOOD = ["https://www.google.com", "https://github.com/anthropics", "https://www.taxi.com",
        "https://pay.google.com", "https://www.paytm.com/recharge", "https://www.irctc.co.in"]

def test_bad_urls_flagged():
    for u in BAD:
        assert hf_engine.predict_url_threat(u)["phishing_probability"] > 0.4, u

def test_good_urls_safe():
    for u in GOOD:
        assert hf_engine.predict_url_threat(u)["phishing_probability"] < 0.3, u

def test_upi_receive_scam():
    r = upi_engine.analyze_upi_payload("upi://pay?pa=x@ybl&pn=Prize&am=500", "Scan to RECEIVE Rs 500")
    assert r["upi_risk_score"] >= 50

def test_upi_safe():
    r = upi_engine.analyze_upi_payload("upi://pay?pa=9876543210@ybl&pn=Ravi%20Kumar", "Pay here")
    assert r["upi_risk_score"] < 20

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
