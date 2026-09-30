# 🛡️ QuishGuard AI — QR phishing defense for UPI & the web
Scans a QR **before** you pay or open it, and explains the risk in plain words.

## Run in 1 command
    docker compose up --build      # API on http://localhost:8000/docs

## How it decides
1. OpenCV decodes the QR (multi-QR + sticker-tamper signals)
2. Short links are followed to the REAL destination (SSRF-safe)
3. Rules: exact registered-domain match, look-alike / punycode / brand tricks
4. ML: RandomForest on 17 URL features, with "why" explanations
5. UPI: pay-vs-receive mismatch, handle checks, amount checks
6. WHOIS age + optional VirusTotal (honestly labelled when offline)

## Train the model (real data)
Download PhishTank (label 1) and Tranco top-sites (label 0) into `backend/ml/data/urls.csv`
with columns `url,label`, then: `cd backend && python ml/train_model.py --csv ml/data/urls.csv`
Paste the printed ROC-AUC / F1 here: **TODO**

## Tests
    cd backend && python -m pytest tests -q

## Privacy
Only the decoded text/URL is analysed. Nothing is stored.
