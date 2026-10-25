"""Train a TB-vs-Normal classifier on the X-ray features and report how good it is.

Needs the features from extract_features.py first. Run from the ml/ folder:
    uv run python cxr/train_classifier.py
    uv run python cxr/train_classifier.py --model efficientnet_b0

What it does, in order:
1. Fits logistic regression on the train features, with class weights so the
   smaller TB class counts as much as the Normal class (instead of deleting images).
2. Picks the regularisation strength C with the best AUROC on val.
3. Picks the decision threshold on val: the highest one that still catches at
   least 90% of TB cases (WHO triage target: >=90% sensitivity, >=70% specificity).
4. Only then looks at test, once, and reports AUROC, sensitivity and specificity
   with 95% confidence intervals (bootstrap).

Output:
- checkpoints/cxr_<model>.joblib  (the fitted model + threshold; git ignores it)
- cxr/results/<model>.json        (the numbers, small enough to commit)
"""

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Let this script import ml/evaluation.py, which lives one folder up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import TARGET_SENSITIVITY, pick_threshold, report

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "processed" / "cxr_features"
CHECKPOINT_DIR = ROOT / "ml" / "checkpoints"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load(model_name: str, split: str) -> tuple[np.ndarray, np.ndarray]:
    data = np.load(FEATURES_DIR / model_name / f"{split}.npz")
    return data["features"], data["labels"]


def show(name: str, r: dict) -> None:
    ci = r["ci95"]
    print(f"  {name}: {r['n']} images ({r['n_tb']} TB)")
    print(f"    AUROC       {r['auroc']:.3f}  95% CI {ci['auroc']}")
    print(f"    sensitivity {r['sensitivity']:.3f}  95% CI {ci['sensitivity']}")
    print(f"    specificity {r['specificity']:.3f}  95% CI {ci['specificity']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="efficientnet_b0", help="feature folder to use")
    args = parser.parse_args()

    x_train, y_train = load(args.model, "train")
    x_val, y_val = load(args.model, "val")

    # Class weights: each TB image counts n_normal / n_tb times (about 1.4x).
    tb_weight = (y_train == 0).sum() / (y_train == 1).sum()
    print(f"Train: {len(y_train)} images, TB weight {tb_weight:.2f}")

    # Try a few regularisation strengths; keep the one with the best val AUROC.
    best = None
    for c in [0.001, 0.01, 0.1, 1.0]:
        clf = make_pipeline(
            StandardScaler(),  # put every feature on the same scale first
            LogisticRegression(C=c, class_weight={0: 1.0, 1: tb_weight}, max_iter=2000),
        )
        clf.fit(x_train, y_train)
        val_auroc = roc_auc_score(y_val, clf.predict_proba(x_val)[:, 1])
        print(f"  C={c:<6} val AUROC {val_auroc:.4f}")
        if best is None or val_auroc > best[1]:
            best = (clf, val_auroc, c)
    clf, _, best_c = best

    val_scores = clf.predict_proba(x_val)[:, 1]
    threshold = pick_threshold(y_val, val_scores, TARGET_SENSITIVITY)
    print(f"Chosen C={best_c}, threshold {threshold:.4f} (set on val)")
    val_report = report(y_val, val_scores, threshold)
    show("val", val_report)

    # Test is looked at only here, after every choice above is fixed.
    x_test, y_test = load(args.model, "test")
    test_report = report(y_test, clf.predict_proba(x_test)[:, 1], threshold)
    show("test", test_report)
    met = "met" if test_report["meets_who_triage_target"] else "NOT met"
    print(f"  WHO triage target (>=90% sens, >=70% spec) on test: {met}")

    CHECKPOINT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {"pipeline": clf, "threshold": threshold}, CHECKPOINT_DIR / f"cxr_{args.model}.joblib"
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    results = {
        "feature_model": args.model,
        "classifier": f"logistic regression, C={best_c}, TB class weight {tb_weight:.2f}",
        "threshold": threshold,
        "val": val_report,
        "test": test_report,
    }
    (RESULTS_DIR / f"{args.model}.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Saved results -> {RESULTS_DIR / f'{args.model}.json'}")


if __name__ == "__main__":
    main()
