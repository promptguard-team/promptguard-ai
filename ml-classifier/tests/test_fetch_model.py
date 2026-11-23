import hashlib
import json

import pytest

from app.card import ModelLoadError, load_card
from scripts import fetch_model
from scripts.fetch_model import fetch

CONTENT = {"config.json": b'{"a": 1}', "model.safetensors": b"weights"}
REV = "c" * 40


def _card(tmp_path, content=CONTENT):
    raw = {
        "model_version": "test-0.1.0",
        "source": {"repo": "org/model", "revision": REV},
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in content.items()
        },
        "labels": {"0": "clean", "1": "injection"},
        "max_tokens": 16,
    }
    path = tmp_path / "card.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class FakeHub:
    """Serves file contents like hf_hub_download into local_dir."""

    def __init__(self, served):
        self.served = served
        self.calls = []

    def __call__(self, repo, revision, filename, dest):
        self.calls.append((repo, revision, filename))
        target = dest / filename
        target.write_bytes(self.served[filename])
        return target


def test_downloads_missing_files_from_the_pinned_revision(tmp_path):
    hub = FakeHub(CONTENT)
    dest = tmp_path / "model"

    fetched = fetch(load_card(_card(tmp_path)), dest, hub)

    assert sorted(fetched) == sorted(CONTENT)
    assert sorted(hub.calls) == sorted(("org/model", REV, name) for name in CONTENT)
    assert (dest / "model.safetensors").read_bytes() == b"weights"


def test_files_that_already_match_are_not_downloaded_again(tmp_path):
    dest = tmp_path / "model"
    dest.mkdir()
    for name, data in CONTENT.items():
        (dest / name).write_bytes(data)
    hub = FakeHub(CONTENT)

    assert fetch(load_card(_card(tmp_path)), dest, hub) == []
    assert hub.calls == []


def test_a_corrupted_local_file_is_downloaded_again(tmp_path):
    dest = tmp_path / "model"
    dest.mkdir()
    (dest / "config.json").write_bytes(CONTENT["config.json"])
    (dest / "model.safetensors").write_bytes(b"truncated")
    hub = FakeHub(CONTENT)

    assert fetch(load_card(_card(tmp_path)), dest, hub) == ["model.safetensors"]


def test_a_download_that_does_not_match_the_card_fails_and_is_removed(tmp_path):
    hub = FakeHub({**CONTENT, "model.safetensors": b"tampered"})
    dest = tmp_path / "model"

    with pytest.raises(ModelLoadError, match="model.safetensors"):
        fetch(load_card(_card(tmp_path)), dest, hub)
    assert not (dest / "model.safetensors").exists()


def test_main_reports_a_bad_card_with_exit_code_1(tmp_path, capsys):
    assert (
        fetch_model.main(
            ["--card", str(tmp_path / "nope.json"), "--dest", str(tmp_path)]
        )
        == 1
    )
    assert "not found" in capsys.readouterr().err


def test_main_fetches_with_the_injected_downloader(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch_model, "hf_download", FakeHub(CONTENT))
    dest = tmp_path / "model"

    code = fetch_model.main(["--card", str(_card(tmp_path)), "--dest", str(dest)])

    assert code == 0
    assert "test-0.1.0" in capsys.readouterr().out
    assert (dest / "config.json").is_file()
