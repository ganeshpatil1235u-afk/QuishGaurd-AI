# backend/services/hf_service.py
import re

class HuggingFacePhishingEngine:
    def __init__(self):
        print("🧠 Loading HuggingFace engine...")
        self.loaded = False
        self.classifier = None
        try:
            from transformers import pipeline
            self.classifier = pipeline(
                "zero-shot-classification",
                model="typeform/distilbert-base-uncased-mnli",
            )
            self.loaded = True
            print("✅ HuggingFace DistilBERT ready")
        except Exception as e:
            print(f"⚠️ HF load failed ({e}). Using heuristic fallback.")
            self.loaded = False

    def predict_url_threat(self, url: str) -> dict:
        if not url:
            return {
                "model": "none",
                "phishing_probability": 0.0,
                "is_phishing": False,
                "confidence": 0.0,
            }
        if not self.loaded:
            return self._heuristic(url)

        clean = re.sub(r"https?://", "", url)
        clean = (
            clean
            .replace("/", " ")
            .replace("-", " ")
            .replace(".", " ")
            .replace("?", " ")
        )
        labels = [
            "legitimate official secure website",
            "scam phishing fraudulent spoofed website",
        ]
        try:
            result = self.classifier(clean, candidate_labels=labels)
            phish = "scam phishing fraudulent spoofed website"
            idx = result["labels"].index(phish)
            prob = float(result["scores"][idx])
            return {
                "model": "HuggingFace DistilBERT Zero-Shot",
                "phishing_probability": round(prob, 4),
                "is_phishing": prob > 0.55,
                "confidence": round(max(result["scores"]) * 100, 1),
            }
        except Exception:
            return self._heuristic(url)

    def _heuristic(self, url: str) -> dict:
        u = url.lower()
        score = 0.10
        if any(t in u for t in [
            ".tk", ".ml", ".ga", ".cf", ".gq",
            ".xyz", ".top", ".buzz", ".click"
        ]):
            score += 0.35
        if any(b in u for b in [
            "paytm", "phonepe", "gpay", "sbi",
            "hdfc", "icici", "amazon", "flipkart"
        ]):
            score += 0.25
        if any(w in u for w in [
            "verify", "login", "secure", "claim",
            "reward", "cashback", "update"
        ]):
            score += 0.20
        if u.startswith("http://"):
            score += 0.10
        score = min(score, 0.99)
        return {
            "model": "HuggingFace Engine (Heuristic Fallback)",
            "phishing_probability": round(score, 4),
            "is_phishing": score > 0.55,
            "confidence": round(score * 100, 1),
        }

hf_engine = HuggingFacePhishingEngine()
