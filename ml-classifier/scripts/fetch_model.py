"""Download the files a model card pins, and verify their sha256.

Run from the ml-classifier/ directory:
    python -m scripts.fetch_model [--card PATH] [--dest DIR]

Defaults come from MODEL_CARD_PATH and MODEL_DIR. Idempotent: files that already
match the card are not downloaded again, so the compose `ml` service runs this
on every start. HF_TOKEN is used if set; the current model is public.
"""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from app.card import ModelCard, ModelLoadError, file_sha256, load_card
from app.config import get_settings

Downloader = Callable[[str, str, str, Path], Path]


def hf_download(repo: str, revision: str, filename: str, dest: Path) -> Path:
    """Download one file of a pinned Hugging Face revision into dest."""
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(
            repo_id=repo,
            filename=filename,
            revision=revision,
            local_dir=dest,
            token=os.environ.get("HF_TOKEN") or None,
        )
    )


def fetch(card: ModelCard, dest: Path, download: Downloader | None = None) -> list[str]:
    """Make dest hold exactly the card's files; return the names downloaded."""
    download = download or hf_download
    dest.mkdir(parents=True, exist_ok=True)
    fetched = []
    for name, expected in card.files.items():
        target = dest / name
        if target.is_file() and file_sha256(target) == expected:
            continue
        download(card.repo, card.revision, name, dest)
        actual = file_sha256(target) if target.is_file() else None
        if actual != expected:
            target.unlink(missing_ok=True)
            raise ModelLoadError(
                f"{name} from {card.repo}@{card.revision} has sha256 {actual}, "
                f"but the card pins {expected}"
            )
        fetched.append(name)
    return fetched


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, default=Path(settings.model_card_path))
    parser.add_argument("--dest", type=Path, default=Path(settings.model_dir))
    args = parser.parse_args(argv)

    try:
        card = load_card(args.card)
        # Looked up at call time so tests can replace hf_download.
        fetched = fetch(card, args.dest, hf_download)
    except ModelLoadError as exc:
        print(f"fetch_model: {exc}", file=sys.stderr)
        return 1
    state = f"downloaded {', '.join(fetched)}" if fetched else "already up to date"
    print(f"fetch_model: {card.model_version} in {args.dest}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
