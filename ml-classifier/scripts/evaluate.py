"""Report a model's behaviour across the threshold grid.

Deliberately not a test. Metrics depend on the artifact, which arrives from
outside this repository and will change; pinning them in CI would either break
on every new model or be loosened until it proved nothing.

Run from the ml-classifier/ directory (it imports `app` and `scripts`):
    python -m scripts.evaluate models/<artifact>.joblib data/eval.csv
    python -m scripts.evaluate models/<artifact>.joblib data/eval.csv --adversarial

The evaluation CSV has two columns: text,label  (label in {injection, clean}).

The evaluation set MUST NOT overlap the data the model was trained on. If it
does, the baseline numbers describe memorisation, and the --adversarial recall
drop is meaningless: the model is recognising the original examples rather than
resisting their obfuscated forms. This script cannot check that; the caller
must guarantee it.

Use the baseline table to choose the block and review thresholds; the values
currently configured in the gateway (0.90 / 0.60) are unmeasured placeholders.
"""

import argparse
import csv
from pathlib import Path

from app.model import ModelBundle
from scripts.adversarial import TRANSFORMS, obfuscate

LABELS = {"injection", "clean"}
GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


def _load(path: Path) -> list[tuple[str, str]]:
    try:
        return _read_rows(path)
    except UnicodeDecodeError:
        raise SystemExit(
            f"{path}: not valid UTF-8. Re-save the file as UTF-8 "
            "(or UTF-8 with BOM); Excel's default 'CSV' may be Windows-1250."
        ) from None


def _read_rows(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"text", "label"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                f"{path}: missing column(s) {sorted(missing)}; "
                f"found {reader.fieldnames}"
            )
        rows = []
        for number, row in enumerate(reader, start=2):
            label = (row["label"] or "").strip().lower()
            if label not in LABELS:
                raise SystemExit(
                    f"{path}: row {number}: label {row['label']!r} "
                    f"is not one of {sorted(LABELS)}"
                )
            if not (row["text"] or "").strip():
                raise SystemExit(f"{path}: row {number}: text is missing or empty")
            rows.append((row["text"], label))
    if not any(label == "injection" for _, label in rows):
        raise SystemExit(f"{path}: no rows labelled 'injection'; nothing to measure")
    return rows


def _report(bundle: ModelBundle, rows: list[tuple[str, str]], title: str) -> None:
    scores = [(bundle.predict(text).score, label) for text, label in rows]
    positives = sum(1 for _, label in scores if label == "injection")
    negatives = len(scores) - positives

    print(f"\n{title}  (n={len(scores)}, injection={positives}, clean={negatives})")
    print(f"{'threshold':>10} {'precision':>10} {'recall':>8} {'FPR':>8}")
    for threshold in GRID:
        tp = sum(1 for s, lab in scores if s >= threshold and lab == "injection")
        fp = sum(1 for s, lab in scores if s >= threshold and lab == "clean")
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / positives if positives else 0.0
        fpr = fp / negatives if negatives else 0.0
        shown = f"{precision:.3f}" if precision is not None else "n/a"
        print(f"{threshold:>10.2f} {shown:>10} {recall:>8.3f} {fpr:>8.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    bundle = ModelBundle.load(args.model)
    if bundle.is_stub:
        print("WARNING: this is the stub artifact. These numbers mean nothing.")

    rows = _load(args.dataset)
    _report(bundle, rows, "baseline")

    if args.adversarial:
        attacks = [(text, label) for text, label in rows if label == "injection"]
        for name in sorted(TRANSFORMS):
            transformed = [(obfuscate(text, name), label) for text, label in attacks]
            _report(bundle, transformed, f"adversarial: {name}")


if __name__ == "__main__":
    main()
