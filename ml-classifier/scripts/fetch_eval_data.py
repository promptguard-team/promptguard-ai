"""Download the evaluation splits a data card pins, and verify their sha256.

Run from the ml-classifier/ directory:
    python -m scripts.fetch_eval_data [--card PATH] [--dest DIR]

The S-Labs dataset is the one the model was trained on: its `train` split
feeds the leakage guard and its held-out `test` split is a second evaluation
set. Files land under DEST at their repository path (data/test.csv). Idempotent.
"""

import argparse
import csv
import json
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.card import file_sha256
from scripts.evalcore import Row

CARD = Path("data/s-labs.card.json")
DEST = Path("data/external/s-labs")

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_REPO = re.compile(r"[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*")
# Repository paths of CSV files; no "..", no absolute paths, no backslashes.
_FILE = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9_-]*/)*[A-Za-z0-9][A-Za-z0-9_.-]*\.csv")
_LABELS = {"0": "clean", "1": "injection"}

Downloader = Callable[[str, str, str, Path], Path]


class DataError(RuntimeError):
    """The data card or a data file is missing, invalid, or failed its hash."""


@dataclass(frozen=True)
class DataCard:
    repo: str
    revision: str
    files: dict[str, str]


def load_data_card(path: Path) -> DataCard:
    """Read and validate a data card, or raise DataError."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataError(f"unreadable data card at {path}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"data card at {path}: must be a JSON object")
    repo, revision, files = raw.get("repo"), raw.get("revision"), raw.get("files")
    if not isinstance(repo, str) or not _REPO.fullmatch(repo):
        raise DataError(f"data card at {path}: 'repo' must look like 'owner/name'")
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        raise DataError(f"data card at {path}: 'revision' must be a commit hash")
    if not isinstance(files, dict) or not files:
        raise DataError(f"data card at {path}: 'files' must map paths to sha256")
    for name, digest in files.items():
        if not isinstance(name, str) or not _FILE.fullmatch(name):
            raise DataError(f"data card at {path}: invalid file path {name!r}")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise DataError(f"data card at {path}: bad sha256 for {name}")
    return DataCard(repo=repo, revision=revision, files=dict(files))


def hf_dataset_download(repo: str, revision: str, filename: str, dest: Path) -> Path:
    """Download one file of a pinned Hugging Face dataset revision into dest."""
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import HfHubHTTPError

    try:
        return Path(
            hf_hub_download(
                repo_id=repo,
                filename=filename,
                revision=revision,
                repo_type="dataset",
                local_dir=dest,
                token=os.environ.get("HF_TOKEN") or None,
            )
        )
    except (HfHubHTTPError, OSError, ValueError) as exc:
        raise DataError(
            f"could not download {filename} from {repo}@{revision}: {exc}"
        ) from exc


def fetch(card: DataCard, dest: Path, download: Downloader | None = None) -> list[str]:
    """Ensure dest holds the card's files with matching sha256; return those downloaded."""
    download = download or hf_dataset_download
    dest.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name, expected in card.files.items():
        target = dest / name
        if target.is_file() and file_sha256(target) == expected:
            continue
        target.unlink(missing_ok=True)
        download(card.repo, card.revision, name, dest)
        actual = file_sha256(target) if target.is_file() else None
        if actual != expected:
            target.unlink(missing_ok=True)
            raise DataError(
                f"{name} from {card.repo}@{card.revision} has sha256 {actual}, "
                f"but the card pins {expected}"
            )
        fetched.append(name)
    return fetched


def load_slabs(path: Path) -> list[Row]:
    """Read an S-Labs split (text,label with 0/1) as Rows."""
    if not path.is_file():
        raise DataError(
            f"{path} not found; run `python -m scripts.fetch_eval_data` first"
        )
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for number, raw in enumerate(csv.DictReader(handle), start=2):
            label = _LABELS.get((raw.get("label") or "").strip())
            if label is None:
                raise DataError(f"{path}: row {number}: label {raw.get('label')!r}")
            rows.append(Row(raw["text"], label, "s-labs", "en"))
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=CARD)
    parser.add_argument("--dest", type=Path, default=DEST)
    args = parser.parse_args(argv)

    try:
        card = load_data_card(args.card)
        # Looked up at call time so tests can replace hf_dataset_download.
        fetched = fetch(card, args.dest, hf_dataset_download)
    except DataError as exc:
        print(f"fetch_eval_data: {exc}", file=sys.stderr)
        return 1
    state = f"downloaded {', '.join(fetched)}" if fetched else "already up to date"
    print(f"fetch_eval_data: {card.repo}@{card.revision[:7]} in {args.dest}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
