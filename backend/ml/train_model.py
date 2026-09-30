# backend/ml/train_model.py   (pure numpy: works even when scipy/scikit-learn are blocked)
# Run from the backend folder:   python ml/train_model.py --csv ml/data/urls.csv
import argparse, csv, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from services.ml_service import extract_features, FEATURE_NAMES

OUT = os.path.join(os.path.dirname(__file__), "model.json")

def demo_data(n=600):
    """ONLY to test the pipeline. Metrics from this are NOT real!"""
    random.seed(1)
    safe = ["google.com", "github.com", "wikipedia.org", "amazon.in", "flipkart.com",
            "paytm.com", "phonepe.com", "sbi.co.in", "icicibank.com", "irctc.co.in"]
    words = ["verify", "kyc", "reward", "claim", "secure", "login", "refund"]
    brands = ["paytm", "sbi", "hdfc", "amazon", "phonepe", "google"]
    tlds = ["xyz", "top", "tk", "click", "buzz", "ml"]
    rows = []
    for _ in range(n):
        rows.append((f"https://{random.choice(safe)}", 0))
        rows.append((f"https://{random.choice(brands)}-{random.choice(words)}.{random.choice(tlds)}", 1))
    return rows

def sigmoid(z): return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

def auc_score(y, p):
    order = np.argsort(p); ranks = np.empty(len(p)); ranks[order] = np.arange(1, len(p) + 1)
    for v in np.unique(p):                      # average ranks for ties
        m = p == v
        if m.sum() > 1: ranks[m] = ranks[m].mean()
    n1, n0 = (y == 1).sum(), (y == 0).sum()
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def fit(X, y, l2=0.05, lr=0.1, steps=3000):
    w = np.zeros(X.shape[1]); b = 0.0
    for _ in range(steps):
        p = sigmoid(X @ w + b); g = p - y
        w -= lr * (X.T @ g / len(y) + l2 * w); b -= lr * g.mean()
    return w, b

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv"); ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        print("⚠️  DEMO DATA: metrics below are NOT real."); rows = demo_data()
    else:
        rows = [(r["url"], int(r["label"])) for r in csv.DictReader(open(a.csv, encoding="utf-8"))]
    X = np.array([extract_features(u) for u, _ in rows], dtype=float); y = np.array([l for _, l in rows])

    rng = np.random.RandomState(42); idx = rng.permutation(len(y)); cut = int(0.8 * len(y))
    tr, te = idx[:cut], idx[cut:]
    mean, std = X[tr].mean(0), X[tr].std(0); std[std < 1e-9] = 1.0
    Z = (X - mean) / std
    w, b = fit(Z[tr], y[tr].astype(float))

    p = sigmoid(Z[te] @ w + b); pred = (p > 0.5).astype(int); yt = y[te]
    tp = int(((pred == 1) & (yt == 1)).sum()); fp = int(((pred == 1) & (yt == 0)).sum())
    fn = int(((pred == 0) & (yt == 1)).sum()); tn = int(((pred == 0) & (yt == 0)).sum())
    prec = tp / max(tp + fp, 1); rec = tp / max(tp + fn, 1); f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    auc = auc_score(yt, p)
    print(f"Test size: {len(yt)}   Train size: {len(tr)}")
    print(f"Precision: {prec:.4f}   Recall: {rec:.4f}   F1: {f1:.4f}   ROC-AUC: {auc:.4f}")
    print(f"Confusion matrix  [[TN={tn}, FP={fp}], [FN={fn}, TP={tp}]]")
    top = sorted(zip(np.abs(w), w, FEATURE_NAMES), reverse=True)[:5]
    print("Most important features:", [(n, round(float(v), 2)) for _, v, n in top])

    json.dump({"weights": w.tolist(), "bias": float(b), "mean": mean.tolist(), "std": std.tolist(),
               "feature_names": FEATURE_NAMES,
               "metrics": {"roc_auc": round(float(auc), 4), "precision": round(prec, 4),
                           "recall": round(rec, 4), "f1": round(f1, 4), "demo": a.demo}},
              open(OUT, "w"))
    print("✅ Saved ml/model.json")

if __name__ == "__main__":
    main()