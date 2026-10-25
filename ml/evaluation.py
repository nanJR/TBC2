"""Scoring helpers shared by every model (cough, chest X-ray, ...).

Scripts in ml/<model>/ import this with:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from evaluation import ...

Words used below:
- sensitivity: share of TB cases the model flags (missing TB is the costly mistake)
- specificity: share of healthy people the model correctly clears
- AUROC: how well the scores rank TB above healthy, over every possible threshold
  (1.0 = perfect, 0.5 = coin flip)
"""

import numpy as np
from sklearn.metrics import roc_auc_score

# WHO target product profile for a TB triage test.
TARGET_SENSITIVITY = 0.90
TARGET_SPECIFICITY = 0.70


def sens_spec(labels: np.ndarray, scores: np.ndarray, threshold: float) -> tuple[float, float]:
    """Sensitivity and specificity when everyone scoring >= threshold is flagged."""
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
    """95% confidence intervals: re-score many random resamples of the test set.

    The wider the interval, the less the single number can be trusted
    (small test sets give wide intervals).
    """
    rng = np.random.default_rng(seed)
    results = {"auroc": [], "sensitivity": [], "specificity": []}
    for _ in range(n_rounds):
        idx = rng.integers(0, len(labels), len(labels))
        y, s = labels[idx], scores[idx]
        if len(set(y)) < 2:  # a tiny resample can miss one class entirely; skip it
            continue
        results["auroc"].append(roc_auc_score(y, s))
        sensitivity, specificity = sens_spec(y, s, threshold)
        results["sensitivity"].append(sensitivity)
        results["specificity"].append(specificity)
    return {
        k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
        for k, v in results.items()
    }


def report(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    """AUROC, sensitivity and specificity at `threshold`, each with a 95% CI."""
    sensitivity, specificity = sens_spec(labels, scores, threshold)
    return {
        "n": len(labels),
        "n_tb": int(labels.sum()),
        "auroc": round(float(roc_auc_score(labels, scores)), 4),
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "ci95": bootstrap_ci(labels, scores, threshold),
        "meets_who_triage_target": sensitivity >= TARGET_SENSITIVITY
        and specificity >= TARGET_SPECIFICITY,
    }
