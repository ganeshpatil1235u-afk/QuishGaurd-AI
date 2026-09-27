# backend/services/threat_api_service.py
import os
import requests
from datetime import datetime
from urllib.parse import urlparse

try:
    import whois
except ImportError:
    whois = None

class ThreatAPIService:
    def __init__(self):
        self.vt_api_key = os.getenv(
            "VIRUSTOTAL_API_KEY", "YOUR_VIRUSTOTAL_API_KEY"
        )
        print("✅ Threat API Service ready (VirusTotal + WHOIS)")

    def check_virustotal(self, url: str) -> dict:
        if not url or not url.startswith("http"):
            return {
                "service": "VirusTotal v3",
                "malicious_votes": 0,
                "flagged": False,
                "threat_score": 0.0,
                "note": "skipped_non_http",
            }
        if self.vt_api_key in ("", "YOUR_VIRUSTOTAL_API_KEY"):
            return self._vt_heuristic(url)

        headers = {"x-apikey": self.vt_api_key}
        try:
            r = requests.post(
                "https://www.virustotal.com/api/v3/urls",
                data={"url": url},
                headers=headers,
                timeout=8,
            )
            if r.status_code not in (200, 201):
                return self._vt_heuristic(url)
            analysis_id = r.json()["data"]["id"]
            a = requests.get(
                f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                headers=headers,
                timeout=8,
            )
            if a.status_code != 200:
                return self._vt_heuristic(url)
            stats = a.json()["data"]["attributes"].get("stats", {})
            malicious = int(stats.get("malicious", 0) or 0)
            suspicious = int(stats.get("suspicious", 0) or 0)
            total = sum(int(v or 0) for v in stats.values()) or 1
            score = min(
                (malicious * 20.0) + (suspicious * 8.0), 100.0
            )
            return {
                "service": "VirusTotal v3 API",
                "malicious_votes": malicious,
                "suspicious_votes": suspicious,
                "total_scanners": total,
                "flagged": malicious > 0 or suspicious > 2,
                "threat_score": round(score, 1),
            }
        except Exception as e:
            out = self._vt_heuristic(url)
            out["error"] = str(e)
            return out

    def _vt_heuristic(self, url: str) -> dict:
        u = url.lower()
        bad = any(x in u for x in [
            ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz",
            "verify", "claim", "reward",
            "cashback", "secure-login",
        ])
        return {
            "service": "VirusTotal v3 (heuristic mode)",
            "malicious_votes": 5 if bad else 0,
            "flagged": bad,
            "threat_score": 75.0 if bad else 5.0,
            "note": "Set VIRUSTOTAL_API_KEY for live API",
        }

    def check_whois(self, url: str) -> dict:
        try:
            if not url.startswith("http"):
                url = "http://" + url
            domain = (
                urlparse(url)
                .netloc
                .replace("www.", "")
                .split(":")[0]
            )
            if not domain:
                return {
                    "domain": "unknown",
                    "age_days": None,
                    "risk_score": 20.0,
                    "is_zero_day": False,
                }
            free_tlds = {
                "tk", "ml", "ga", "cf", "gq",
                "xyz", "top", "buzz", "click", "link"
            }
            tld = domain.split(".")[-1].lower()
            is_free = tld in free_tlds
            age_days = None
            registrar = None

            if whois is not None:
                try:
                    w = whois.whois(domain)
                    creation = w.creation_date
                    if isinstance(creation, list):
                        creation = creation[0] if creation else None
                    if creation:
                        age_days = max(
                            0, (datetime.now() - creation).days
                        )
                    registrar = (
                        str(w.registrar)
                        if getattr(w, "registrar", None)
                        else None
                    )
                except Exception:
                    pass

            if age_days is None:
                age_days = 3 if is_free else 400

            if age_days < 7:
                risk, label = 90.0, "CRITICAL"
            elif age_days < 30:
                risk, label = 65.0, "HIGH"
            elif age_days < 90:
                risk, label = 35.0, "MEDIUM"
            elif age_days < 365:
                risk, label = 15.0, "LOW"
            else:
                risk, label = 5.0, "SAFE"

            if is_free:
                risk = min(risk + 15.0, 100.0)

            return {
                "domain": domain,
                "registrar": registrar,
                "age_days": age_days,
                "is_free_tld": is_free,
                "is_zero_day": age_days < 14,
                "age_risk": label,
                "risk_score": round(risk, 1),
            }
        except Exception as e:
            return {
                "domain": "unknown",
                "age_days": None,
                "is_zero_day": False,
                "risk_score": 25.0,
                "error": str(e),
            }

threat_api_service = ThreatAPIService()
