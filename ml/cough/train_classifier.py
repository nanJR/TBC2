"""Train a TB-vs-Healthy cough classifier and report how good it really is.

Needs the features from extract_features.py first. Run from the ml/ folder:
    uv run python cough/train_classifier.py

Scores are per PERSON, not per clip: one person has many clips, so a person's
score is the average of their clip scores, and every metric counts people.

What it reports:
1. The main model (trained on the given train split, threshold set on val so it
   catches >=90% of TB people), scored on the test people:
   a. all test people, and
   b. TBscreen people only (no Coswara), the fairer test.
2. Shortcut check: can the same features tell Coswara (home) recordings apart
   from TBscreen (clinic) non-TB recordings? Both are "Healthy", so if they can,
   a model could be learning "where was this recorded" instead of TB.
3. TBscreen-only cross-validation: train and test only on clinic people, 5 times
   over different groups of people, so every TBscreen person is tested once.
   With just 4 non-TB people in the official test split, this is the more
   trustworthy number.

Output:
- checkpoints/cough_logreg.joblib  (the main model + threshold; git ignores it)
- cough/results/logreg.json        (the numbers, small enough to commit)
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Let this script import ml/evaluation.py, which lives one folder up.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import TARGET_SENSITIVITY, bootstrap_ci, pick_threshold, report

ROOT = Path(__file__).resolve().parents[2]
FEATURES_FILE = ROOT / "data" / "processed" / "cough_features.npz"
CHECKPOINT_DIR = ROOT / "ml" / "checkpoints"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def make_model(c: float):
    return make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=5000))


def sample_weights(labels: np.ndarray, person: np.ndarray) -> np.ndarray:
    """Weights so that every person counts equally, and both classes count equally.

    Without this, a person with 40 clips would count 40 times as much as a
    person with 1 clip.
    """
    clips_per_person = {p: n for p, n in zip(*np.unique(person, return_counts=True))}
    weights = np.array([1.0 / clips_per_person[p] for p in person])
    for label in (0, 1):
        is_label = labels == label
        weights[is_label] /= weights[is_label].sum()
    return weights * len(labels)


def per_person(scores, labels, person, source):
    """Average clip scores into one score per person."""
    people = np.unique(person)
    first = {p: i for i, p in reversed(list(enumerate(person)))}  # any clip of each person
    return (
        np.array([scores[person == p].mean() for p in people]),
        np.array([labels[first[p]] for p in people]),
        np.array([source[first[p]] for p in people]),
    )


def show(name: str, r: dict) -> None:
    ci = r["ci95"]
    print(f"  {name}: {r['n']} people ({r['n_tb']} TB)")
    print(f"    AUROC       {r['auroc']:.3f}  95% CI {ci['auroc']}")
    print(f"    sensitivity {r['sensitivity']:.3f}  95% CI {ci['sensitivity']}")
    print(f"    specificity {r['specificity']:.3f}  95% CI {ci['specificity']}")


def main() -> None:
    data = np.load(FEATURES_FILE)
    x, y, person, source, split = (
        data[k] for k in ["features", "labels", "person", "source", "split"]
    )
    results = {}

    # ---- 1. Main model on the official splits --------------------------------
    train, val, test = (split == s for s in ["train", "val", "test"])
    print(f"Train: {train.sum()} clips from {len(np.unique(person[train]))} people")

    best = None
    for c in [0.001, 0.01, 0.1, 1.0]:
        model = make_model(c)
        model.fit(
            x[train],
            y[train],
            logisticregression__sample_weight=sample_weights(y[train], person[train]),
        )
        val_scores, val_labels, _ = per_person(
            model.predict_proba(x[val])[:, 1], y[val], person[val], source[val]
        )
        auroc = roc_auc_score(val_labels, val_scores)
        print(f"  C={c:<6} val AUROC (people) {auroc:.3f}")
        if best is None or auroc > best[1]:
            best = (model, auroc, c)
    model, _, best_c = best

    val_scores, val_labels, _ = per_person(
        model.predict_proba(x[val])[:, 1], y[val], person[val], source[val]
    )
    threshold = pick_threshold(val_labels, val_scores, TARGET_SENSITIVITY)
    print(f"Chosen C={best_c}, threshold {threshold:.4f} (set on val)")

    # Test is looked at only here, after every choice above is fixed.
    test_scores, test_labels, test_source = per_person(
        model.predict_proba(x[test])[:, 1], y[test], person[test], source[test]
    )
    results["test_all_people"] = report(test_labels, test_scores, threshold)
    show("test, all people", results["test_all_people"])
    clinic = test_source == "TBscreen"
    results["test_tbscreen_only"] = report(test_labels[clinic], test_scores[clinic], threshold)
    show("test, TBscreen people only", results["test_tbscreen_only"])

    # ---- 2. Shortcut check: Coswara vs TBscreen, healthy people only ---------
    healthy = (y == 0) & (split != "test")
    is_coswara = (source[healthy] == "Coswara").astype(int)
    oof = np.zeros(healthy.sum())
    folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=0)
    for fit_idx, held_idx in folds.split(x[healthy], is_coswara, person[healthy]):
        detector = make_model(best_c).fit(x[healthy][fit_idx], is_coswara[fit_idx])
        oof[held_idx] = detector.predict_proba(x[healthy][held_idx])[:, 1]
    src_scores, src_labels, _ = per_person(oof, is_coswara, person[healthy], source[healthy])
    shortcut_auroc = roc_auc_score(src_labels, src_scores)
    results["shortcut_check_auroc_coswara_vs_tbscreen_healthy"] = round(shortcut_auroc, 4)
    print(f"Shortcut check: Coswara vs TBscreen healthy, AUROC {shortcut_auroc:.3f}")
    print("  (0.5 = can't tell them apart; near 1.0 = recording source is easy to spot)")

    # ---- 3. TBscreen-only cross-validation, all splits pooled ----------------
    clinic = source == "TBscreen"
    oof = np.zeros(clinic.sum())
    for fit_idx, held_idx in folds.split(x[clinic], y[clinic], person[clinic]):
        fold_model = make_model(best_c)
        fold_model.fit(
            x[clinic][fit_idx],
            y[clinic][fit_idx],
            logisticregression__sample_weight=sample_weights(
                y[clinic][fit_idx], person[clinic][fit_idx]
            ),
        )
        oof[held_idx] = fold_model.predict_proba(x[clinic][held_idx])[:, 1]
    cv_scores, cv_labels, _ = per_person(oof, y[clinic], person[clinic], source[clinic])
    cv_auroc = roc_auc_score(cv_labels, cv_scores)
    cv_ci = bootstrap_ci(cv_labels, cv_scores, threshold=0.5)["auroc"]
    results["tbscreen_only_5fold_cv"] = {
        "n": len(cv_labels),
        "n_tb": int(cv_labels.sum()),
        "auroc": round(cv_auroc, 4),
        "auroc_ci95": cv_ci,
    }
    print(
        f"TBscreen-only 5-fold CV: {len(cv_labels)} people ({cv_labels.sum()} TB), "
        f"AUROC {cv_auroc:.3f}  95% CI {cv_ci}"
    )

    CHECKPOINT_DIR.mkdir(exist_ok=True)
    joblib.dump({"pipeline": model, "threshold": threshold}, CHECKPOINT_DIR / "cough_logreg.joblib")

    RESULTS_DIR.mkdir(exist_ok=True)
    results = {
        "features": "1 s clip at 16 kHz -> 64 log-mel + 20 MFCC, mean and std over time",
        "classifier": f"logistic regression, C={best_c}, person- and class-balanced weights",
        "threshold": threshold,
        **results,
    }
    (RESULTS_DIR / "logreg.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Saved results -> {RESULTS_DIR / 'logreg.json'}")


if __name__ == "__main__":
    main()
