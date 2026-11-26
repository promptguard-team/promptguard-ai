"""Report a model's behaviour across the threshold grid.

Deliberately not a test. Metrics depend on the artifact, which arrives from
outside this repository and will change; pinning them in CI would either break
on every new model or be loosened until it proved nothing.

Run from the ml-classifier/ directory (it imports `app` and `scripts`):
    python -m scripts.evaluate models/xlm-roberta-pi.card.json data/eval.csv
    python -m scripts.evaluate models/xlm-roberta-pi.card.json data/eval.csv --adversarial
(weights from MODEL_DIR, default models/xlm-roberta-pi; fetch them first)

The evaluation CSV has columns text,label (label in {injection, clean}) and optionally category,lang.

The evaluation set MUST NOT overlap the data the model was trained on. If it
does, the baseline numbers describe memorisation, and the --adversarial recall
drop is meaningless: the model is recognising the original examples rather than
resisting their obfuscated forms. This script cannot check that; the caller
must guarantee it.

Use the baseline table to choose the block and review thresholds; the values
currently configured in the gateway (0.90 / 0.60) are unmeasured placeholders.
"""

import argparse
from pathlib import Path

from app.config import get_settings
from app.model import ModelBundle
from scripts.adversarial import TRANSFORMS, obfuscate
from scripts.evalcore import Row, Scored, grid_table, load_rows


def _report(bundle: ModelBundle, rows: list[Row], title: str) -> None:
    scored = [Scored(row, bundle.predict(row.text).score) for row in rows]
    positives = sum(1 for item in scored if item.row.label == "injection")
    print(
        f"\n{title}  (n={len(scored)}, injection={positives}, "
        f"clean={len(scored) - positives})"
    )
    print(grid_table(scored))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--adversarial", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    bundle = ModelBundle.load(
        args.card,
        args.model_dir or Path(settings.model_dir),
        settings.classifier_max_windows,
    )
    if bundle.is_stub:
        print("WARNING: this is a stub model. These numbers mean nothing.")

    rows = load_rows(args.dataset)
    _report(bundle, rows, "baseline")

    if args.adversarial:
        attacks = [row for row in rows if row.label == "injection"]
        for name in sorted(TRANSFORMS):
            transformed = [
                Row(obfuscate(row.text, name), row.label, row.category, row.lang)
                for row in attacks
            ]
            _report(bundle, transformed, f"adversarial: {name}")


if __name__ == "__main__":
    main()
