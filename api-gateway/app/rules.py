import re
from collections.abc import Callable
from dataclasses import dataclass

from app.normalize import compact, normalize, to_original_span

# No word-boundary anchors on either edge of the credential prefixes: an
# attacker can defeat a `\b`- or alnum-lookbehind-based anchor simply by
# gluing one more character onto either end of the key, and evading
# detection is this product's threat model. `scan_text` only uses
# `search()` for truthiness, so an anchor buys nothing about match extent
# while costing that evasion (a key immediately followed by one more
# letter or digit was previously missed by a trailing `\b` alone).
_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
    "private_key_block": re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE
    ),
}
_PRIVATE_KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)
# Case-sensitive on purpose: used only on the compact view (see _RULES).
_AWS_COMPACT = re.compile(r"AKIA[0-9A-Z]{16}")

# Linear by construction: one bounded-below quantifier over a single character
# class, with no overlapping alternative to backtrack into. The lookbehind
# stops `sk-` from matching the tail of an ordinary word ("task-", "risk-",
# "disk-", "ask-") while still allowing a key glued to punctuation or a digit
# ("key:sk-...", '"sk-...').
_OPENAI_CANDIDATE = re.compile(r"(?<![A-Za-z])sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE)
# A real key's body carries a long unbroken alphanumeric run; a hyphenated slug
# that happens to begin with "sk-" does not.
_OPENAI_KEY_BODY = re.compile(r"[A-Za-z0-9]{20,}")


def _matches_openai_key(text: str) -> bool:
    return any(
        _OPENAI_KEY_BODY.search(m.group()) for m in _OPENAI_CANDIDATE.finditer(text)
    )


# Tolerates a single '-' or ' ' separator (e.g. "440514-01359"). The class is
# deliberately just "- " (not \s) to match what the stripping below removes;
# a tab- or newline-joined candidate is meant to fail the length check, not
# to be silently accepted by a wider match and then discarded anyway.
#
# Digit boundaries, not word boundaries: a `\b`-anchored PESEL is defeated by
# appending a single letter or digit to either end (verified: "44051401359x",
# "x44051401359" and "044051401359" all previously passed undetected), so the
# anchors here require a non-digit (or string edge) instead. This deliberately
# does NOT slide an 11-digit window through a longer digit run — that would
# also catch "044051401359", but every 11-digit window carries roughly a 1.9%
# chance of passing the checksum, so a long numeric id (an order number, a
# timestamp) would false-positive at a meaningful rate, and a hard 403 on
# legitimate work is the failure mode this product cannot afford. A
# digit-padded PESEL is therefore knowingly out of reach of this layer; it is
# left to the future ML classifier, which can weigh context instead of firing
# on the first checksum match in a wider window.
_PESEL_CANDIDATE = re.compile(r"(?<!\d)\d{11}(?!\d)|(?<!\d)\d{1,10}[- ]\d{1,10}(?!\d)")
_PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)


@dataclass(frozen=True)
class RuleMatch:
    """A sensitive-data rule that matched the scanned text."""

    rule: str


def _is_valid_pesel(digits: str) -> bool:
    """Check the checksum and the YYMMDD date sanity of an 11-digit PESEL.

    The month field encodes the century by adding 0/20/40/60/80, hence the
    `% 20`. The checksum alone admits about 1 in 10 arbitrary 11-digit
    strings; requiring a plausible month and day rejects most of the
    phone numbers, order ids, and timestamps that would otherwise pass it
    by chance.
    """
    month = int(digits[2:4]) % 20
    day = int(digits[4:6])
    if not (1 <= month <= 12) or not (1 <= day <= 31):
        return False
    checksum = sum(int(d) * w for d, w in zip(digits[:10], _PESEL_WEIGHTS))
    return (10 - checksum % 10) % 10 == int(digits[10])


@dataclass(frozen=True)
class SecretMatch:
    """A rule match located in the original (un-normalized) text."""

    rule: str
    start: int
    end: int


def _aws_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _PATTERNS["aws_access_key"].finditer(text)]


def _openai_spans(text: str) -> list[tuple[int, int]]:
    return [
        m.span()
        for m in _OPENAI_CANDIDATE.finditer(text)
        if _OPENAI_KEY_BODY.search(m.group())
    ]


def _aws_compact_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _AWS_COMPACT.finditer(text)]


def _private_key_spans(text: str) -> list[tuple[int, int]]:
    # The span runs to the END line, or to the end of the text when it is
    # missing, so redaction removes the key body and not just its header.
    spans = []
    position = 0
    while header := _PATTERNS["private_key_block"].search(text, position):
        footer = _PRIVATE_KEY_END.search(text, header.end())
        stop = footer.end() if footer else len(text)
        spans.append((header.start(), stop))
        position = stop
    return spans


def _pesel_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    for m in _PESEL_CANDIDATE.finditer(text):
        digits = m.group().replace("-", "").replace(" ", "")
        if len(digits) == 11 and _is_valid_pesel(digits):
            spans.append(m.span())
    return spans


Spans = Callable[[str], list[tuple[int, int]]]

# Priority order: the first rule here names a request's audit row. Only the
# AWS rule also scans the compact view (short separators between
# alphanumerics removed), and there case-sensitively: joining words could
# otherwise spell "akia" plus 16 letters out of prose ("Kakiage tempura is
# tasty"). PESEL must not use it, or phone numbers and ids written in digit
# groups would become checksum candidates; OpenAI keys contain hyphens.
_RULES: tuple[tuple[str, Spans, Spans | None], ...] = (
    ("aws_access_key", _aws_spans, _aws_compact_spans),
    ("openai_api_key", _openai_spans, None),
    ("private_key_block", _private_key_spans, None),
    ("pesel", _pesel_spans, None),
)
_PRIORITY = {name: index for index, (name, _, _) in enumerate(_RULES)}


def find_secrets(text: str) -> list[SecretMatch]:
    """Every rule match, inspected on the normalized text, spanned in text.

    Overlapping or touching spans are merged; the merged span keeps the name
    of its highest-priority rule. Sorted by position.
    """
    view = normalize(text)
    squeezed = compact(view)
    found: list[tuple[int, int, int, str]] = []
    for name, spans, compact_spans in _RULES:
        passes = [(view, spans)]
        if compact_spans is not None:
            passes.append((squeezed, compact_spans))
        for candidate, finder in passes:
            for start, end in finder(candidate.text):
                first, last = to_original_span(candidate, start, end)
                found.append((first, last, _PRIORITY[name], name))
    found.sort()
    merged: list[list] = []
    for start, end, priority, name in found:
        if merged and start <= merged[-1][1]:
            last = merged[-1]
            last[1] = max(last[1], end)
            if priority < last[2]:
                last[2], last[3] = priority, name
        else:
            merged.append([start, end, priority, name])
    return [SecretMatch(name, start, end) for start, end, _, name in merged]


def first_rule(matches: list[SecretMatch]) -> str:
    """The highest-priority rule among matches (names the audit row)."""
    return min(matches, key=lambda match: _PRIORITY[match.rule]).rule


def redact(text: str, matches: list[SecretMatch]) -> str:
    """text with every match replaced by [REDACTED:<rule>]."""
    for match in sorted(matches, key=lambda m: m.start, reverse=True):
        text = f"{text[: match.start]}[REDACTED:{match.rule}]{text[match.end :]}"
    return text


def scan_text(text: str) -> RuleMatch | None:
    """Return the highest-priority sensitive-data rule matching the text."""
    matches = find_secrets(text)
    return RuleMatch(rule=first_rule(matches)) if matches else None
