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
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
FEATURES_DIR = ROOT / "data" / "processed" / "cxr_features"
CHECKPOINT_DIR = ROOT / "ml" / "checkpoints"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
TARGET_SENSITIVITY = 0.90
TARGET_SPECIFICITY = 0.70


def load(model_name: str, split: str) -> tuple[np.ndarray, np.ndarray]:
    data = np.load(FEATURES_DIR / model_name / f"{split}.npz")
    return data["features"], data["labels"]


def sens_spec(labels: np.ndarray, scores: np.ndarray, threshold: float) -> tuple[float, float]:
    """Sensitivity = share of TB caught. Specificity = share of Normal correctly cleared."""
    flagged = scores >= threshold
    sensitivity = flagged[labels == 1].mean()
    specificity = (~flagged[labels == 0]).mean()
    return float(sensitivity), float(specificity)


def pick_threshold(labels: np.ndarray, scores: np.ndarray, min_sensitivity: float) -> float:
    """Highest threshold that still flags at least `min_sensitivity` of the TB cases.

    A higher threshold flags fewer people, so this is the setting with the best
    specificity that still meets the sensitivity target.
    """
    tb_scores = np.sort(scores[labels == 1])
    # Flagging everything >= the k-th lowest TB score catches (n - k) of n TB cases.
    k = int(np.floor(len(tb_scores) * (1 - min_sensitivity)))
    return float(tb_scores[k])


def bootstrap_ci(labels, scores, threshold, n_rounds=1000, seed=0) -> dict[str, list[float]]:
    """95% confidence intervals: re-score many random resamples of the test set."""
    rng = np.random.default_rng(seed)
    results = {"auroc": [], "sensitivity": [], "specificity": []}
    for _ in range(n_rounds):
        idx = rng.integers(0, len(labels), len(labels))
        y, s = labels[idx], scores[idx]
        results["auroc"].append(roc_auc_score(y, s))
        sensitivity, specificity = sens_spec(y, s, threshold)
        results["sensitivity"].append(sensitivity)
        results["specificity"].append(specificity)
    return {
        k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
        for k, v in results.items()
    }


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
    clf, val_auroc, best_c = best

    val_scores = clf.predict_proba(x_val)[:, 1]
    threshold = pick_threshold(y_val, val_scores, TARGET_SENSITIVITY)
    val_sens, val_spec = sens_spec(y_val, val_scores, threshold)
    print(f"Chosen C={best_c}, threshold {threshold:.4f} (set on val)")
    print(f"  val: AUROC {val_auroc:.4f}, sensitivity {val_sens:.3f}, specificity {val_spec:.3f}")

    # Test is looked at only here, after every choice above is fixed.
    x_test, y_test = load(args.model, "test")
    test_scores = clf.predict_proba(x_test)[:, 1]
    test_auroc = roc_auc_score(y_test, test_scores)
    test_sens, test_spec = sens_spec(y_test, test_scores, threshold)
    ci = bootstrap_ci(y_test, test_scores, threshold)
    meets = test_sens >= TARGET_SENSITIVITY and test_spec >= TARGET_SPECIFICITY
    print(f"  test: AUROC {test_auroc:.4f} {ci['auroc']}")
    print(f"        sensitivity {test_sens:.3f} {ci['sensitivity']}")
    print(f"        specificity {test_spec:.3f} {ci['specificity']}")
    print(f"  WHO triage target (>=90% sens, >=70% spec): {'met' if meets else 'NOT met'}")

    CHECKPOINT_DIR.mkdir(exist_ok=True)
    joblib.dump(
        {"pipeline": clf, "threshold": threshold}, CHECKPOINT_DIR / f"cxr_{args.model}.joblib"
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    results = {
        "feature_model": args.model,
        "classifier": f"logistic regression, C={best_c}, TB class weight {tb_weight:.2f}",
        "threshold": threshold,
        "val": {
            "n": len(y_val),
            "auroc": val_auroc,
            "sensitivity": val_sens,
            "specificity": val_spec,
        },
        "test": {
            "n": len(y_test),
            "n_tb": int(y_test.sum()),
            "auroc": test_auroc,
            "sensitivity": test_sens,
            "specificity": test_spec,
            "ci95": ci,
        },
        "meets_who_triage_target": meets,
    }
    (RESULTS_DIR / f"{args.model}.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Saved results -> {RESULTS_DIR / f'{args.model}.json'}")


if __name__ == "__main__":
    main()
