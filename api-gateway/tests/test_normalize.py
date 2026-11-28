import time

import pytest

from app.normalize import COLLAPSE_MIN_RUN, compact, normalize, to_original_span

TRICKY = [
    "\ufdfa" * 50,  # one character whose NFKC form is 18 characters
    "\ufb01 \ufb02 \ufb03",  # ligatures expand to several characters
    "\uff28\uff45\uff4c\uff4c\uff4f",  # full-width Hello
    "e\u0301",  # combining accent
    "\U0001f44d\U0001f3fd ok",
    "a\u200bb\u200dc\ufeff",
    "Привет мир",
    "H\u0435llo",
    " ".join("AKIAIOSFODNN7EXAMPLE"),
    "x\r\ny",
    "",
]


@pytest.mark.parametrize("text", TRICKY)
def test_output_is_never_longer_and_maps_back_in_order(text):
    view = normalize(text)
    assert len(view.text) <= len(text)
    assert len(view.origin) == len(view.text)
    assert list(view.origin) == sorted(set(view.origin))
    assert all(0 <= index < len(text) for index in view.origin)


def test_format_characters_are_dropped():
    assert normalize("ig\u200bno\u200dre\ufeff\u00ad").text == "ignore"


def test_single_character_compatibility_forms_are_folded():
    assert normalize("\uff28\uff45\uff4c\uff4c\uff4f").text == "Hello"


def test_multi_character_expansions_are_left_alone():
    assert normalize("\ufdfa \ufb01").text == "\ufdfa \ufb01"


def test_cyrillic_look_alikes_in_mixed_words_become_latin():
    assert normalize("H\u0435llo w\u043erld").text == "Hello world"


def test_pure_cyrillic_text_is_unchanged():
    assert normalize("Привет мир, как дела?").text == "Привет мир, как дела?"


def test_runs_of_spaced_characters_are_joined():
    assert normalize("i g n o r e previous").text == "ignore previous"


def test_runs_shorter_than_the_minimum_are_kept():
    short = " ".join("abcdefgh"[: COLLAPSE_MIN_RUN - 1])
    assert normalize(short).text == short


def test_line_breaks_and_tabs_count_as_single_gaps():
    assert normalize("a\nb\r\nc\td e f").text == "abcdef"


def test_double_spaces_break_a_run():
    assert normalize("a b c  d e f").text == "a b c  d e f"


def test_punctuation_glued_to_the_run_edges_stays_in_the_run():
    assert normalize("(A K I A I O) ok").text == "(AKIAIO) ok"


def test_origin_and_spans_point_at_the_original_text():
    text = "go: a b c d e f!"
    view = normalize(text)
    assert view.text == "go: abcdef!"
    start = view.text.index("abcdef")
    assert to_original_span(view, start, start + 6) == (4, 15)


def test_compact_drops_short_separators_between_alphanumerics():
    view = compact(normalize("AKIA-IOSF\r\nODNN.7EXA_MPLE"))
    assert view.text == "AKIAIOSFODNN7EXAMPLE"


def test_compact_keeps_long_gaps_and_separators_next_to_punctuation():
    text = "one - two\n\n\nthree, four"
    assert compact(normalize(text)).text == "one - two\n\n\nthree, four"


def test_compact_maps_back_to_the_original():
    text = "id AKIA-IOSF"
    view = compact(normalize(text))
    start = view.text.index("AKIA")
    assert to_original_span(view, start, start + 8) == (3, 12)


def test_normalize_is_linear_on_adversarial_input():
    started = time.perf_counter()
    normalize("(a " * 11000)
    normalize("\u200b" * 32000)
    assert time.perf_counter() - started < 1.0
