# backend/services/ml_service.py
import math, os, re
from collections import Counter
from services.domain_utils import (get_host, registered_domain, tld_of, RISKY_TLDS,
                                   is_ip_host, has_punycode, brand_check)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.json")
KW = ["verify", "login", "secure", "account", "update", "confirm", "claim",
      "reward", "cashback", "kyc", "refund", "otp", "free", "bonus", "gift"]

FEATURE_NAMES = ["url_length", "host_length", "path_length", "dot_count", "dash_count",
                 "digit_ratio", "host_entropy", "subdomain_depth", "is_https",
                 "has_ip", "risky_tld", "has_punycode", "has_at", "keyword_hits",
                 "brand_in_host", "query_length", "special_chars",
                 "label_dashes", "label_length", "longest_label",
                 "longest_digit_run", "vowel_ratio", "tld_word_in_subdomain",
                 "keywords_in_host"]

READABLE = {
    "url_length": "The link is unusually long", "host_length": "The domain name is long",
    "path_length": "Long hidden path", "dot_count": "Too many dots",
    "dash_count": "Many dashes in the link", "digit_ratio": "Many numbers in the link",
    "host_entropy": "Domain looks random", "subdomain_depth": "Many sub-domains",
    "is_https": "Not using https", "has_ip": "Uses raw IP address",
    "risky_tld": "Cheap/abused domain ending", "has_punycode": "Look-alike characters",
    "has_at": "Contains @ trick", "keyword_hits": "Scam pressure words",
    "brand_in_host": "Fakes a known brand", "query_length": "Long query string",
    "special_chars": "Many special characters",
    "label_dashes": "Dashes inside the main domain name",
    "label_length": "Main domain name is unusually long",
    "longest_label": "One part of the domain is very long",
    "longest_digit_run": "Long run of numbers in the domain",
    "vowel_ratio": "Domain name looks unnatural",
    "tld_word_in_subdomain": "Fake 'com/net' hidden inside the domain",
    "keywords_in_host": "Scam words inside the domain",
}


def _entropy(s):
    if not s:
        return 0.0
    c = Counter(s)
    return -sum(v / len(s) * math.log2(v / len(s)) for v in c.values())


def extract_features(url: str):
    full_host = get_host(url.strip().lower())
    # Judge the REGISTERED domain only. In our training data 48% of phishing hosts have a
    # sub-domain but only 6% of the "safe" hosts do, so sub-domain shape would just teach
    # the model "sub-domain = phishing" (a data artifact). Sub-domain tricks such as
    # accounts.google.com.evil.io are caught by the rules layer instead.
    host = registered_domain(full_host) if not is_ip_host(full_host) else full_host
    # The model was TRAINED on "https://host" only, so it must be TESTED the same way.
    # (Path/query words are handled by the rules layer.)
    u = "https://" + host
    path, query = "", ""
    kind, _b = brand_check(full_host)

    reg = registered_domain(host)
    label = reg.split(".")[0] if reg else host
    parts = host.split(".") if host else [""]

    return [
        len(u), len(host), len(path), host.count("."), host.count("-"),
        sum(ch.isdigit() for ch in host) / max(len(host), 1),
        _entropy(registered_domain(host).split(".")[0]),
        max(host.count(".") - 1, 0),
        1 if u.startswith("https://") else 0,
        1 if is_ip_host(host) else 0,
        1 if tld_of(host) in RISKY_TLDS else 0,
        1 if has_punycode(host) else 0,
        1 if "@" in u else 0,
        sum(w in u for w in KW),
        1 if kind else 0,
        len(query),
        len(re.findall(r"[^a-z0-9./:\-]", u)),
        # ---- new features ----
        label.count("-"),
        len(label),
        max(len(p) for p in parts),
        max((len(m) for m in re.findall(r"\d+", host)), default=0),
        sum(c in "aeiou" for c in label) / max(len(label), 1),
        1 if any(p in ("com", "net", "org", "co", "in", "gov") for p in parts[:-2]) else 0,
        sum(w in host for w in KW),
    ]


class MLEngine:
    """Logistic regression in pure numpy: no scikit-learn / scipy needed."""

    def __init__(self):
        self.w = self.b = self.mean = self.std = self.medians = None
        self.metrics = None
        try:
            import json
            with open(MODEL_PATH, encoding="utf-8") as f:
                m = json.load(f)
            self.w = [float(v) for v in m["weights"]]
            self.b = float(m["bias"])
            self.mean = [float(v) for v in m["mean"]]
            self.std = [float(v) if float(v) > 1e-9 else 1.0 for v in m["std"]]
            self.metrics = m.get("metrics")
            # Old model.json (17 features) can't be used with the new 24 features.
            if len(self.w) != len(FEATURE_NAMES):
                self.w = None
        except Exception:
            pass  # no model file yet -> rules only

    @property
    def loaded(self):
        return self.w is not None

    def predict(self, url: str):
        x = extract_features(url)
        z = [(x[i] - self.mean[i]) / self.std[i] for i in range(len(x))]
        contrib = [self.w[i] * z[i] for i in range(len(z))]   # exact "why" per feature
        logit = sum(contrib) + self.b
        p = 1.0 / (1.0 + math.exp(-max(min(logit, 30), -30)))
        top = sorted(zip(contrib, FEATURE_NAMES), reverse=True)[:3]
        reasons = [READABLE[n] for c, n in top if c > 0.3]
        return {"probability": round(p, 4), "reasons": reasons}


ml_engine = MLEngine()