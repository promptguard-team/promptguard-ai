"""Shape of the hand-written PoC set. Scores are not tested here."""

from collections import Counter
from pathlib import Path

from scripts.evalcore import load_rows
from scripts.leakage import find_overlap, normalise

CLEAN = Path("data/poc/clean.csv")
ATTACKS = Path("data/poc/attacks.csv")
CLEAN_CATEGORIES = {"business", "borderline", "code", "chitchat"}
ATTACK_CATEGORIES = {
    "jailbreak",
    "roleplay",
    "system_prompt_leak",
    "instruction_override",
}


def _check(rows, categories, minimum):
    assert len(rows) >= minimum
    counts = Counter(row.category for row in rows)
    assert set(counts) == categories
    assert min(counts.values()) >= 15
    langs = Counter(row.lang for row in rows)
    assert set(langs) == {"pl", "en"}
    assert min(langs.values()) >= 0.4 * len(rows)


def test_clean_set_shape():
    _check(load_rows(CLEAN, label="clean"), CLEAN_CATEGORIES, 150)


def test_attack_set_shape():
    _check(load_rows(ATTACKS, label="injection"), ATTACK_CATEGORIES, 100)


def test_every_category_has_both_languages():
    for path, label in ((CLEAN, "clean"), (ATTACKS, "injection")):
        pairs = {(row.category, row.lang) for row in load_rows(path, label=label)}
        categories = {category for category, _ in pairs}
        assert pairs == {(c, lang) for c in categories for lang in ("pl", "en")}


def test_no_duplicates_across_both_files():
    rows = load_rows(CLEAN, label="clean") + load_rows(ATTACKS, label="injection")
    texts = [normalise(row.text) for row in rows]
    assert len(texts) == len(set(texts))


def test_no_row_repeats_the_notebook_training_samples():
    rows = load_rows(CLEAN, label="clean") + load_rows(ATTACKS, label="injection")
    assert find_overlap(rows, []) == []
