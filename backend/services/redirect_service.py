# backend/services/redirect_service.py
# Follows short links to find the REAL destination. Blocks private IPs (SSRF safety).
import ipaddress, socket
import requests
from urllib.parse import urljoin, urlparse

def _is_private(host: str) -> bool:
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except Exception:
        return True   # cannot resolve -> do not fetch
    return False

def follow_redirects(url: str, max_hops: int = 5, timeout: float = 4.0) -> dict:
    chain, current = [url], url
    try:
        for _ in range(max_hops):
            host = urlparse(current).hostname or ""
            if not current.startswith(("http://", "https://")) or _is_private(host):
                return {"final_url": current, "chain": chain, "hops": len(chain) - 1,
                        "note": "stopped: unsafe or unresolvable host"}
            r = requests.get(current, allow_redirects=False, timeout=timeout, stream=True,
                             headers={"User-Agent": "QuishGuard/3.0"})
            r.close()
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                current = urljoin(current, r.headers["Location"])
                chain.append(current)
            else:
                break
        return {"final_url": current, "chain": chain, "hops": len(chain) - 1, "note": "ok"}
    except Exception as e:
        return {"final_url": current, "chain": chain, "hops": len(chain) - 1,
                "note": f"redirect check failed: {type(e).__name__}"}
