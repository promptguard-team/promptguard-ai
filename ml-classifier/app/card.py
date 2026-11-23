"""The model card: what the served weights are, and the checks that prove it."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The gateway stores model_version in audit_events.ml_model_version
# (String(64)); a longer value would pass here and fail every audit insert.
MAX_MODEL_VERSION_CHARS = 64

# The gateway scores a prompt with P(injection) alone, so the contract is
# binary. Labels are declared on the card because the model itself only knows
# LABEL_0/LABEL_1, and an inverted mapping would turn every verdict around.
REQUIRED_LABELS = frozenset({"clean", "injection"})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_CHUNK = 1 << 20


class ModelLoadError(RuntimeError):
    """The model card or weights are missing, unreadable, or failed validation."""


@dataclass(frozen=True)
class ModelCard:
    """The validated contents of a model card."""

    model_version: str
    stub: bool
    repo: str
    revision: str
    files: dict[str, str]
    labels: dict[int, str]
    max_tokens: int


def file_sha256(path: Path) -> str:
    """Return the hex sha256 of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(path: Path, problem: str) -> ModelLoadError:
    return ModelLoadError(f"model card at {path}: {problem}")


def _version(raw: dict[str, Any], path: Path) -> str:
    value = raw.get("model_version")
    if not isinstance(value, str) or not value:
        raise _fail(path, "'model_version' must be a non-empty string")
    if len(value) > MAX_MODEL_VERSION_CHARS:
        raise _fail(
            path,
            f"'model_version' is {len(value)} characters; "
            f"the limit is {MAX_MODEL_VERSION_CHARS}",
        )
    return value


def _source(raw: dict[str, Any], path: Path) -> tuple[str, str]:
    source = raw.get("source")
    if not isinstance(source, dict):
        raise _fail(path, "'source' must be an object with 'repo' and 'revision'")
    repo = source.get("repo")
    revision = source.get("revision")
    if not isinstance(repo, str) or not repo:
        raise _fail(path, "'source.repo' must be a non-empty string")
    if not isinstance(revision, str) or not _REVISION.match(revision):
        # A branch name would let the weights change under the same card.
        raise _fail(path, "'source.revision' must be a 40-character commit hash")
    return repo, revision


def _files(raw: dict[str, Any], path: Path) -> dict[str, str]:
    files = raw.get("files")
    if not isinstance(files, dict) or not files:
        raise _fail(path, "'files' must map file names to sha256 hashes")
    for name, digest in files.items():
        # Names become paths under the model directory when fetching.
        if (
            not isinstance(name, str)
            or "/" in name
            or "\\" in name
            or name in {"", ".", ".."}
        ):
            raise _fail(path, f"invalid file name {name!r} in 'files'")
        if not isinstance(digest, str) or not _SHA256.match(digest):
            raise _fail(path, f"'files.{name}' must be a lowercase hex sha256")
    return dict(files)


def _labels(raw: dict[str, Any], path: Path) -> dict[int, str]:
    labels = raw.get("labels")
    problem = (
        f"'labels' must map class indices 0 and 1 to exactly {sorted(REQUIRED_LABELS)}"
    )
    if not isinstance(labels, dict):
        raise _fail(path, problem)
    try:
        parsed = {int(index): str(name) for index, name in labels.items()}
    except ValueError:
        raise _fail(path, problem) from None
    if set(parsed) != {0, 1} or set(parsed.values()) != REQUIRED_LABELS:
        raise _fail(path, problem)
    return parsed


def _max_tokens(raw: dict[str, Any], path: Path) -> int:
    value = raw.get("max_tokens")
    # bool is a subclass of int; True must not pass as 1.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 2:
        raise _fail(path, "'max_tokens' must be an integer greater than 2")
    return value


def load_card(path: Path) -> ModelCard:
    """Read and validate a model card, or raise ModelLoadError."""
    if not path.is_file():
        raise ModelLoadError(f"model card not found at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModelLoadError(f"unreadable model card at {path}") from exc
    if not isinstance(raw, dict):
        raise _fail(path, "must be a JSON object")

    stub = raw.get("stub", False)
    if not isinstance(stub, bool):
        raise _fail(path, "'stub' must be true or false")
    repo, revision = _source(raw, path)
    return ModelCard(
        model_version=_version(raw, path),
        stub=stub,
        repo=repo,
        revision=revision,
        files=_files(raw, path),
        labels=_labels(raw, path),
        max_tokens=_max_tokens(raw, path),
    )


def verify_files(card: ModelCard, model_dir: Path) -> None:
    """Check every file the card lists exists in model_dir with its sha256."""
    for name, expected in card.files.items():
        target = model_dir / name
        if not target.is_file():
            raise ModelLoadError(
                f"{name} is missing from {model_dir}; run `python -m scripts.fetch_model`"
            )
        actual = file_sha256(target)
        if actual != expected:
            raise ModelLoadError(
                f"{name} in {model_dir} has sha256 {actual}, "
                f"but the card pins {expected}"
            )
