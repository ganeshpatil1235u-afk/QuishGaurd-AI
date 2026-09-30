# backend/ml/build_dataset.py   (v2: MORE data, merges with what you already have)
# Writes ml/data/urls.csv (columns: url,label)  label 1 = phishing, 0 = safe
# Run from the backend folder:   python ml/build_dataset.py
#
# Phishing sources : OpenPhish feed + Phishing.Database (thousands of domains)
#                    + your own file  ml/data/my_phish.txt   (optional, one link per line)
# Safe sources     : Tranco top-100k + built-in Indian payment/bank sites
#                    + your own file  ml/data/my_safe.txt    (optional, one link per line)
# Old phishing rows in urls.csv are KEPT, so the dataset grows every time you run this.
import argparse, csv, io, os, random, sys, zipfile
from urllib.parse import urlparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests
from services.domain_utils import registered_domain

DATA = os.path.join(os.path.dirname(__file__), "data")
OUT = os.path.join(DATA, "urls.csv")
PHISH_CAP = 5000          # max new phishing links from Phishing.Database per run

HARD_SAFE = """paytm.com phonepe.com pay.google.com navi.com sbi.co.in onlinesbi.sbi hdfcbank.com
icicibank.com axisbank.com kotak.com npci.org.in bhimupi.org.in irctc.co.in amazon.in flipkart.com
swiggy.com zomato.com groww.in zerodha.com bharatpe.com mobikwik.com freecharge.in airtel.in jio.com
uidai.gov.in incometax.gov.in india.gov.in digilocker.gov.in myntra.com bigbasket.com olacabs.com
uber.com makemytrip.com bookmyshow.com github.com wikipedia.org google.com youtube.com""".split()

def host_only(u):
    """Keep only https://host so the model can't cheat on 'has a path' or 'is http'."""
    u = u.strip()
    if not u or u.startswith("#"):
        return None
    if "//" not in u:
        u = "http://" + u
    try:
        h = (urlparse(u).hostname or "").lower()
    except ValueError:
        return None
    return f"https://{h}" if h and "." in h else None

def fetch(src, url, optional=False):
    try:
        if src:
            return open(src, "rb").read()
        print("Downloading", url)
        r = requests.get(url, timeout=90, headers={"User-Agent": "QuishGuard-research"})
        r.raise_for_status()
        return r.content
    except Exception as e:
        why = type(e).__name__
        if isinstance(e, requests.exceptions.ConnectionError):
            why = "cannot reach the internet / DNS problem"
        print(f"  (could not get it: {why})")
        if optional:
            return b""
        raise

def read_lines(path):
    return open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phish-file"); ap.add_argument("--tranco-file"); ap.add_argument("--pdb-file")
    a = ap.parse_args(); random.seed(7)
    os.makedirs(DATA, exist_ok=True)

    # ---- old phishing rows (keep them) ----
    old_phish, old_safe = set(), set()
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8")):
            (old_phish if r["label"] == "1" else old_safe).add(r["url"])
    print(f"Kept {len(old_phish)} phishing rows from your earlier dataset")

    # ---- popular sites list (Tranco, or Cisco Umbrella as backup) ----
    text = None
    for src, url in ((a.tranco_file, "https://tranco-list.eu/top-1m.csv.zip"),
                     (None, "https://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip")):
        z = fetch(src, url, optional=True)
        if not z:
            continue
        try:
            text = zipfile.ZipFile(io.BytesIO(z)).read("top-1m.csv").decode()
        except zipfile.BadZipFile:
            text = z.decode("utf-8", "ignore")
        break
    if text is None:
        sys.exit("\n❌ Could not download the list of popular (safe) sites.\n"
                 "   Your computer cannot reach the internet from Python right now.\n"
                 "   Fix: switch Wi-Fi / use phone hotspot, then run this again.\n"
                 "   Or download files in Chrome and use --tranco-file (see instructions).")
    top = [row[1] for row in csv.reader(text.splitlines()[:100000]) if len(row) > 1]
    top_regs = {registered_domain(d) for d in top}

    # ---- new phishing ----
    new = set()
    raw = fetch(a.phish_file, "https://openphish.com/feed.txt", optional=True).decode("utf-8", "ignore")
    new |= {host_only(l) for l in raw.splitlines()}
    pdb = fetch(a.pdb_file, "https://raw.githubusercontent.com/mitchellkrogza/Phishing.Database/master/phishing-domains-ACTIVE.txt",
                optional=True).decode("utf-8", "ignore").splitlines()
    pdb = [host_only(l) for l in pdb]
    pdb = [p for p in pdb if p]
    random.shuffle(pdb)
    new |= set(pdb[:PHISH_CAP])
    new |= {host_only(l) for l in read_lines(os.path.join(DATA, "my_phish.txt"))}
    new.discard(None)

    phish = old_phish | new
    before = len(phish)
    phish = {p for p in phish if registered_domain(p.replace("https://", "")) not in top_regs}
    print(f"Removed {before - len(phish)} 'phishing' hosts that are actually top-100k sites (label noise)")

    # ---- safe ----
    safe = {host_only(d) for d in HARD_SAFE} | old_safe
    safe |= {host_only(l) for l in read_lines(os.path.join(DATA, "my_safe.txt"))}
    pool = [host_only(d) for d in top]
    pool = [p for p in pool if p and p not in safe]
    need = max(len(phish) - len(safe), 0)
    safe |= set(random.sample(pool, min(need, len(pool))))
    safe.discard(None)

    rows = [(u, 1) for u in phish] + [(u, 0) for u in safe]
    random.shuffle(rows)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["url", "label"]); w.writerows(rows)
    print(f"✅ Wrote {OUT}: {len(phish)} phishing + {len(safe)} safe = {len(rows)} rows")
    if len(rows) < 1000:
        print("⚠️ Under 1000 rows - results will be weak.")

if __name__ == "__main__":
    main()