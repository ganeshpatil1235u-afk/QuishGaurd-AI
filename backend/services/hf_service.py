# backend/services/hf_service.py
import re

class HuggingFacePhishingEngine:
    def __init__(self):
        print("🧠 Loading HuggingFace engine...")
        self.loaded = False
        self.classifier = None
        try:
            from transformers import pipeline
            # Use a better model for URL classification
            self.classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",  # Better than DistilBERT for this
            )
            self.loaded = True
            print("✅ HuggingFace BART-MNLI ready")
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

        # 🔥 KEY FIX: Convert URL to descriptive text
        clean = self._url_to_descriptive_text(url)
        
        # 🔥 IMPROVED LABELS: Clear opposites
        labels = [
            "safe legitimate trusted website",
            "phishing scam fraud malicious",
        ]
        
        try:
            result = self.classifier(clean, candidate_labels=labels)
            
            # Get phishing label score
            phish_label = "phishing scam fraud malicious"
            idx = result["labels"].index(phish_label)
            prob = float(result["scores"][idx])
            
            # 🔥 LOWERED THRESHOLD: 0.45 instead of 0.55
            # BART-MNLI typically gives lower confidence for zero-shot
            is_phishing = prob > 0.45
            
            return {
                "model": "HuggingFace BART-MNLI Zero-Shot",
                "phishing_probability": round(prob, 4),
                "is_phishing": is_phishing,
                "confidence": round(max(result["scores"]) * 100, 1),
                "debug_scores": {
                    "safe": round(result["scores"][1-idx], 4),
                    "phishing": round(prob, 4),
                }
            }
        except Exception as e:
            print(f"HF prediction failed: {e}")
            return self._heuristic(url)

    def _url_to_descriptive_text(self, url: str) -> str:
        """
        🔥 KEY FIX: Convert URL to natural language description
        Example: 
          http://paytm-verify.tk/claim 
          → "website paytm verify domain tk path claim"
        """
        # Remove protocol
        clean = re.sub(r"https?://", "", url.lower())
        
        # Split domain and path
        parts = clean.replace("www.", "").split("/")
        domain = parts[0] if parts else ""
        path = " ".join(parts[1:]) if len(parts) > 1 else ""
        
        # Extract meaningful tokens from domain
        domain_tokens = re.sub(r"[.\-_]", " ", domain)
        
        # Combine into descriptive sentence
        description = f"website {domain_tokens}"
        if path:
            path_tokens = re.sub(r"[.\-_?=&]", " ", path)
            description += f" path {path_tokens}"
        
        # Add red flags as explicit features
        red_flags = []
        if any(tld in domain for tld in [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz"]):
            red_flags.append("free domain")
        if any(word in clean for word in ["verify", "login", "secure", "claim", "reward"]):
            red_flags.append("suspicious keywords")
        if url.startswith("http://"):
            red_flags.append("insecure http")
        
        if red_flags:
            description += " has " + " and ".join(red_flags)
        
        return description

    def _heuristic(self, url: str) -> dict:
        """Fallback rule-based scoring when HF model unavailable"""
        u = url.lower()
        score = 0.10
        
        # Free TLDs (very high risk)
        if any(t in u for t in [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".buzz", ".click"]):
            score += 0.40
        
        # Brand impersonation
        if any(b in u for b in ["paytm", "phonepe", "gpay", "sbi", "hdfc", "icici", "amazon", "flipkart"]):
            score += 0.30
        
        # Suspicious keywords
        if any(w in u for w in ["verify", "login", "secure", "claim", "reward", "cashback", "update", "confirm"]):
            score += 0.25
        
        # HTTP (not HTTPS)
        if u.startswith("http://"):
            score += 0.15
        
        # Excessive hyphens (e.g., paytm-verify-secure-login)
        if u.count("-") >= 3:
            score += 0.10
        
        score = min(score, 0.99)
        
        return {
            "model": "HuggingFace Engine (Heuristic Fallback)",
            "phishing_probability": round(score, 4),
            "is_phishing": score > 0.55,
            "confidence": round(score * 100, 1),
        }

hf_engine = HuggingFacePhishingEngine()
