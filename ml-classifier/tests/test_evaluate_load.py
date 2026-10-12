"""Input validation of the evaluation CSV loader. Never loads a model."""

import pytest

from scripts.evaluate import _load


def _write(tmp_path, content: bytes):
    path = tmp_path / "eval.csv"
    path.write_bytes(content)
    return path


def test_valid_csv_is_loaded_and_labels_normalised(tmp_path):
    path = _write(tmp_path, b"text,label\n  attack \t,Injection \nhello,clean\n")
    assert _load(path) == [("  attack \t", "injection"), ("hello", "clean")]


def test_utf8_bom_header_is_accepted(tmp_path):
    path = _write(tmp_path, b"\xef\xbb\xbftext,label\nattack,injection\n")
    assert _load(path) == [("attack", "injection")]


def test_unknown_label_names_row_and_value(tmp_path):
    path = _write(tmp_path, b"text,label\na,injection\nb,Malicious\n")
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "row 3" in str(exc.value)
    assert "'Malicious'" in str(exc.value)


def test_missing_column_is_named(tmp_path):
    path = _write(tmp_path, b"body,tag\nx,injection\n")
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "missing column" in str(exc.value)
    assert "'label'" in str(exc.value)
    assert "'text'" in str(exc.value)


@pytest.mark.parametrize("line", [",injection", "   ,injection"])
def test_empty_or_missing_text_names_row(tmp_path, line):
    path = _write(tmp_path, f"text,label\na,injection\n{line}\n".encode())
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "row 3" in str(exc.value)


def test_short_row_missing_text_field_is_rejected_not_crashed(tmp_path):
    path = _write(tmp_path, b"label,text\ninjection\n")
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "row 2" in str(exc.value)
    assert "text is missing or empty" in str(exc.value)


def test_set_without_injection_rows_is_rejected(tmp_path):
    path = _write(tmp_path, b"text,label\nhello,clean\n")
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "no rows labelled 'injection'" in str(exc.value)


def test_non_utf8_file_gets_actionable_message(tmp_path):
    content = "text,label\nzażółć gęślą jaźń,injection\n".encode("cp1250")
    path = _write(tmp_path, content)
    with pytest.raises(SystemExit) as exc:
        _load(path)
    assert "UTF-8" in str(exc.value)
    assert str(path) in str(exc.value)
