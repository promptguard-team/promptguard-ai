import hashlib
import json
from pathlib import Path

import pytest

from app.card import ModelLoadError, file_sha256, load_card, verify_files

COMMITTED_CARD = (
    Path(__file__).resolve().parents[1] / "models" / "xlm-roberta-pi.card.json"
)
SHA = "a" * 64
REV = "b" * 40


def _card(**overrides):
    card = {
        "model_version": "test-0.1.0",
        "stub": True,
        "source": {"repo": "org/model", "revision": REV},
        "files": {"config.json": SHA},
        "labels": {"0": "clean", "1": "injection"},
        "max_tokens": 16,
    }
    card.update(overrides)
    return card


def _write(tmp_path, card):
    path = tmp_path / "card.json"
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


def test_valid_card_is_parsed(tmp_path):
    card = load_card(_write(tmp_path, _card()))

    assert card.model_version == "test-0.1.0"
    assert card.stub is True
    assert card.repo == "org/model"
    assert card.revision == REV
    assert card.files == {"config.json": SHA}
    assert card.labels == {0: "clean", 1: "injection"}
    assert card.max_tokens == 16


def test_stub_defaults_to_false(tmp_path):
    card = _card()
    del card["stub"]
    assert load_card(_write(tmp_path, card)).stub is False


def test_committed_card_is_valid():
    card = load_card(COMMITTED_CARD)

    assert card.model_version == "xlmr-pi-e8a758a"
    assert card.stub is False
    assert card.labels == {0: "clean", 1: "injection"}
    assert set(card.files) == {
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
    }


def test_missing_card_is_rejected(tmp_path):
    with pytest.raises(ModelLoadError, match="not found"):
        load_card(tmp_path / "nope.json")


def test_unreadable_card_is_rejected(tmp_path):
    path = tmp_path / "card.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelLoadError, match="unreadable"):
        load_card(path)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"model_version": ""}, "model_version"),
        ({"model_version": "x" * 65}, "64"),
        ({"stub": "yes"}, "stub"),
        ({"source": {"repo": "org/model"}}, "revision"),
        ({"source": {"repo": "", "revision": REV}}, "repo"),
        ({"source": {"repo": "org/model", "revision": "main"}}, "revision"),
        ({"files": {}}, "files"),
        ({"files": {"config.json": "abc"}}, "sha256"),
        ({"files": {"../evil.json": SHA}}, "file name"),
        ({"files": {"sub/config.json": SHA}}, "file name"),
        ({"labels": {"0": "clean", "1": "attack"}}, "labels"),
        ({"labels": {"0": "clean"}}, "labels"),
        ({"labels": {"zero": "clean", "1": "injection"}}, "labels"),
        ({"max_tokens": 2}, "max_tokens"),
        ({"max_tokens": True}, "max_tokens"),
        ({"max_tokens": "256"}, "max_tokens"),
    ],
)
def test_invalid_cards_are_rejected_with_the_field_named(tmp_path, overrides, message):
    with pytest.raises(ModelLoadError, match=message):
        load_card(_write(tmp_path, _card(**overrides)))


def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"x" * 3_000_000)
    assert file_sha256(path) == hashlib.sha256(b"x" * 3_000_000).hexdigest()


def test_verify_files_accepts_matching_files(tmp_path):
    (tmp_path / "config.json").write_bytes(b"{}")
    card = load_card(
        _write(
            tmp_path, _card(files={"config.json": hashlib.sha256(b"{}").hexdigest()})
        )
    )
    verify_files(card, tmp_path)


def test_verify_files_names_a_missing_file(tmp_path):
    card = load_card(_write(tmp_path, _card()))
    with pytest.raises(ModelLoadError, match="config.json.*missing"):
        verify_files(card, tmp_path)


def test_verify_files_names_a_mismatching_file(tmp_path):
    (tmp_path / "config.json").write_bytes(b"{}")
    card = load_card(_write(tmp_path, _card()))
    with pytest.raises(ModelLoadError, match="config.json.*sha256"):
        verify_files(card, tmp_path)
