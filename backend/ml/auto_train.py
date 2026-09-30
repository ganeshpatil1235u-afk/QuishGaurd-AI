# backend/ml/auto_train.py
# One command:   python ml/auto_train.py            (downloads fresh data, then trains)
#                python ml/auto_train.py --skip-download   (re-uses ml/data/urls.csv)
# Pure numpy. No scipy / scikit-learn.
import argparse, csv, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, BACKEND)

import numpy as np
from services.ml_service import extract_features, FEATURE_NAMES
from services.domain_utils import registered_domain, get_host
from ml.train_model import fit, sigmoid, auc_score

CSV_PATH = os.path.join(HERE, "data", "urls.csv")
MODEL_OUT = os.path.join(HERE, "model.json")

REAL_SAFE = ["https://www.google.com", "https://github.com/anthropics", "https://pay.google.com",
             "https://www.paytm.com/recharge", "https://www.irctc.co.in", "https://phonepe.com",
             "https://navi.com", "https://www.hdfcbank.com", "https://www.sbi.co.in",
             "https://www.icicibank.com", "https://www.flipkart.com", "https://www.amazon.in"]
REAL_SCAMS = ["https://accounts.google.com.evil.io/verify", "https://paytm-kyc-verify.xyz/login",
              "https://xn--pypal-4ve.com", "http://192.168.5.4/pay", "https://paytmm.com/offer",
              "https://g00gle.com/login", "https://sbi-website.info", "http://bit.ly/claim-reward"]


def metrics_at(y, p, thr=0.5):
    pred = (p > thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    return prec, rec, f1, tn, fp, fn, tp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true")
    a = ap.parse_args()

    # ---------- STEP 1: data ----------
    if not a.skip_download:
        print("STEP 1/4: building dataset (needs internet)")
        r = subprocess.run([sys.executable, os.path.join(HERE, "build_dataset.py")], cwd=BACKEND)
        if r.returncode != 0:
            print("Dataset build failed. Fix internet, or run again with --skip-download.")
            sys.exit(1)
    if not os.path.exists(CSV_PATH):
        sys.exit("Missing ml/data/urls.csv. Run without --skip-download first.")

    rows = [(r["url"], int(r["label"])) for r in csv.DictReader(open(CSV_PATH, encoding="utf-8"))]
    X = np.array([extract_features(u) for u, _ in rows], dtype=float)
    y = np.array([l for _, l in rows])
    groups = [registered_domain(get_host(u)) or u for u, _ in rows]

    # ---------- split by DOMAIN so test domains are truly unseen ----------
    rng = np.random.RandomState(42)
    uniq = sorted(set(groups))
    order = rng.permutation(len(uniq))
    bucket = {}
    for rank, i in enumerate(order):
        f = rank / len(uniq)
        bucket[uniq[i]] = 0 if f < 0.70 else (1 if f < 0.85 else 2)   # train / val / test
    b = np.array([bucket[g] for g in groups])
    tr, va, te = np.where(b == 0)[0], np.where(b == 1)[0], np.where(b == 2)[0]

    n1 = int((y == 1).sum()); n0 = int((y == 0).sum())
    print(f"\nSTEP 2/4: training on {len(tr)} rows ({int((y[tr]==1).sum())} phishing, {int((y[tr]==0).sum())} safe)"
          f"   [dataset total {len(y)}: {n1} phishing, {n0} safe]")

    mean, std = X[tr].mean(0), X[tr].std(0)
    std[std < 1e-9] = 1.0
    Z = (X - mean) / std

    best = None
    for l2 in (0.01, 0.05, 0.2, 0.5, 1.0, 2.0):
        w, bias = fit(Z[tr], y[tr].astype(float), l2=l2)
        auc_v = auc_score(y[va], sigmoid(Z[va] @ w + bias))
        if best is None or auc_v > best[0]:
            best = (auc_v, l2)
    l2 = best[1]
    print(f"  chosen regularisation: {l2}  (picked on the validation set, not the test set)")

    # final fit on train+val, test stays untouched
    trv = np.concatenate([tr, va])
    mean, std = X[trv].mean(0), X[trv].std(0)
    std[std < 1e-9] = 1.0
    Z = (X - mean) / std
    w, bias = fit(Z[trv], y[trv].astype(float), l2=l2)

    # ---------- STEP 3: honest test ----------
    p = sigmoid(Z[te] @ w + bias)
    prec, rec, f1, tn, fp, fn, tp = metrics_at(y[te], p)
    auc = float(auc_score(y[te], p))
    print("\nSTEP 3/4: results on UNSEEN domains (test set, never used for training)")
    print(f"  Test rows : {len(te)}")
    print(f"  Precision : {prec:.3f}   (when it says phishing, how often is it right)")
    print(f"  Recall    : {rec:.3f}   (how many real scams it catches)")
    print(f"  F1        : {f1:.3f}")
    print(f"  ROC-AUC   : {auc:.3f}")
    print(f"  Confusion : TN={tn}  FP={fp}  FN={fn}  TP={tp}")

    shuf = []
    r2 = np.random.RandomState(0)
    for _ in range(10):
        ys = r2.permutation(y[trv]).astype(float)
        ws, bs = fit(Z[trv], ys, l2=l2, steps=800)
        shuf.append(auc_score(y[te], sigmoid(Z[te] @ ws + bs)))
    shuf_auc = float(np.mean(shuf))
    print(f"  Shuffled-label AUC, average of 10 (should be near 0.5): {shuf_auc:.3f}")
    top = sorted(zip(np.abs(w), w, FEATURE_NAMES), reverse=True)[:5]
    print("  Top features:", [(n, round(float(v), 2)) for _, v, n in top])

    json.dump({"weights": w.tolist(), "bias": float(bias), "mean": mean.tolist(), "std": std.tolist(),
               "feature_names": FEATURE_NAMES,
               "metrics": {"roc_auc": round(auc, 4), "precision": round(prec, 4),
                           "recall": round(rec, 4), "f1": round(f1, 4),
                           "rows": len(rows), "test_rows": int(len(te))}},
              open(MODEL_OUT, "w"))

    # ---------- STEP 4: full engine (rules + ML) ----------
    from services.ml_service import ml_engine
    ml_engine.__init__()   # reload the model we just saved
    print("\nSTEP 4/4: real-world check with the full engine (rules + ML)")
    from services.hf_service import hf_engine       # imported AFTER model.json is saved
    bad_safe = [u for u in REAL_SAFE if hf_engine.predict_url_threat(u)["phishing_probability"] >= 0.3]
    missed = [u for u in REAL_SCAMS if hf_engine.predict_url_threat(u)["phishing_probability"] <= 0.4]
    engine_ok = not bad_safe and not missed
    if engine_ok:
        print("  OK: all 12 real sites SAFE and all 8 scams caught")
    else:
        if bad_safe: print("  FALSE ALARMS on real sites:", bad_safe)
        if missed:   print("  MISSED scams:", missed)

    # ---------- verdict ----------
    print("\n" + "=" * 60)
    problems = []
    if auc >= 0.995: problems.append("ROC-AUC 0.995+ is suspiciously high: check for a data leak first")
    if shuf_auc > 0.58: problems.append("Shuffled-label AUC is too far above 0.5: the test may be leaking")
    if not engine_ok: problems.append("Full-engine real-world check failed (see above)")
    if problems:
        print("VERDICT: NOT ENOUGH YET")
        for x in problems: print("  -", x)
    elif prec >= 0.85 and rec >= 0.85:
        print("VERDICT: ENOUGH")
        print("  You may quote these numbers (they are on unseen domains).")
    elif prec >= 0.90 and rec >= 0.70 and auc >= 0.88:
        print("VERDICT: ENOUGH TO PRESENT HONESTLY (recall is below our 0.85 target)")
        print("  Quote the numbers as they are and say the limit out loud:")
        print("  ML looks only at the domain name, and the rules layer covers look-alike tricks.")
    else:
        print("VERDICT: NOT ENOUGH YET")
        if prec < 0.90: print("  - Precision is low: add safe sites to ml/data/my_safe.txt")
        if rec < 0.70:  print("  - Recall is low: add scams to ml/data/my_phish.txt")
    print("Saved ml/model.json. Restart the server (python main.py) to use it.")
    print("=" * 60)


if __name__ == "__main__":
    main()