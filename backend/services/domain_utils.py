# backend/services/domain_utils.py
# Safe domain tools. NEVER use "brand in url" – always compare the REGISTERED domain.
import re
from urllib.parse import urlparse

MULTI_SUFFIX = {"co.in", "org.in", "net.in", "gov.in", "ac.in", "co.uk",
                "com.au", "co.jp", "com.br", "co.za"}

RISKY_TLDS = {"tk", "ml", "ga", "cf", "gq", "xyz", "top", "buzz", "click",
              "link", "pw", "cc", "club", "icu", "live", "rest", "zip", "mov"}

# brand -> official registered domains
BRANDS = {
    "paytm": {"paytm.com", "paytm.in", "paytmpay.com"},
    "phonepe": {"phonepe.com", "phone.pe"},
    "googlepay": {"pay.google.com", "google.com"},
    "google": {"google.com", "google.co.in", "goo.gl", "gstatic.com"},
    "amazon": {"amazon.com", "amazon.in", "amzn.to", "amazonaws.com"},
    "flipkart": {"flipkart.com"},
    "sbi": {"sbi.co.in", "onlinesbi.com", "onlinesbi.sbi", "sbi.bank.in"},
    "hdfc": {"hdfcbank.com", "hdfc.com"},
    "hdfcbank": {"hdfcbank.com"},
    "icici": {"icicibank.com", "icici.com"},
    "axis": {"axisbank.com"},
    "npci": {"npci.org.in"},
    "irctc": {"irctc.co.in"},
    "paypal": {"paypal.com"},
    "microsoft": {"microsoft.com", "live.com", "office.com"},
    "apple": {"apple.com", "icloud.com"},
    "netflix": {"netflix.com"},
    "whatsapp": {"whatsapp.com", "wa.me", "whatsapp.net"},
    "instagram": {"instagram.com"},
    "facebook": {"facebook.com", "fb.com", "messenger.com"},
    "telegram": {"telegram.org", "t.me"},
}
ALL_OFFICIAL = set().union(*BRANDS.values())
TRUSTED = {"google.com", "youtube.com", "wikipedia.org", "github.com",
           "microsoft.com", "apple.com", "amazon.in", "amazon.com",
           "whatsapp.com", "wa.me", "whatsapp.net", "instagram.com", "facebook.com",
           "fb.com", "messenger.com", "telegram.org", "t.me", "linkedin.com",
           "twitter.com", "x.com", "zoom.us", "spotify.com", "netflix.com",
           "flipkart.com", "swiggy.com", "zomato.com", "myntra.com", "irctc.co.in"}

_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})


def get_host(url: str) -> str:
    u = url.strip()
    if "//" not in u:
        u = "http://" + u
    try:
        host = (urlparse(u).hostname or "").lower().rstrip(".")
    except ValueError:
        host = ""
    return host


def registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_SUFFIX:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def tld_of(host: str) -> str:
    return host.split(".")[-1] if "." in host else ""


def is_official(host: str) -> bool:
    """True only if the host IS an official domain or a subdomain of one."""
    return any(host == d or host.endswith("." + d) for d in ALL_OFFICIAL)


def is_trusted(host: str) -> bool:
    reg = registered_domain(host)
    return reg in TRUSTED or is_official(host)


def is_ip_host(host: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host))


def has_punycode(host: str) -> bool:
    return any(label.startswith("xn--") for label in host.split("."))


def has_non_ascii(host: str) -> bool:
    return any(ord(c) > 127 for c in host)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def brand_check(host: str):
    """Return (kind, brand) where kind is 'IMPERSONATION' | 'LOOKALIKE' | None."""
    if is_official(host):
        return None, None
    reg = registered_domain(host)
    main_label = reg.split(".")[0]
    tokens = [t for t in re.split(r"[^a-z0-9]+", host) if t]
    for brand in BRANDS:
        # brand written as a whole word anywhere in the host (paytm-kyc.xyz, google.com.evil.io)
        if brand in tokens or (len(brand) >= 5 and any(brand in t for t in tokens)):
            return "IMPERSONATION", brand
    fixed = main_label.translate(_LEET)
    for brand in BRANDS:
        if len(brand) < 5:
            continue
        if fixed != brand and levenshtein(fixed, brand) <= 1:
            return "LOOKALIKE", brand      # paytmm.com, g00gle.com, arnazon.com
        if main_label != brand and fixed == brand:
            return "LOOKALIKE", brand
    return None, None