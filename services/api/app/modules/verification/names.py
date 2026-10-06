"""Indian business-name normaliser and deterministic matcher (plan section 1.3).

No model is involved. Thresholds are named constants; the provider's own name-match
score is a separate, second input handled elsewhere.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

# Score is the difflib ratio of the sorted, normalised token strings (0.0 to 1.0).
HIGH_THRESHOLD = 0.92
MEDIUM_THRESHOLD = 0.75

# Names longer than this are never matched (LOW, 0.0) and are truncated by
# normalise_name. The cap applies BEFORE NFKC, which can expand text, so work is bounded.
MAX_NAME_LEN = 200


class MatchLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class NameMatch:
    level: MatchLevel
    score: float


_LEADING = frozenset({"ms", "messrs", "shri", "sri", "smt", "mr", "mrs", "dr"})
_TRAILING = frozenset({"pvt", "private", "ltd", "limited", "llp", "p"})
_DROPPED = frozenset({"and"})

_MS_PREFIX = re.compile(r"^\s*m\s*/\s*s\b\.?")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalise_name(name: str) -> str:
    """Lower-case, strip M/s, honorifics, legal-form suffixes, punctuation and '&'/'and'.

    Input beyond MAX_NAME_LEN characters is truncated before normalisation (match_names
    rejects such input outright instead of matching a truncated name).
    """
    s = unicodedata.normalize("NFKC", name[:MAX_NAME_LEN]).casefold()
    s = _MS_PREFIX.sub(" ", s)
    s = s.replace("&", " and ").replace(".", "")
    tokens = [t for t in _NON_ALNUM.sub(" ", s).split() if t not in _DROPPED]
    start = 0  # index slicing, not pop(0): linear time
    while start < len(tokens) and tokens[start] in _LEADING:
        start += 1
    tokens = tokens[start:]
    # "P. Ltd" leaves a lone "p" before "ltd"; trailing forms are stripped repeatedly.
    while len(tokens) > 1 and tokens[-1] in _TRAILING:
        tokens.pop()
    return " ".join(tokens)


def match_names(a: str, b: str) -> NameMatch:
    if len(a) > MAX_NAME_LEN or len(b) > MAX_NAME_LEN:
        return NameMatch(MatchLevel.LOW, 0.0)
    ta, tb = normalise_name(a).split(), normalise_name(b).split()
    if not ta or not tb:
        return NameMatch(MatchLevel.LOW, 0.0)
    score = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    if score >= HIGH_THRESHOLD:
        level = MatchLevel.HIGH
    elif score >= MEDIUM_THRESHOLD:
        level = MatchLevel.MEDIUM
    else:
        level = MatchLevel.LOW
    return NameMatch(level, score)
