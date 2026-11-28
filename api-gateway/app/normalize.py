"""Canonical form of text for inspection by the rules and the classifier.

The gateway inspects this form but always forwards the user's original text.
Every step drops characters or replaces one character with one character, so
the result is never longer than the input: a crafted prompt cannot grow past
the classifier's length limit (a classifier error fails open). `origin` maps
each kept character back to its index in the original, which is how a rule
match found here is redacted in the original text.
"""

import unicodedata
from dataclasses import dataclass

# Fewer spaced-out characters than this are left alone: Polish has one-letter
# words ("a", "i", "w", "z"), and short runs carry no hidden secret.
COLLAPSE_MIN_RUN = 6
_GAPS = frozenset({" ", "\t", "\n", "\r\n"})
_WHITESPACE = frozenset(" \t\n\r")
_COMPACT_SEPARATORS = frozenset(" \t\n\r-._")
# Punctuation that may be glued to the first or last character of a run.
_GLUED = frozenset("()[]{}\"'.,;:!?")
_MAX_GLUED = 2
# Cyrillic letters that render like Latin ones. Applied only inside words that
# mix both scripts, so genuine Russian or Ukrainian text is left intact.
_HOMOGLYPHS = {
    "а": "a", "с": "c", "е": "e", "і": "i", "о": "o", "р": "p", "х": "x",
    "у": "y", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H",
    "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
}  # fmt: skip

Chars = list[tuple[str, int]]


@dataclass(frozen=True)
class Normalized:
    """Canonical text and, for each of its characters, the original index."""

    text: str
    origin: tuple[int, ...]


def _drop_format(chars: Chars) -> Chars:
    # Zero-width spaces and joiners, BOM, bidi controls, soft hyphen.
    return [(c, i) for c, i in chars if unicodedata.category(c) != "Cf"]


def _fold_compatibility(chars: Chars) -> Chars:
    out = []
    for c, i in chars:
        folded = unicodedata.normalize("NFKC", c)
        out.append((folded if len(folded) == 1 else c, i))
    return out


def _is_latin(c: str) -> bool:
    return c.isalpha() and (c.isascii() or "À" <= c <= "ɏ")


def _is_cyrillic(c: str) -> bool:
    return "Ѐ" <= c <= "ӿ"


def _unmix_words(chars: Chars) -> Chars:
    out = list(chars)
    start = 0
    while start < len(out):
        if not out[start][0].isalnum():
            start += 1
            continue
        end = start
        while end < len(out) and out[end][0].isalnum():
            end += 1
        word = [c for c, _ in out[start:end]]
        if any(map(_is_latin, word)) and any(map(_is_cyrillic, word)):
            for k in range(start, end):
                c, i = out[k]
                out[k] = (_HOMOGLYPHS.get(c, c), i)
        start = end
    return out


def _segments(chars: Chars) -> list[Chars]:
    """Split into alternating runs of whitespace and non-whitespace."""
    segments: list[Chars] = []
    for item in chars:
        space = item[0] in _WHITESPACE
        if segments and (segments[-1][0][0] in _WHITESPACE) == space:
            segments[-1].append(item)
        else:
            segments.append([item])
    return segments


def _is_gap(segment: Chars) -> bool:
    return "".join(c for c, _ in segment) in _GAPS


def _is_edge(segment: Chars, at_end: bool) -> bool:
    """One alphanumeric with punctuation glued on, like "(A" or "z." at a run edge.

    Without this, a spaced-out secret written in a sentence ("... 4 z.")
    would lose its first or last character to the run, and that character
    would survive redaction.
    """
    if not 1 < len(segment) <= 1 + _MAX_GLUED:
        return False
    core, glued = (segment[0], segment[1:]) if at_end else (segment[-1], segment[:-1])
    return core[0].isalnum() and all(c in _GLUED for c, _ in glued)


def _collapse_spaced(chars: Chars) -> Chars:
    """Join runs like "A K I A ..." into "AKIA...", dropping the single gaps."""
    segments = _segments(chars)
    out: Chars = []
    i = 0
    while i < len(segments):
        segment = segments[i]
        starts = segment[0][0] not in _WHITESPACE and (
            len(segment) == 1 or _is_edge(segment, at_end=False)
        )
        if starts:
            j, count = i, 1
            while j + 2 < len(segments) and _is_gap(segments[j + 1]):
                following = segments[j + 2]
                if len(following) == 1:
                    j, count = j + 2, count + 1
                    continue
                if _is_edge(following, at_end=True):
                    j, count = j + 2, count + 1
                break
            if count >= COLLAPSE_MIN_RUN:
                for k in range(i, j + 1, 2):
                    out.extend(segments[k])
                i = j + 1
                continue
        out.extend(segment)
        i += 1
    return out


def _build(chars: Chars) -> Normalized:
    return Normalized("".join(c for c, _ in chars), tuple(i for _, i in chars))


def normalize(text: str) -> Normalized:
    """Canonical form of text for inspection; never longer than text."""
    chars: Chars = [(c, i) for i, c in enumerate(text)]
    for step in (_drop_format, _fold_compatibility, _unmix_words, _collapse_spaced):
        chars = step(chars)
    return _build(chars)


def compact(view: Normalized) -> Normalized:
    """view without one- or two-character separators between alphanumerics.

    "AKIA-IOSF", "AKIAIOSF\\r\\nODNN" and "a.b" lose their separators; longer
    gaps (" - ", a blank line) are kept, so ordinary prose stays apart.
    """
    text = view.text
    keep: list[int] = []
    k = 0
    while k < len(text):
        if text[k] in _COMPACT_SEPARATORS:
            end = k
            while end < len(text) and text[end] in _COMPACT_SEPARATORS:
                end += 1
            bounded = 0 < k and end < len(text)
            if not (
                bounded
                and end - k <= 2
                and text[k - 1].isalnum()
                and text[end].isalnum()
            ):
                keep.extend(range(k, end))
            k = end
            continue
        keep.append(k)
        k += 1
    return Normalized(
        "".join(text[k] for k in keep), tuple(view.origin[k] for k in keep)
    )


def to_original_span(view: Normalized, start: int, end: int) -> tuple[int, int]:
    """The span of the original text that view.text[start:end] came from."""
    return view.origin[start], view.origin[end - 1] + 1
