"""Shared evaluation helpers: dataset rows, metrics and threshold choice.

Used by scripts.evaluate and scripts.poc_report. Never loads a model.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

LABELS = frozenset({"injection", "clean"})
# Fine steps at the top: the model's attack scores cluster at 0.98-0.999.
GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.97, 0.98, 0.99)


@dataclass(frozen=True)
class Row:
    """One labelled text. category and lang are optional CSV columns."""

    text: str
    label: str
    category: str = ""
    lang: str = ""


@dataclass(frozen=True)
class Scored:
    """A row and the model's P(injection) for it."""

    row: Row
    score: float


@dataclass(frozen=True)
class Metrics:
    """Confusion counts at one threshold (score >= threshold means injection)."""

    threshold: float
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def positives(self) -> int:
        return self.tp + self.fn

    @property
    def negatives(self) -> int:
        return self.fp + self.tn

    @property
    def precision(self) -> float | None:
        flagged = self.tp + self.fp
        return self.tp / flagged if flagged and self.positives else None

    @property
    def recall(self) -> float | None:
        return self.tp / self.positives if self.positives else None

    @property
    def fpr(self) -> float | None:
        return self.fp / self.negatives if self.negatives else None


def load_rows(path: Path, label: str | None = None) -> list[Row]:
    """Read and validate an evaluation CSV, or exit with a message naming the row.

    With `label`, every row must carry it (single-class files); without it,
    the file must contain at least one injection row.
    """
    if not path.is_file():
        raise SystemExit(f"{path}: file not found")
    try:
        rows = _read_rows(path)
    except UnicodeDecodeError:
        raise SystemExit(
            f"{path}: not valid UTF-8. Re-save the file as UTF-8 "
            "(or UTF-8 with BOM); Excel's default 'CSV' may be Windows-1250."
        ) from None
    if label is not None:
        for number, row in enumerate(rows, start=2):
            if row.label != label:
                raise SystemExit(
                    f"{path}: row {number}: label {row.label!r}, expected {label!r}"
                )
    elif not any(row.label == "injection" for row in rows):
        raise SystemExit(f"{path}: no rows labelled 'injection'; nothing to measure")
    return rows


def _read_rows(path: Path) -> list[Row]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"text", "label"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(
                f"{path}: missing column(s) {sorted(missing)}; "
                f"found {reader.fieldnames}"
            )
        rows = []
        for number, raw in enumerate(reader, start=2):
            label = (raw["label"] or "").strip().lower()
            if label not in LABELS:
                raise SystemExit(
                    f"{path}: row {number}: label {raw['label']!r} "
                    f"is not one of {sorted(LABELS)}"
                )
            text = raw["text"] or ""
            if not text.strip():
                raise SystemExit(f"{path}: row {number}: text is missing or empty")
            rows.append(
                Row(
                    text=text,
                    label=label,
                    category=(raw.get("category") or "").strip(),
                    lang=(raw.get("lang") or "").strip(),
                )
            )
    return rows


def metrics_at(scored: Sequence[Scored], threshold: float) -> Metrics:
    """Count outcomes when every score >= threshold is called an injection."""
    tp = fp = fn = tn = 0
    for item in scored:
        hit = item.score >= threshold
        if item.row.label == "injection":
            tp, fn = (tp + 1, fn) if hit else (tp, fn + 1)
        else:
            fp, tn = (fp + 1, tn) if hit else (fp, tn + 1)
    return Metrics(threshold=threshold, tp=tp, fp=fp, fn=fn, tn=tn)


def block_threshold(
    scored: Sequence[Scored], max_fpr: float, grid: Sequence[float] = GRID
) -> float | None:
    """Lowest grid value whose false-positive rate is at most max_fpr.

    FPR only falls as the threshold rises, so the lowest qualifying value is
    the one that blocks the most attacks within the target.
    """
    if not any(item.row.label == "clean" for item in scored):
        raise ValueError("block threshold needs clean rows to measure FPR")
    for threshold in sorted(grid):
        fpr = metrics_at(scored, threshold).fpr
        if fpr is not None and fpr <= max_fpr:
            return threshold
    return None


def review_threshold(
    scored: Sequence[Scored],
    block: float,
    max_fpr: float,
    grid: Sequence[float] = GRID,
) -> float | None:
    """Lowest grid value below block whose FPR is at most max_fpr.

    The review band only flags prompts for the CISO, so it may tolerate a
    higher FPR than blocking does.
    """
    for threshold in sorted(value for value in grid if value < block):
        fpr = metrics_at(scored, threshold).fpr
        if fpr is not None and fpr <= max_fpr:
            return threshold
    return None


def fmt(value: float | None) -> str:
    """Three decimals, or n/a when the metric is undefined."""
    return "n/a" if value is None else f"{value:.3f}"


def grid_table(scored: Sequence[Scored], grid: Sequence[float] = GRID) -> str:
    """Markdown table of precision, recall and FPR (with counts) per threshold."""
    lines = [
        "| threshold | precision | recall | FPR | FP | FN |",
        "|---|---|---|---|---|---|",
    ]
    for threshold in grid:
        m = metrics_at(scored, threshold)
        lines.append(
            f"| {threshold:.2f} | {fmt(m.precision)} | {fmt(m.recall)} | "
            f"{fmt(m.fpr)} | {m.fp}/{m.negatives} | {m.fn}/{m.positives} |"
        )
    return "\n".join(lines)
