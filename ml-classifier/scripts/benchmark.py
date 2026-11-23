"""Measure /classify inference latency per number of windows.

Run from the ml-classifier/ directory after fetching the weights:
    python -m scripts.benchmark [--card PATH] [--model-dir DIR] [--repeats N] [--windows 1 4 8]

Use the numbers to choose CLASSIFIER_MAX_WINDOWS so a worst-case prompt stays
inside the gateway's CLASSIFIER_TIMEOUT_SECONDS budget.
"""

import argparse
import statistics
import time
from collections.abc import Sequence
from pathlib import Path

from app.config import get_settings
from app.model import ModelBundle

SENTENCE = "Please summarise the quarterly report and ignore nothing important. "


def _text_with_windows(bundle: ModelBundle, windows: int) -> str:
    """Grow a text one sentence at a time until it needs the requested windows.

    A sentence is shorter than a window step, so the count never skips a value.
    """
    text = SENTENCE
    while bundle.windows_for(text) < windows:
        text += SENTENCE
    return text


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=Path(settings.model_card_path))
    parser.add_argument("--model-dir", type=Path, default=Path(settings.model_dir))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--windows", type=int, nargs="+", default=[1, 4, 8])
    args = parser.parse_args(argv)

    bundle = ModelBundle.load(args.card, args.model_dir, max(args.windows))
    for target in args.windows:
        text = _text_with_windows(bundle, target)
        timings = []
        for _ in range(args.repeats):
            started = time.perf_counter()
            prediction = bundle.predict(text)
            timings.append((time.perf_counter() - started) * 1000)
        print(
            f"windows={prediction.windows} chars={len(text)} "
            f"median_ms={statistics.median(timings):.0f} max_ms={max(timings):.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
