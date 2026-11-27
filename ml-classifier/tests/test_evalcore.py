"""Evaluation core: CSV loading, metrics, threshold choice. Never loads a model."""

import pytest

from scripts.evalcore import (
    Row,
    Scored,
    block_threshold,
    grid_table,
    load_rows,
    metrics_at,
    review_threshold,
)


def _write(tmp_path, content: bytes):
    path = tmp_path / "eval.csv"
    path.write_bytes(content)
    return path


def test_valid_csv_is_loaded_and_labels_normalised(tmp_path):
    path = _write(tmp_path, b"text,label\n  attack \t,Injection \nhello,clean\n")
    assert load_rows(path) == [Row("  attack \t", "injection"), Row("hello", "clean")]


def test_optional_category_and_lang_columns_are_read(tmp_path):
    path = _write(
        tmp_path, b"text,label,category,lang\nhej,clean,chitchat,pl\nx,injection,,\n"
    )
    assert load_rows(path) == [
        Row("hej", "clean", "chitchat", "pl"),
        Row("x", "injection", "", ""),
    ]


def test_utf8_bom_header_is_accepted(tmp_path):
    path = _write(tmp_path, b"\xef\xbb\xbftext,label\nattack,injection\n")
    assert load_rows(path) == [Row("attack", "injection")]


def test_unknown_label_names_row_and_value(tmp_path):
    path = _write(tmp_path, b"text,label\na,injection\nb,Malicious\n")
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "row 3" in str(exc.value)
    assert "'Malicious'" in str(exc.value)


def test_missing_column_is_named(tmp_path):
    path = _write(tmp_path, b"body,tag\nx,injection\n")
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "missing column" in str(exc.value)
    assert "'label'" in str(exc.value)
    assert "'text'" in str(exc.value)


@pytest.mark.parametrize("line", [",injection", "   ,injection"])
def test_empty_or_missing_text_names_row(tmp_path, line):
    path = _write(tmp_path, f"text,label\na,injection\n{line}\n".encode())
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "row 3" in str(exc.value)


def test_short_row_missing_text_field_is_rejected_not_crashed(tmp_path):
    path = _write(tmp_path, b"label,text\ninjection\n")
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "row 2" in str(exc.value)
    assert "text is missing or empty" in str(exc.value)


def test_set_without_injection_rows_is_rejected(tmp_path):
    path = _write(tmp_path, b"text,label\nhello,clean\n")
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "no rows labelled 'injection'" in str(exc.value)


def test_expected_label_accepts_a_single_class_file(tmp_path):
    path = _write(tmp_path, b"text,label\nhello,clean\n")
    assert load_rows(path, label="clean") == [Row("hello", "clean")]


def test_expected_label_rejects_a_row_of_the_other_class(tmp_path):
    path = _write(tmp_path, b"text,label\nhello,clean\nhack,injection\n")
    with pytest.raises(SystemExit) as exc:
        load_rows(path, label="clean")
    assert "row 3" in str(exc.value)
    assert "expected 'clean'" in str(exc.value)


def test_missing_file_is_named(tmp_path):
    with pytest.raises(SystemExit) as exc:
        load_rows(tmp_path / "nope.csv")
    assert "nope.csv" in str(exc.value)


def test_non_utf8_file_gets_actionable_message(tmp_path):
    content = "text,label\nzażółć gęślą jaźń,injection\n".encode("cp1250")
    path = _write(tmp_path, content)
    with pytest.raises(SystemExit) as exc:
        load_rows(path)
    assert "UTF-8" in str(exc.value)
    assert str(path) in str(exc.value)


def _scored(clean, attacks):
    return [Scored(Row(f"c{i}", "clean"), s) for i, s in enumerate(clean)] + [
        Scored(Row(f"a{i}", "injection"), s) for i, s in enumerate(attacks)
    ]


SAMPLE = _scored(clean=[0.1, 0.5, 0.95], attacks=[0.6, 0.99])
GRID = (0.5, 0.9, 0.96, 0.99)


def test_metrics_at_a_threshold_are_inclusive():
    m = metrics_at(SAMPLE, 0.5)
    assert (m.tp, m.fp, m.fn, m.tn) == (2, 2, 0, 1)
    assert m.precision == pytest.approx(0.5)
    assert m.recall == pytest.approx(1.0)
    assert m.fpr == pytest.approx(2 / 3)


def test_metrics_without_positives_report_none_not_zero():
    m = metrics_at(_scored(clean=[0.2], attacks=[]), 0.5)
    assert m.recall is None
    assert m.precision is None


def test_block_threshold_is_the_lowest_grid_value_within_the_fpr_target():
    assert block_threshold(SAMPLE, max_fpr=0.0, grid=GRID) == 0.96


def test_block_threshold_is_none_when_no_grid_value_qualifies():
    scored = _scored(clean=[1.0], attacks=[1.0])
    assert block_threshold(scored, max_fpr=0.0, grid=GRID) is None


def test_block_threshold_needs_clean_rows():
    with pytest.raises(ValueError, match="clean"):
        block_threshold(_scored(clean=[], attacks=[0.9]), max_fpr=0.01, grid=GRID)


def test_review_threshold_is_the_lowest_value_below_block_within_its_target():
    assert review_threshold(SAMPLE, block=0.96, max_fpr=0.34, grid=GRID) == 0.9


def test_review_threshold_is_none_when_nothing_below_block_qualifies():
    assert review_threshold(SAMPLE, block=0.96, max_fpr=0.0, grid=GRID) is None


def test_grid_table_is_markdown_with_counts():
    table = grid_table(SAMPLE, grid=(0.5,))
    lines = table.splitlines()
    assert lines[0] == "| threshold | precision | recall | FPR | FP | FN |"
    assert lines[2] == "| 0.500 | 0.500 | 1.000 | 0.667 | 2/3 | 0/2 |"


def test_grid_table_keeps_fine_thresholds_distinct():
    table = grid_table(SAMPLE, grid=(0.99, 0.995, 0.998))
    rows = [line.split(" | ")[0] for line in table.splitlines()[2:]]
    assert rows == ["| 0.990", "| 0.995", "| 0.998"]
