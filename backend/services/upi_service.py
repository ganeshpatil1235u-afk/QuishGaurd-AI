# backend/services/upi_service.py
from urllib.parse import urlparse, parse_qs
import re


class UPIIntentEngine:
    # Well-formed VPA: <local-part>@<handle>
    VPA_REGEX = re.compile(r"^[a-z0-9][a-z0-9._\-]{1,255}@[a-z][a-z0-9]{1,63}$")

    # Registered UPI handles (PSP / bank suffixes) -> app/bank family.
    # Phone-number VPAs on these handles (e.g. 9876543210@ibl) are NORMAL in India.
    KNOWN_HANDLES = {
        # PhonePe
        "ybl": "PhonePe", "ibl": "PhonePe", "axl": "PhonePe",
        # Google Pay
        "okhdfcbank": "Google Pay", "okicici": "Google Pay",
        "okaxis": "Google Pay", "oksbi": "Google Pay",
        # Paytm
        "paytm": "Paytm", "ptyes": "Paytm", "pthdfc": "Paytm",
        "ptsbi": "Paytm", "ptaxis": "Paytm",
        # Amazon Pay / WhatsApp / others
        "apl": "Amazon Pay", "yapl": "Amazon Pay",
        "waaxis": "WhatsApp Pay", "wahdfcbank": "WhatsApp Pay",
        "wasbi": "WhatsApp Pay", "waicici": "WhatsApp Pay",
        "freecharge": "Freecharge", "jupiter": "Jupiter", "fbl": "Federal Bank",
        # Banks
        "sbi": "SBI", "hdfcbank": "HDFC Bank", "icici": "ICICI Bank",
        "axisbank": "Axis Bank", "axisb": "Axis Bank", "kotak": "Kotak",
        "yesbank": "Yes Bank", "indus": "IndusInd", "pnb": "PNB",
        "boi": "Bank of India", "cnrb": "Canara Bank", "okbizaxis": "Google Pay",
        "unionbank": "Union Bank", "uboi": "Union Bank", "ubi": "Union Bank",
        "idfcbank": "IDFC First", "idfcfirst": "IDFC First", "rbl": "RBL",
        "aubank": "AU Bank", "federal": "Federal Bank", "upi": "NPCI",
        "airtel": "Airtel Payments", "postbank": "India Post",
        "barodampay": "Bank of Baroda", "allbank": "Indian Bank",
        "idbi": "IDBI", "iob": "IOB", "kvb": "Karur Vysya", "sib": "South Indian Bank",
        "dbs": "DBS", "hsbc": "HSBC", "bandhan": "Bandhan", "csbpay": "CSB",
        "dcb": "DCB", "jsb": "Janata Sahakari", "mahb": "Bank of Maharashtra",
        "uco": "UCO Bank", "cbin": "Central Bank", "andb": "Andhra Bank",
        "naviaxis": "Navi", "navi": "Navi", "slc": "Slice", "sliceaxis": "Slice",
        "superyes": "super.money", "fifederal": "Fi Money", "yesbankltd": "BharatPe / Yes Bank",
        "yesg": "Groww", "jio": "Jio Payments", "pz": "PayZapp", "tapicici": "Tata Neu",
        "kiwi": "Kiwi", "cred": "CRED", "axisb": "CRED", "ptybl": "Paytm",
        "ikwik": "MobiKwik", "abfspay": "Aditya Birla", "cmsidfc": "IDFC First",
    }

    # Local-part patterns that are genuinely suspicious
    SUSPICIOUS_LOCAL_PATTERNS = [
        r"^test\d*$", r"^temp\d*$", r"^scam", r"^fraud", r"^fake",
        r"^[a-z]{22,}$",          # long random letter strings
        r"^\d{13,}$",             # 13+ digits is not a phone number
    ]

    # Social-engineering words in payee name / VPA
    LURE_WORDS = [
        "refund", "cashback", "reward", "lottery", "prize", "kyc",
        "helpline", "customer care", "customercare", "support", "winner",
    ]

    RECEIVE_WORDS = [
        "receive", "recieve", "get money", "claim", "cashback",
        "reward", "won", "prize", "refund", "credited", "you get",
    ]

    def analyze_upi_payload(self, upi_string: str, context_text: str = None) -> dict:
        if not upi_string or not upi_string.strip().lower().startswith("upi://"):
            return {"is_upi": False}

        parsed = urlparse(upi_string.strip())
        params = parse_qs(parsed.query)
        payee_vpa = (params.get("pa", [None])[0] or "").strip()
        payee_name = (params.get("pn", [""])[0] or "").strip()
        note = params.get("tn", [""])[0]
        try:
            amount = float(params.get("am", ["0"])[0] or 0)
        except ValueError:
            amount = 0.0

        risks = []
        risk_score = 0
        vpa_lower = payee_vpa.lower()
        local, _, handle = vpa_lower.partition("@")
        vpa_valid = bool(self.VPA_REGEX.match(vpa_lower))
        known_psp = self.KNOWN_HANDLES.get(handle)
        is_phone_vpa = bool(re.fullmatch(r"[6-9]\d{9}", local))

        # 1. Sign says RECEIVE but QR is a payment intent (classic QR fraud)
        if context_text:
            ctx = context_text.lower()
            if any(w in ctx for w in self.RECEIVE_WORDS):
                if amount > 0:
                    risks.append({
                        "severity": "CRITICAL",
                        "type": "PAY_VS_RECEIVE_MISMATCH",
                        "detail": (f"Sign says RECEIVE but this QR will DEBIT "
                                   f"Rs.{amount:,.2f} from YOUR account!"),
                    })
                    risk_score += 55
                else:
                    risks.append({
                        "severity": "CRITICAL",
                        "type": "PAY_VS_RECEIVE_MISMATCH",
                        "detail": ("Sign promises you'll RECEIVE money, but this QR "
                                   "opens a PAYMENT screen. Entering your PIN approves "
                                   "money LEAVING your account."),
                    })
                    risk_score += 50

        # 2. Amount
        if amount >= 10000:
            risks.append({"severity": "HIGH", "type": "VERY_HIGH_AMOUNT",
                          "detail": f"QR requests debit of Rs.{amount:,.2f}"})
            risk_score += 25
        elif amount >= 2000:
            risks.append({"severity": "MEDIUM", "type": "HIGH_AMOUNT",
                          "detail": f"QR requests debit of Rs.{amount:,.2f}"})
            risk_score += 12

        # 3. VPA structure / handle
        if not payee_vpa:
            risks.append({"severity": "HIGH", "type": "MISSING_VPA",
                          "detail": "QR has no payee UPI ID (pa)"})
            risk_score += 40
        elif not vpa_valid:
            risks.append({"severity": "HIGH", "type": "MALFORMED_VPA",
                          "detail": f"'{payee_vpa}' is not a valid UPI ID format"})
            risk_score += 40
        elif known_psp is None:
            risks.append({"severity": "LOW", "type": "UNKNOWN_HANDLE",
                          "detail": f"Handle '@{handle}' is not in our list yet - check the payee name"})
            risk_score += 8

        # 4. Genuinely suspicious local parts (phone numbers are NOT flagged)
        if vpa_valid and not is_phone_vpa:
            for pat in self.SUSPICIOUS_LOCAL_PATTERNS:
                if re.search(pat, local):
                    risks.append({
                        "severity": "HIGH", "type": "SUSPICIOUS_VPA",
                        "detail": f"UPI ID '{payee_vpa}' looks auto-generated or fake",
                    })
                    risk_score += 30
                    break

        # 5. Lure words in payee name / VPA
        haystack = f"{payee_name} {vpa_lower}".lower()
        if any(w in haystack for w in self.LURE_WORDS):
            risks.append({"severity": "MEDIUM", "type": "LURE_KEYWORD",
                          "detail": "Payee name/UPI ID contains refund/reward/support style wording"})
            risk_score += 20

        # 6. Missing / generic name
        if not payee_name or payee_name.lower() in ["merchant", "user", "account", "unknown"]:
            risks.append({"severity": "LOW", "type": "GENERIC_PAYEE_NAME",
                          "detail": "Payee name is missing or generic"})
            risk_score += 5

        return {
            "is_upi": True,
            "payee_vpa": payee_vpa,
            "payee_name": payee_name or "Unknown",
            "amount": amount,
            "transaction_note": note,
            "actual_action": "DEBIT",
            "vpa_valid": vpa_valid,
            "vpa_handle": handle or None,
            "known_psp": known_psp,
            "is_phone_number_vpa": is_phone_vpa,
            "risks": risks,
            "upi_risk_score": min(risk_score, 100),
        }


upi_engine = UPIIntentEngine()
print(f"[QuishGuard] NEW UPI engine loaded from: {__file__}")