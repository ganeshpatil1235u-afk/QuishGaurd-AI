# backend/services/hf_service.py  (REPLACES the old file)
# Name kept so main.py does not change. It is now: strong rules + trained ML model.
import re
from services.domain_utils import (get_host, registered_domain, tld_of, RISKY_TLDS,
                                   is_trusted, is_ip_host, has_punycode,
                                   has_non_ascii, brand_check)

KEYWORDS = ["verify", "login", "secure", "account", "update", "confirm", "billing",
            "suspended", "claim", "reward", "prize", "cashback", "winner", "kyc",
            "urgent", "refund", "otp", "blocked"]
SHORTENERS = {"bit.ly", "tinyurl.com", "goo.gl", "ow.ly", "t.co", "is.gd",
              "buff.ly", "adf.ly", "cutt.ly", "rb.gy", "shorturl.at"}


class PhishingEngine:
    def __init__(self):
        from services.ml_service import ml_engine
        self.ml = ml_engine
        print("🧠 Phishing engine ready (rules + ML:",
              "ON" if self.ml.loaded else "OFF - run ml/train_model.py", ")")

    def rules(self, url: str) -> dict:
        u = url.lower()
        host = get_host(u)
        reg = registered_domain(host)
        score, flags, reasons = 0.0, [], []

        def add(p, flag, why):
            nonlocal score
            score += p; flags.append(flag); reasons.append(why)

        if is_trusted(host):
            return {"score": 0.0, "flags": ["TRUSTED_DOMAIN"], "reasons": [],
                    "host": host, "registered_domain": reg}

        if tld_of(host) in RISKY_TLDS:
            add(0.40, "RISKY_TLD", f"Domain ends in .{tld_of(host)} (cheap/abused)")
        kind, brand = brand_check(host)
        if kind == "IMPERSONATION":
            add(0.45, "BRAND_IMPERSONATION", f"Uses the name '{brand}' but is NOT the real {brand} site")
        elif kind == "LOOKALIKE":
            add(0.55, "LOOKALIKE_DOMAIN", f"Looks like '{brand}' with tiny spelling tricks")
        if has_punycode(host) or has_non_ascii(host):
            add(0.45, "HOMOGRAPH", "Uses look-alike foreign characters (punycode)")
        if is_ip_host(host):
            add(0.45, "IP_ADDRESS_URL", "Link uses a raw IP address, not a name")
        if reg in SHORTENERS:
            add(0.25, "URL_SHORTENER", "Shortened link hides the real destination")
        hits = [w for w in KEYWORDS if w in u]
        if hits:
            add(min(0.10 + 0.05 * len(hits), 0.25), "SUSPICIOUS_KEYWORDS",
                "Pressure words: " + ", ".join(hits[:3]))
        if u.startswith("http://"):
            add(0.15, "INSECURE_HTTP", "Not encrypted (http, not https)")
        if host.count(".") >= 4 or host.count("-") >= 3:
            add(0.10, "EXCESSIVE_SEPARATORS", "Too many dots/dashes in the domain")
        if "@" in u.split("?")[0].split("//", 1)[-1].split("/")[0]:
            add(0.30, "AT_SYMBOL_TRICK", "Contains '@' to fake the real host")
        return {"score": min(score, 0.99), "flags": flags, "reasons": reasons,
                "host": host, "registered_domain": reg}

    def predict_url_threat(self, url: str) -> dict:
        if not url:
            return {"model": "none", "phishing_probability": 0.0, "is_phishing": False}
        r = self.rules(url)
        ml = self.ml.predict(url) if self.ml.loaded else None
        if ml is None:
            prob, model = r["score"], "Rules engine v3"
        elif "TRUSTED_DOMAIN" in r["flags"]:
            prob, model = 0.0, "Rules + ML (trusted domain)"
        else:
            # blend: rules catch known tricks, ML catches unknown patterns
            prob, model = max(r["score"], 0.5 * r["score"] + 0.5 * ml["probability"]), "Rules + ML hybrid"
        prob = round(min(max(prob, 0.0), 0.99), 4)
        return {
            "model": model,
            "phishing_probability": prob,
            "is_phishing": prob > 0.5,
            "confidence": round(prob * 100, 1),
            "detected_flags": r["flags"],
            "reasons": r["reasons"] + (ml["reasons"] if ml else []),
            "ml_probability": ml["probability"] if ml else None,
            "rule_score": r["score"],
            "registered_domain": r["registered_domain"],
        }


hf_engine = PhishingEngine()
