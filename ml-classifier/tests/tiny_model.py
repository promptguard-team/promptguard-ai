"""A tiny random XLM-R classifier, saved like the real one, for offline tests."""

import json
from pathlib import Path

import torch
from tokenizers import Tokenizer, models, pre_tokenizers
from transformers import (
    PreTrainedTokenizerFast,
    XLMRobertaConfig,
    XLMRobertaForSequenceClassification,
)

from app.card import file_sha256

SPECIALS = ["<s>", "<pad>", "</s>", "<unk>", "<mask>"]
WORDS = [
    "ignore",
    "all",
    "previous",
    "instructions",
    "reveal",
    "system",
    "prompt",
    "hello",
    "please",
    "summarise",
    "this",
    "report",
    "a",
    "b",
]
VERSION = "tiny-test-0.1.0"
MAX_TOKENS = 16  # 14 content tokens per window: long texts split quickly
FILES = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")


def build_tiny_model(directory: Path, *, num_labels: int = 2, seed: int = 0) -> None:
    """Write tokenizer and weights to directory (one word = one token)."""
    vocab = {token: index for index, token in enumerate(SPECIALS + WORDS)}
    tokenizer = Tokenizer(models.WordLevel(vocab=vocab, unk_token="<unk>"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tokenizer,
        bos_token="<s>",
        eos_token="</s>",
        cls_token="<s>",
        sep_token="</s>",
        pad_token="<pad>",
        unk_token="<unk>",
        mask_token="<mask>",
    )
    torch.manual_seed(seed)
    config = XLMRobertaConfig(
        vocab_size=len(vocab),
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        max_position_embeddings=MAX_TOKENS + 4,
        pad_token_id=1,
        bos_token_id=0,
        eos_token_id=2,
        num_labels=num_labels,
    )
    model = XLMRobertaForSequenceClassification(config)
    with torch.no_grad():
        # Default init yields near-identical outputs for every input; wider
        # weights make scores depend on the text, so max-over-windows is testable.
        for parameter in model.parameters():
            parameter.normal_(0.0, 0.5)
    directory.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(directory, safe_serialization=True)
    fast.save_pretrained(directory)


def write_card(directory: Path, card_path: Path, **overrides) -> Path:
    """Write a card whose hashes match the files in directory."""
    card = {
        "model_version": VERSION,
        "stub": True,
        "source": {"repo": "test/tiny", "revision": "0" * 40},
        "files": {name: file_sha256(directory / name) for name in FILES},
        "labels": {"0": "clean", "1": "injection"},
        "max_tokens": MAX_TOKENS,
    }
    card.update(overrides)
    card_path.write_text(json.dumps(card), encoding="utf-8")
    return card_path
