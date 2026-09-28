# backend/services/hf_service.py
import re
from urllib.parse import urlparse


class HuggingFacePhishingEngine:
    def __init__(self):
        # FIX: lazy load — old code downloaded torch at import time,
        # making the API take minutes to boot (or crash without torch)
        print("🧠 HF engine ready (heuristic-first, lazy ML)")
        self._classifier = None
        self._load_attempted = False

    def _load_model(self):
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            from transformers import pipeline
            self._classifier = pipeline(
                "text-classification",
                model="madhurjindal/autonlp-Gibberish-Detector-492513457",
                max_length=512,
                truncation=True,
            )
            print("✅ HF model loaded")
        except Exception as e:
            print(f"⚠️ HF model unavailable ({e}). Heuristic-only mode.")
            self._classifier = None

    @property
    def loaded(self):
        return self._classifier is not None

    def predict_url_threat(self, url: str) -> dict:
        if not url:
            return {"model": "none", "phishing_probability": 0.0,
                    "is_phishing": False, "confidence": 0.0}

        heuristic_result = self._advanced_heuristic(url)
        if heuristic_result["phishing_probability"] > 0.7:
            return heuristic_result

        self._load_model()
        if self.loaded:
            try:
                ml_result = self._ml_check(url)
                final_prob = max(heuristic_result["phishing_probability"],
                                 ml_result.get("phishing_probability", 0))
                return {
                    "model": "HuggingFace + Advanced Heuristics (Hybrid)",
                    "phishing_probability": round(final_prob, 4),
                    "is_phishing": final_prob > 0.50,
                    "confidence": round(final_prob * 100, 1),
                    "heuristic_score": heuristic_result["phishing_probability"],
                    "ml_score": ml_result.get("phishing_probability", 0),
                }
            except Exception as e:
                print(f"ML check failed: {e}")
        return heuristic_result

    def _ml_check(self, url: str) -> dict:
        try:
            result = self._classifier(url[:200])
            label = result[0]["label"].lower()
            score = float(result[0]["score"])
            if "gibberish" in label or "noise" in label:
                return {"phishing_probability": score}
            return {"phishing_probability": 1.0 - score}
        except Exception:
            return {"phishing_probability": 0.0}

    def _advanced_heuristic(self, url: str) -> dict:
        u = url.lower()
        score, flags = 0.0, []
        try:
            host = urlparse(u if "//" in u else "https://" + u).netloc.replace("www.", "")
        except Exception:
            host = u

        free_tlds = [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top",
                     ".buzz", ".click", ".link", ".pw", ".cc", ".info", ".club"]
        if any(t in u for t in free_tlds):
            score += 0.50
            flags.append("FREE_TLD")

        # FIX: don't flag the brand's OWN official domain as impersonation
        official_domains = {
            "paytm": ["paytm.com", "paytm.in", "paytmpay.com"],
            "phonepe": ["phonepe.com", "phone.pe"],
            "gpay": ["pay.google.com", "google.com"],
            "googlepay": ["pay.google.com", "google.com"],
            "amazon": ["amazon.com", "amazon.in", "amzn.to", "amazonaws.com"],
            "flipkart": ["flipkart.com"],
            "sbi": ["sbi.co.in", "onlinesbi.com"],
            "hdfc": ["hdfcbank.com", "hdfc.com"],
            "icici": ["icicibank.com", "icici.com"],
            "axis": ["axisbank.com"],
        }
        for brand, domains in official_domains.items():
            if brand in u:
                if any(host == d or host.endswith("." + d) for d in domains):
                    break  # legitimate site — no flag
                score += 0.35
                flags.append(f"BRAND_IMPERSONATION:{brand}")
                break

        suspicious_words = ["verify", "login", "secure", "account", "update",
                            "confirm", "billing", "suspended", "claim", "reward",
                            "prize", "cashback", "winner", "congratulation",
                            "click", "urgent"]
        if any(w in u for w in suspicious_words):
            score += 0.25
            flags.append("SUSPICIOUS_KEYWORDS")

        if u.startswith("http://") and not u.startswith("http://localhost"):
            score += 0.15
            flags.append("INSECURE_HTTP")

        if u.count("-") >= 3 or u.count(".") >= 5:
            score += 0.10
            flags.append("EXCESSIVE_SEPARATORS")

        if re.search(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", u):
            score += 0.40
            flags.append("IP_ADDRESS_URL")

        if re.search(r":\d{4,5}(?:/|$)", u) and ":8000" not in u and ":3000" not in u:
            score += 0.20
            flags.append("NON_STANDARD_PORT")

        shorteners = ["bit.ly", "tinyurl", "goo.gl", "ow.ly", "t.co",
                      "is.gd", "buff.ly", "adf.ly"]
        if any(s in u for s in shorteners):
            score += 0.30
            flags.append("URL_SHORTENER")

        trusted = ["google.com", "youtube.com", "wikipedia.org",
                   "github.com", "microsoft.com"]
        if any(t in host for t in trusted):
            score = max(0, score - 0.60)
            flags.append("TRUSTED_DOMAIN")

        if u.startswith("https://"):
            score = max(0, score - 0.05)

        score = min(max(score, 0.0), 0.99)
        return {
            "model": "Advanced Heuristic Engine v2.1",
            "phishing_probability": round(score, 4),
            "is_phishing": score > 0.50,
            "confidence": round(score * 100, 1),
            "detected_flags": flags,
            "flag_count": len(flags),
        }


hf_engine = HuggingFacePhishingEngine()
