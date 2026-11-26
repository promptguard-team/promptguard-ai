"""Run the PoC suites against the served model and print Markdown tables.

Covers the model side of the attack taxonomy: LLM01 direct injection (our
PL/EN set), LLM02 indirect injection (attacks pasted inside documents) and
MITRE ATLAS AML.T0015 evasion (obfuscated attacks), plus the S-Labs held-out
test split, and recommends gateway thresholds.

Run from the ml-classifier/ directory:
    python -m scripts.fetch_model
    python -m scripts.fetch_eval_data
    python -m scripts.poc_report [--quick] [--threads 2] > poc-output.md

Scores go through ModelBundle.predict with the service's window cap, so they
describe what the gateway sees. Not a test: the numbers are not pinned in CI.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import torch

from app.card import ModelLoadError
from app.config import get_settings
from app.model import ModelBundle
from scripts.adversarial import TRANSFORMS, obfuscate
from scripts.evalcore import (
    GRID,
    Row,
    Scored,
    block_threshold,
    fmt,
    grid_table,
    load_rows,
    metrics_at,
    review_threshold,
)
from scripts.fetch_eval_data import DEST, DataError, load_slabs
from scripts.indirect import build_cases, pick_attacks
from scripts.leakage import find_overlap


def score_rows(bundle: ModelBundle, rows: Sequence[Row]) -> list[Scored]:
    return [Scored(row, bundle.predict(row.text).score) for row in rows]


def _hits(scores: Sequence[float], threshold: float) -> str:
    hits = sum(1 for score in scores if score >= threshold)
    return f"{hits}/{len(scores)}"


def _cell(text: str, width: int = 90) -> str:
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def category_table(scored: Sequence[Scored], block: float, review: float) -> str:
    groups: dict[tuple[str, str, str], list[float]] = {}
    for item in scored:
        key = (item.row.label, item.row.category, item.row.lang)
        groups.setdefault(key, []).append(item.score)
    lines = [
        "| label | category | lang | >= review | >= block |",
        "|---|---|---|---|---|",
    ]
    for (label, category, lang), scores in sorted(groups.items()):
        lines.append(
            f"| {label} | {category} | {lang} | {_hits(scores, review)} | "
            f"{_hits(scores, block)} |"
        )
    return "\n".join(lines)


def extremes_table(scored: Sequence[Scored], label: str, top: int) -> str:
    items = sorted(
        (item for item in scored if item.row.label == label),
        key=lambda item: item.score,
        reverse=label == "clean",
    )[:top]
    lines = ["| score | category | lang | text |", "|---|---|---|---|"]
    for item in items:
        lines.append(
            f"| {item.score:.3f} | {item.row.category} | {item.row.lang} | "
            f"{_cell(item.row.text)} |"
        )
    return "\n".join(lines)


def evasion_table(
    bundle: ModelBundle,
    attacks: Sequence[Row],
    baseline: Sequence[Scored],
    block: float,
    review: float,
) -> str:
    rows = [("none (original)", [item.score for item in baseline])]
    for name in sorted(TRANSFORMS):
        transformed = [
            Row(obfuscate(row.text, name), row.label, row.category, row.lang)
            for row in attacks
        ]
        rows.append((name, [item.score for item in score_rows(bundle, transformed)]))
    lines = ["| transform | >= review | >= block |", "|---|---|---|"]
    for name, scores in rows:
        lines.append(f"| {name} | {_hits(scores, review)} | {_hits(scores, block)} |")
    return "\n".join(lines)


def indirect_table(
    bundle: ModelBundle, attacks: Sequence[Row], block: float, review: float
) -> str:
    groups: dict[tuple[str, str, str], list[float]] = {}
    windows: dict[tuple[str, str, str], int] = {}
    for case in build_cases(attacks):
        prediction = bundle.predict(case.row.text)
        key = (case.carrier, case.length, case.position)
        groups.setdefault(key, []).append(prediction.score)
        windows[key] = prediction.windows
    lines = [
        "| carrier | length | attack position | windows | >= review | >= block |",
        "|---|---|---|---|---|---|",
    ]
    for (carrier, length, position), scores in sorted(groups.items()):
        lines.append(
            f"| {carrier} | {length} | {position} | "
            f"{windows[(carrier, length, position)]} | "
            f"{_hits(scores, review)} | {_hits(scores, block)} |"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=Path(settings.model_card_path))
    parser.add_argument("--model-dir", type=Path, default=Path(settings.model_dir))
    parser.add_argument("--clean", type=Path, default=Path("data/poc/clean.csv"))
    parser.add_argument("--attacks", type=Path, default=Path("data/poc/attacks.csv"))
    parser.add_argument("--slabs-dir", type=Path, default=DEST)
    # compose limits the service to 2 CPUs and sets CLASSIFIER_TORCH_THREADS=2.
    parser.add_argument(
        "--threads", type=int, default=settings.classifier_torch_threads or 2
    )
    parser.add_argument("--max-fpr", type=float, default=0.01)
    parser.add_argument("--review-max-fpr", type=float, default=0.10)
    parser.add_argument("--indirect-attacks", type=int, default=20)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--quick", action="store_true", help="skip S-Labs test")
    args = parser.parse_args(argv)

    try:
        clean = load_rows(args.clean, label="clean")
        attacks = load_rows(args.attacks, label="injection")
        train = load_slabs(args.slabs_dir / "data" / "train.csv")
        overlap = find_overlap(clean + attacks, [row.text for row in train])
        if overlap:
            listed = "\n".join(f"  {row.text!r}" for row in overlap)
            print(
                f"poc_report: rows overlap the training data:\n{listed}",
                file=sys.stderr,
            )
            return 1
        test = [] if args.quick else load_slabs(args.slabs_dir / "data" / "test.csv")
        torch.set_num_threads(args.threads)
        bundle = ModelBundle.load(
            args.card, args.model_dir, settings.classifier_max_windows
        )
    except (DataError, ModelLoadError) as exc:
        print(f"poc_report: {exc}", file=sys.stderr)
        return 1

    ours = score_rows(bundle, clean + attacks)
    block = block_threshold(ours, args.max_fpr)
    review = (
        review_threshold(ours, block, args.review_max_fpr)
        if block is not None
        else None
    )
    # Tables need a value even when no grid point meets the target.
    shown_block = block if block is not None else max(GRID)
    shown_review = review if review is not None else shown_block

    print(f"# PoC run: {bundle.version}")
    print(
        f"\nwindows cap {settings.classifier_max_windows}, torch threads "
        f"{args.threads}, clean {len(clean)}, attacks {len(attacks)}"
    )
    if bundle.is_stub:
        print("\nWARNING: stub model; these numbers mean nothing.")

    print("\n## Recommended thresholds\n")
    print(
        f"Recommended: block={fmt(block)} review={fmt(review)} "
        f"(block FPR target {args.max_fpr:.0%}, review FPR target "
        f"{args.review_max_fpr:.0%}, on our clean prompts)"
    )
    for name, value in (("block", block), ("review", review)):
        if value is None:
            print(f"\nNo grid value meets the {name} target.")
            continue
        m = metrics_at(ours, value)
        print(
            f"\n{name} {value:.2f}: recall {fmt(m.recall)} ({m.tp}/{m.positives}), "
            f"FPR {fmt(m.fpr)} ({m.fp}/{m.negatives})"
        )

    print("\n## LLM01: direct injection, PL/EN set\n")
    print(grid_table(ours))
    print("\n## LLM01: per category\n")
    print(category_table(ours, shown_block, shown_review))
    print("\n## Highest-scoring clean prompts\n")
    print(extremes_table(ours, "clean", args.top))
    print("\n## Lowest-scoring attacks\n")
    print(extremes_table(ours, "injection", args.top))

    baseline = [item for item in ours if item.row.label == "injection"]
    print("\n## AML.T0015: evasion\n")
    print(evasion_table(bundle, attacks, baseline, shown_block, shown_review))

    print("\n## LLM02: indirect injection\n")
    chosen = pick_attacks(attacks, args.indirect_attacks)
    print(f"{len(chosen)} attacks x 4 carriers x 2 lengths x 3 positions\n")
    print(indirect_table(bundle, chosen, shown_block, shown_review))

    if test:
        held_out = score_rows(bundle, test)
        print("\n## S-Labs held-out test split\n")
        print(grid_table(held_out))
        if block is not None:
            m = metrics_at(held_out, block)
            print(
                f"\nAt block {block:.2f}: recall {fmt(m.recall)}, FPR {fmt(m.fpr)} "
                f"({m.fp}/{m.negatives})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
