"""The only component that knows a transformer is underneath."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers.utils import logging as hf_logging

from app.card import ModelCard, ModelLoadError, load_card, verify_files
from app.windows import split_windows

__all__ = ["ModelBundle", "ModelLoadError", "Prediction"]

# Tokens shared by consecutive windows, so an instruction cut at a window edge
# is still read whole by its neighbour. Capped at a quarter of a window so tiny
# test models still make progress.
WINDOW_OVERLAP = 64


@dataclass(frozen=True)
class Prediction:
    """One scored text."""

    label: str
    score: float
    windows: int


class ModelBundle:
    """A loaded classifier plus the card that describes it."""

    def __init__(self, card: ModelCard, tokenizer: Any, model: Any, max_windows: int):
        special = (
            tokenizer.cls_token_id,
            tokenizer.sep_token_id,
            tokenizer.pad_token_id,
        )
        if any(token is None for token in special):
            raise ModelLoadError("tokenizer must define cls, sep and pad tokens")
        self._card = card
        self._tokenizer = tokenizer
        self._model = model
        self._max_windows = max_windows
        self._cls, self._sep, self._pad = special
        self._content = card.max_tokens - 2  # room for <s> and </s>
        self._overlap = min(WINDOW_OVERLAP, self._content // 4)
        self._injection_idx = next(
            i for i, name in card.labels.items() if name == "injection"
        )

    @property
    def version(self) -> str:
        return self._card.model_version

    @property
    def is_stub(self) -> bool:
        return self._card.stub

    def _batch(self, windows: list[list[int]]) -> tuple[torch.Tensor, torch.Tensor]:
        sequences = [[self._cls, *window, self._sep] for window in windows]
        width = max(len(sequence) for sequence in sequences)
        input_ids = torch.full((len(sequences), width), self._pad, dtype=torch.long)
        attention = torch.zeros((len(sequences), width), dtype=torch.long)
        for row, sequence in enumerate(sequences):
            input_ids[row, : len(sequence)] = torch.tensor(sequence, dtype=torch.long)
            attention[row, : len(sequence)] = 1
        return input_ids, attention

    def _windows(self, text: str) -> list[list[int]]:
        # verbose=False: long prompts exceed model_max_length by design here.
        ids = self._tokenizer.encode(text, add_special_tokens=False, verbose=False)
        return split_windows(ids, self._content, self._overlap, self._max_windows)

    def windows_for(self, text: str) -> int:
        """How many windows predict() would score for text (no inference)."""
        return len(self._windows(text))

    def predict(self, text: str) -> Prediction:
        """Return P(injection) as the max over the text's windows."""
        windows = self._windows(text)
        input_ids, attention = self._batch(windows)
        with torch.inference_mode():
            logits = self._model(input_ids=input_ids, attention_mask=attention).logits
        probabilities = torch.softmax(logits, dim=-1)
        injection = probabilities[:, self._injection_idx]
        best = int(torch.argmax(injection))
        label = self._card.labels[int(torch.argmax(probabilities[best]))]
        return Prediction(
            label=label, score=float(injection[best]), windows=len(windows)
        )

    @classmethod
    def load(cls, card_path: Path, model_dir: Path, max_windows: int) -> "ModelBundle":
        """Load and validate a card and its weights offline, or raise ModelLoadError."""
        card = load_card(card_path)
        verify_files(card, model_dir)
        hf_logging.disable_progress_bar()
        try:
            # Local files only: the service never reaches the network, and the
            # files were just verified against the card's sha256. Bandit's B615
            # (unpinned Hub download) does not apply: nothing is downloaded here,
            # and the card pins the revision the files were fetched from.
            tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
                model_dir, local_files_only=True
            )
            model = AutoModelForSequenceClassification.from_pretrained(  # nosec B615
                model_dir, local_files_only=True, use_safetensors=True
            )
        except Exception as exc:  # noqa: BLE001 - any failure here is fatal
            raise ModelLoadError(f"could not load the model from {model_dir}") from exc

        if model.config.num_labels != len(card.labels):
            raise ModelLoadError(
                f"model has {model.config.num_labels} classes; "
                f"the card declares {len(card.labels)}"
            )
        positions = model.config.max_position_embeddings - 2
        if card.max_tokens > positions:
            raise ModelLoadError(
                f"card max_tokens {card.max_tokens} exceeds the model's {positions} positions"
            )
        model.eval()
        return cls(card, tokenizer, model, max_windows)
