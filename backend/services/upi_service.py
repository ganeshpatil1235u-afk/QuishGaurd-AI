# backend/services/upi_service.py
from urllib.parse import urlparse, parse_qs
import re

class UPIIntentEngine:
    KNOWN_SCAM_PATTERNS = [
        r"^test\d*@",
        r"^temp\d*@",
        r"^scam",
        r"^fraud",
        r"^fake",
        r"^[a-z]{18,}@",
        r"^\d{10,}@",
    ]

    def analyze_upi_payload(
        self, upi_string: str, context_text: str = None
    ) -> dict:
        if not upi_string or not upi_string.strip().lower().startswith("upi://"):
            return {"is_upi": False}

        parsed = urlparse(upi_string.strip())
        params = parse_qs(parsed.query)
        payee_vpa = params.get("pa", [None])[0]
        payee_name = params.get("pn", ["Unknown"])[0]
        note = params.get("tn", [""])[0]
        try:
            amount = float(params.get("am", ["0"])[0] or 0)
        except ValueError:
            amount = 0.0

        risks = []
        risk_score = 0

        # KILLER FEATURE: Pay vs Receive mismatch
        if context_text and amount > 0:
            ctx = context_text.lower()
            receive_words = [
                "receive", "recieve", "get money",
                "claim", "cashback", "reward",
                "won", "prize", "refund",
                "credited", "you get",
            ]
            if any(w in ctx for w in receive_words):
                risks.append({
                    "severity": "CRITICAL",
                    "type": "PAY_VS_RECEIVE_MISMATCH",
                    "detail": (
                        f"Sign says RECEIVE but this QR will "
                        f"DEBIT Rs.{amount:,.2f} from YOUR account!"
                    ),
                })
                risk_score += 55

        if amount >= 10000:
            risks.append({
                "severity": "HIGH",
                "type": "VERY_HIGH_AMOUNT",
                "detail": f"QR requests debit of Rs.{amount:,.2f}",
            })
            risk_score += 25
        elif amount >= 2000:
            risks.append({
                "severity": "MEDIUM",
                "type": "HIGH_AMOUNT",
                "detail": f"QR requests debit of Rs.{amount:,.2f}",
            })
            risk_score += 12

        if payee_vpa:
            for pat in self.KNOWN_SCAM_PATTERNS:
                if re.search(pat, payee_vpa.lower()):
                    risks.append({
                        "severity": "CRITICAL",
                        "type": "SUSPICIOUS_VPA",
                        "detail": (
                            f"VPA '{payee_vpa}' matches known scam patterns"
                        ),
                    })
                    risk_score += 30
                    break

        if not payee_name or payee_name.lower() in [
            "merchant", "user", "account", "unknown", ""
        ]:
            risks.append({
                "severity": "LOW",
                "type": "GENERIC_PAYEE_NAME",
                "detail": "Payee name is missing or generic",
            })
            risk_score += 5

        return {
            "is_upi": True,
            "payee_vpa": payee_vpa,
            "payee_name": payee_name,
            "amount": amount,
            "transaction_note": note,
            "actual_action": "DEBIT",
            "risks": risks,
            "upi_risk_score": min(risk_score, 100),
        }

upi_engine = UPIIntentEngine()
