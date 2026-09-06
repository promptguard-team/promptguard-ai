import re
from dataclasses import dataclass

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


def scan_text(text: str) -> RuleMatch | None:
    """Return the first sensitive-data rule matching the text, if any."""
    if _PATTERNS["aws_access_key"].search(text):
        return RuleMatch(rule="aws_access_key")
    if _matches_openai_key(text):
        return RuleMatch(rule="openai_api_key")
    if _PATTERNS["private_key_block"].search(text):
        return RuleMatch(rule="private_key_block")
    for candidate in _PESEL_CANDIDATE.findall(text):
        digits = candidate.replace("-", "").replace(" ", "")
        if len(digits) == 11 and _is_valid_pesel(digits):
            return RuleMatch(rule="pesel")
    return None
