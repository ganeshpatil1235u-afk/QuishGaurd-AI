# backend/services/page_service.py
# Option 2: look INSIDE the landing page for phishing signals.
#
# Safety rules (why this is safe to run on unknown sites):
#   * The page is only DOWNLOADED as text. No JavaScript is ever executed.
#   * Private / internal / unresolvable hosts are refused (same guard as redirect_service).
#   * Only http/https on ports 80/443, max 300 KB, 4 second timeout, HTML content-type only.
#   * Redirects are NOT followed here (redirect_service already found the final URL).
#   * The result can only ADD warning points. It never lowers a score.
#
# Known limits (say them out loud to judges):
#   * Pages that build their form with JavaScript look empty to us.
#   * DNS can change between our safety check and the fetch (DNS rebinding).
#   * A clean-looking page proves nothing. No signal != safe.
#
# Extra design notes:
#   * Zero new dependencies: HTML is parsed with the standard-library html.parser.
#   * Trusted domains (domain_utils.is_trusted) are NOT fetched: their login forms are
#     legitimate, and it saves latency. A hacked trusted site is out of scope.
#   * Everything we copy out of the (hostile) page into our JSON is sanitised, because
#     the browser extension renders server text with innerHTML.

import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from services.domain_utils import (
    BRANDS, get_host, is_ip_host, is_trusted, registered_domain,
)
from services.redirect_service import _is_private   # reuse the SSRF guard (one source of truth)

# ------------------------------------------------------------------ limits
MAX_BYTES = 300 * 1024          # never read more than 300 KB
TIMEOUT = 4.0                   # seconds, applied to connect, read AND total download
ALLOWED_PORTS = {80, 443}
MAX_RISK_POINTS = 40.0          # page signals can add at most this much to the score
USER_AGENT = "QuishGuard/3.0 (page-check; no-js)"
_MAX_TEXT = 20_000              # visible text we keep for keyword checks
_MAX_SCRIPT = 100_000           # inline script text we keep for obfuscation checks
_MAX_ITEMS = 200                # cap on stored inputs / forms (memory safety)

LIMITS_NOTE = ("Static HTML only: JavaScript is never run, so JS-built forms are invisible. "
               "A page with no signals is not proven safe.")

# ------------------------------------------------------------------ patterns
_NOT_ALNUM_L, _NOT_ALNUM_R = r"(?<![a-z0-9])", r"(?![a-z0-9])"

_SENSITIVE_KINDS = {
    "otp": r"otp|one[\s_-]?time[\s_-]?(pass|code)|verification[\s_-]?code",
    "card": r"cvv|cvc|card[\s_-]?(no|num|number)|(debit|credit)[\s_-]?card|card[\s_-]?expiry",
    "upi_pin": r"(upi|atm|m|login|secret)[\s_-]?pin|upi[\s_-]?id",
    "gov_id": r"aadhaar|aadhar|pan[\s_-]?(no|num|number|card)",
    "bank": r"ifsc|net[\s_-]?banking|account[\s_-]?(no|num|number)",
}
_SENSITIVE_RE = {k: re.compile(_NOT_ALNUM_L + "(?:" + v + ")" + _NOT_ALNUM_R, re.I)
                 for k, v in _SENSITIVE_KINDS.items()}
_SENSITIVE_AUTOCOMPLETE = {"cc-number": "card", "cc-csc": "card", "cc-exp": "card",
                           "one-time-code": "otp"}

# How each brand is written on a page (plain words like "axis"/"apple" need context).
_BRAND_TERMS = {
    "paytm": r"paytm", "phonepe": r"phone\s?pe", "googlepay": r"google\s?pay|gpay",
    "google": r"google", "amazon": r"amazon", "flipkart": r"flipkart",
    "sbi": r"sbi|state bank of india", "hdfc": r"hdfc", "icici": r"icici",
    "axis": r"axis bank", "npci": r"npci|bhim", "irctc": r"irctc", "paypal": r"paypal",
    "microsoft": r"microsoft", "apple": r"apple id|icloud", "netflix": r"netflix",
    "whatsapp": r"whatsapp", "instagram": r"instagram", "facebook": r"facebook",
    "telegram": r"telegram",
}
_BRAND_RE = {b: re.compile(_NOT_ALNUM_L + "(?:" + t + ")" + _NOT_ALNUM_R, re.I)
             for b, t in _BRAND_TERMS.items() if b in BRANDS}

_LURE_RE = [re.compile(p, re.I) for p in (
    r"account\s+(will\s+be\s+|has\s+been\s+)?(suspended|blocked|locked|deactivated|closed)",
    r"verify\s+(your\s+)?(account|identity|kyc|details)",
    r"kyc\s+(update|expired|pending|verification)",
    r"within\s+(24|48)\s+hours",
    r"(claim|collect)\s+(your\s+)?(reward|prize|cashback|refund|gift)",
    r"you\s+(have\s+)?won",
    r"update\s+your\s+(pan|aadhaar|aadhar|bank)",
    r"unusual\s+(sign[\s-]?in|activity|login)",
)]

_OBFUSCATION_RE = [re.compile(p) for p in (
    r"eval\s*\(\s*(?:atob|unescape|decodeURIComponent|String\.fromCharCode)",
    r"document\.write\s*\(\s*unescape",
    r"atob\s*\(\s*['\"][A-Za-z0-9+/=]{200,}",
    r"(?:\\x[0-9a-fA-F]{2}){40,}",
    r"String\.fromCharCode\s*\((?:\s*\d+\s*,){20,}",
)]
_RIGHT_CLICK_RE = re.compile(r"contextmenu[\s\S]{0,80}(preventDefault|return\s+false)", re.I)

# Hidden iframes to these are normal (analytics / tag managers) - do not flag them.
_BENIGN_FRAME_DOMAINS = {"googletagmanager.com", "google-analytics.com", "doubleclick.net",
                         "youtube.com", "youtube-nocookie.com", "facebook.com", "google.com",
                         "recaptcha.net", "gstatic.com"}

_HIDDEN_STYLE_RE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|(?:width|height)\s*:\s*[01](?:px)?\s*(?:;|$)",
    re.I)


# ------------------------------------------------------------------ helpers
def _clean(value, limit: int = 60) -> str:
    """Make attacker-controlled text safe to echo in JSON / an innerHTML popup."""
    s = re.sub(r"[^A-Za-z0-9 .:/_\-]", "", str(value or ""))
    return s.strip()[:limit]


def _to_int(v):
    try:
        return int(re.sub(r"[^0-9]", "", str(v)) or "x")
    except ValueError:
        return None


def _brand_is_official_here(host: str, brand: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in BRANDS.get(brand, ()))


def _http_host(url: str, base: str):
    """Absolute http(s) URL -> host, else None (javascript:, mailto:, #, empty ...)."""
    try:
        absolute = urljoin(base, url.strip())
    except ValueError:
        return None
    if urlparse(absolute).scheme not in ("http", "https"):
        return None
    return get_host(absolute)


# ------------------------------------------------------------------ 1) safe download
def fetch_page(url: str) -> dict:
    """Download the page as text. Returns {"html": str|None, "note": str, ...meta}."""
    def refuse(note):
        return {"html": None, "note": note}

    try:
        parsed = urlparse(url)
        port = parsed.port                        # may raise ValueError on junk
    except ValueError:
        return refuse("skipped: malformed URL")
    if parsed.scheme not in ("http", "https"):
        return refuse("skipped: only http/https pages are fetched")
    if port is not None and port not in ALLOWED_PORTS:
        return refuse("skipped: only ports 80/443 are fetched")
    host = parsed.hostname or ""
    if not host or _is_private(host):
        return refuse("skipped: unsafe or unresolvable host")

    resp = None
    try:
        resp = requests.get(
            url, allow_redirects=False, stream=True, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT,
                     "Accept": "text/html,application/xhtml+xml;q=0.9",
                     "Accept-Language": "en"})
        if resp.status_code in (301, 302, 303, 307, 308):
            return refuse("skipped: page redirected (redirects are not followed here)")
        if resp.status_code != 200:
            return {"html": None, "note": f"skipped: HTTP {resp.status_code}",
                    "http_status": resp.status_code}

        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype not in ("text/html", "application/xhtml+xml"):
            return {"html": None, "note": f"skipped: not HTML ({_clean(ctype) or 'unknown'})",
                    "http_status": 200}

        deadline = time.monotonic() + TIMEOUT      # total cap: defeats slow-drip servers
        buf, truncated = bytearray(), False
        for chunk in resp.iter_content(chunk_size=8192):
            buf.extend(chunk)
            if len(buf) >= MAX_BYTES:
                del buf[MAX_BYTES:]
                truncated = True
                break
            if time.monotonic() > deadline:
                truncated = True
                break
        return {"html": bytes(buf).decode("utf-8", errors="replace"),
                "note": "ok" + (" (truncated)" if truncated else ""),
                "http_status": 200, "content_type": ctype,
                "bytes_read": len(buf), "truncated": truncated}
    except Exception as e:                          # network errors must never crash a scan
        return refuse(f"page fetch failed: {type(e).__name__}")
    finally:
        if resp is not None:
            resp.close()


# ------------------------------------------------------------------ 2) parse (no JS run)
class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.forms = []            # {"action": str, "inputs": [..]}
        self.inputs = []           # every input on the page (inside a form or not)
        self.iframes = []
        self.meta_refresh = []
        self.text = []
        self.text_len = 0
        self.script_text = []
        self.script_len = 0
        self.script_count = 0
        self.right_click_attr = False
        self._cur_form = None
        self._in = None            # "title" | "script" | "style" | None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if "oncontextmenu" in a and "return false" in a["oncontextmenu"].lower():
            self.right_click_attr = True
        if tag == "title":
            self._in = "title"
        elif tag in ("script", "style"):
            self._in = tag
            if tag == "script":
                self.script_count += 1
        elif tag == "form" and len(self.forms) < _MAX_ITEMS:
            self._cur_form = {"action": a.get("action", ""), "inputs": []}
            self.forms.append(self._cur_form)
        elif tag == "input" and len(self.inputs) < _MAX_ITEMS:
            inp = {"type": a.get("type", "text").lower(),
                   "hint": " ".join(a.get(k, "") for k in ("name", "id", "placeholder", "aria-label")),
                   "autocomplete": a.get("autocomplete", "").lower()}
            self.inputs.append(inp)
            if self._cur_form is not None:
                self._cur_form["inputs"].append(inp)
        elif tag == "iframe" and len(self.iframes) < _MAX_ITEMS:
            self.iframes.append(a)
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            self.meta_refresh.append(a.get("content", ""))

    def handle_endtag(self, tag):
        if tag == "form":
            self._cur_form = None
        if tag in ("title", "script", "style"):
            self._in = None

    def handle_data(self, data):
        if self._in == "title":
            self.title += data[:200]
        elif self._in == "script":
            if self.script_len < _MAX_SCRIPT:
                self.script_text.append(data)
                self.script_len += len(data)
        elif self._in is None and self.text_len < _MAX_TEXT:
            self.text.append(data)
            self.text_len += len(data)


def _sensitive_kinds(inputs) -> set:
    kinds = set()
    for i in inputs:
        if i["type"] in ("hidden", "submit", "button", "image", "checkbox", "radio"):
            continue
        for ac in i["autocomplete"].split():
            if ac in _SENSITIVE_AUTOCOMPLETE:
                kinds.add(_SENSITIVE_AUTOCOMPLETE[ac])
        for kind, rx in _SENSITIVE_RE.items():
            if rx.search(i["hint"]):
                kinds.add(kind)
    return kinds


# ------------------------------------------------------------------ 3) score the signals
def analyze_html(html: str, url: str) -> dict:
    """Pure function (no network): HTML text + its URL -> signals. Easy to unit-test."""
    p = _PageParser()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass                                        # broken HTML: use whatever was parsed

    page_host = get_host(url)
    page_reg = registered_domain(page_host)
    signals = []

    def add(code, points, detail):
        signals.append({"code": code, "points": float(points), "detail": detail})

    has_password = any(i["type"] == "password" for i in p.inputs)
    kinds = _sensitive_kinds(p.inputs)
    credential_page = has_password or bool(kinds)
    title = re.sub(r"\s+", " ", p.title).strip()
    text = re.sub(r"\s+", " ", " ".join(p.text)).strip()
    script = " ".join(p.script_text)

    # -- password / sensitive-data collection
    if has_password:
        add("password_field", 6, "Page asks for a password on an unverified domain")
        if urlparse(url).scheme == "http":
            add("insecure_password", 10, "Password field on a page that is not encrypted (http)")
    if kinds:
        pts = 16 if len(kinds) >= 2 else 12
        add("sensitive_fields", pts,
            "Page asks for sensitive data: " + ", ".join(sorted(kinds)).replace("_", " "))

    # -- where do the forms send the data?
    for form in p.forms:
        f_kinds = _sensitive_kinds(form["inputs"])
        f_cred = any(i["type"] == "password" for i in form["inputs"]) or bool(f_kinds)
        action = form["action"].strip()
        if action.lower().startswith("mailto:"):
            add("mailto_form", 15, "Form sends what you type straight to an email address")
            continue
        if not f_cred:
            continue                                # only judge forms that collect secrets
        a_host = _http_host(action, url) if action else None
        if not a_host:
            continue
        if registered_domain(a_host) != page_reg and not is_trusted(a_host):
            add("cross_domain_form", 20,
                f"Login/payment form sends data to a different site ({_clean(registered_domain(a_host))})")
            if is_ip_host(a_host):
                add("ip_form_action", 10, "Form data is sent to a raw IP address")
            break                                   # one finding is enough

    # -- pretending to be a brand
    title_l = title.lower()
    found = []
    for brand, rx in _BRAND_RE.items():
        if _brand_is_official_here(page_host, brand):
            continue
        in_title = bool(rx.search(title_l))
        mentions = len(rx.findall(text))
        if in_title and credential_page:
            found.append((18, brand, "in the page title"))
        elif in_title:
            found.append((8, brand, "in the page title"))
        elif credential_page and mentions >= 3:
            found.append((12, brand, f"{mentions} times on the page"))
    if found:
        pts, brand, where = max(found)              # strongest single brand claim only
        add("brand_impersonation", pts,
            f"Page presents itself as {_clean(brand)} ({where}) but is hosted on {_clean(page_reg)}")

    # -- pressure / lure language
    lures = sum(1 for rx in _LURE_RE if rx.search(text) or rx.search(title))
    if lures:
        add("urgent_language", min(lures * 4, 12),
            f"{lures} pressure/reward phrase(s) typical of scams (e.g. account suspended, verify KYC)")

    # -- sneaky tricks
    for fr in p.iframes:
        src_host = _http_host(fr.get("src", ""), url) if fr.get("src") else None
        if not src_host or registered_domain(src_host) == page_reg:
            continue
        if registered_domain(src_host) in _BENIGN_FRAME_DOMAINS or is_trusted(src_host):
            continue
        w, h = _to_int(fr.get("width")), _to_int(fr.get("height"))
        hidden = ("hidden" in fr or (w is not None and w <= 1) or (h is not None and h <= 1)
                  or bool(_HIDDEN_STYLE_RE.search(fr.get("style", ""))))
        if hidden:
            add("hidden_iframe", 12, f"Invisible frame loads content from {_clean(registered_domain(src_host))}")
            break

    for content in p.meta_refresh:
        m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", content, re.I)
        r_host = _http_host(m.group(1), url) if m else None
        if r_host and registered_domain(r_host) != page_reg and not is_trusted(r_host):
            add("meta_refresh", 10, f"Page silently forwards you to {_clean(registered_domain(r_host))}")
            break

    if any(rx.search(script) for rx in _OBFUSCATION_RE):
        add("obfuscated_js", 12, "Page contains scrambled/encoded JavaScript (hides what it does)")
    if p.right_click_attr or _RIGHT_CLICK_RE.search(script):
        add("right_click_blocked", 4, "Page blocks right-click (often used to stop inspection)")

    # -- honest limit: looks empty because JS builds the page (0 points, information only)
    js_only = (not p.forms and not p.inputs and len(text) < 200 and p.script_count > 0)
    if js_only:
        add("js_only_page", 0, "Page is built by JavaScript, so its content could not be inspected")

    total = min(sum(s["points"] for s in signals), MAX_RISK_POINTS)
    return {
        "title": _clean(title, 100),
        "forms": len(p.forms),
        "has_password_field": has_password,
        "signals": signals,
        "risk_points": round(total, 1),
        "reasons": [s["detail"] for s in signals if s["points"] > 0],
    }


# ------------------------------------------------------------------ 4) public entry point
def analyze_page(url: str) -> dict:
    """Used by main.py. NEVER raises, never returns negative points."""
    base = {"checked": False, "risk_points": 0.0, "signals": [], "reasons": [],
            "limits": LIMITS_NOTE}
    try:
        host = get_host(url)
        if is_trusted(host):
            return {**base, "note": "skipped: trusted domain"}
        got = fetch_page(url)
        if got["html"] is None:
            return {**base, "note": got["note"]}
        result = analyze_html(got["html"], url)
        meta = {k: got[k] for k in ("http_status", "content_type", "bytes_read", "truncated")
                if k in got}
        return {**base, **meta, **result, "checked": True, "note": got["note"]}
    except Exception as e:                          # last-resort guard: a scan must never fail here
        return {**base, "note": f"page analysis failed: {type(e).__name__}"}