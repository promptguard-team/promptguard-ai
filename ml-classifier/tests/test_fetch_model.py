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


def test_a_rejected_local_file_is_removed_before_downloading(tmp_path):
    dest = tmp_path / "model"
    dest.mkdir()
    (dest / "config.json").write_bytes(CONTENT["config.json"])
    (dest / "model.safetensors").write_bytes(b"stale")
    seen = []

    def download(repo, revision, filename, target_dir):
        seen.append((filename, (target_dir / filename).exists()))
        (target_dir / filename).write_bytes(CONTENT[filename])
        return target_dir / filename

    assert fetch(load_card(_card(tmp_path)), dest, download) == ["model.safetensors"]
    assert seen == [("model.safetensors", False)]


def test_a_downloader_that_writes_nothing_fails_naming_the_file(tmp_path):
    def download(repo, revision, filename, target_dir):
        return target_dir / filename

    with pytest.raises(ModelLoadError, match="config.json"):
        fetch(load_card(_card(tmp_path)), tmp_path / "model", download)


def test_main_reports_a_download_failure_with_exit_code_1(
    tmp_path, monkeypatch, capsys
):
    def download(repo, revision, filename, target_dir):
        raise ModelLoadError(f"could not download {filename}")

    monkeypatch.setattr(fetch_model, "hf_download", download)

    code = fetch_model.main(
        ["--card", str(_card(tmp_path)), "--dest", str(tmp_path / "m")]
    )

    assert code == 1
    err = capsys.readouterr().err
    assert "could not download" in err
    assert len(err.strip().splitlines()) == 1


def test_hf_download_wraps_hub_errors(tmp_path, monkeypatch):
    import huggingface_hub

    def boom(**kwargs):
        raise OSError("offline")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", boom)

    with pytest.raises(
        ModelLoadError, match=r"could not download config.json from org/m@abc"
    ):
        fetch_model.hf_download("org/m", "abc", "config.json", tmp_path)
