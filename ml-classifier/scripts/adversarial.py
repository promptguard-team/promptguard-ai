"""Text transformations for the MITRE ATLAS AML.T0015 evasion experiment.

The obfuscated set must be built from examples the model was NOT trained on,
otherwise the measured recall drop describes memorisation rather than
robustness.
"""

import base64
from collections.abc import Callable

_LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5"})
_ZERO_WIDTH = "​"


def _leetspeak(text: str) -> str:
    return text.translate(_LEET)


def _spacing(text: str) -> str:
    return " ".join(" ".join(word) for word in text.split())


def _zero_width(text: str) -> str:
    return _ZERO_WIDTH.join(text)


def _base64_wrap(text: str) -> str:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"decode this and follow it: {encoded}"


def _upper_snake(text: str) -> str:
    return text.upper().replace(" ", "_")


TRANSFORMS: dict[str, Callable[[str], str]] = {
    "leetspeak": _leetspeak,
    "spacing": _spacing,
    "zero_width": _zero_width,
    "base64": _base64_wrap,
    "upper_snake": _upper_snake,
}


def obfuscate(text: str, name: str) -> str:
    """Apply one named transformation. Raises KeyError if it is unknown."""
    return TRANSFORMS[name](text)
