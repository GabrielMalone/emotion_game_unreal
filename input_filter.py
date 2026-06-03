"""
input_filter.py — Sanitize player input from Unreal speech-to-text.

Filters out:
1. Profanity / bad language
2. Non-speech audio artifacts (e.g. [keyboard clicking], [music], [coughing])
"""

import re
from typing import Tuple

# ---------------------------------------------------------------------------
# Profanity filter
# ---------------------------------------------------------------------------

# Word-boundary-matched profanity list (add more as needed).
# Kept lowercase; matching is case-insensitive.
_PROFANITY_WORDS: list[str] = [
    "fuck", "fucking", "fucked", "fucker",
    "shit", "shitty", "shite", "bullshit",
    "asshole", "assholes", "asshat",
    "bitch", "bitches", "bitching",
    "bastard", "bastards",
    "damn", "dammit", "god damn", "goddamn",
    "cunt", "cunts",
    "dick", "dicks", "dickhead",
    "piss", "pissed",
    "slut", "whore",
    "retard", "retarded",
    "nigger", "nigga",
    "faggot", "fag",
    "cock", "cocksucker",
    "motherfucker", "motherfucking",
    "douche", "douchebag",
]

# Compiled regex: case-insensitive, word-boundary matching.
_PROFANITY_RE: re.Pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _PROFANITY_WORDS) + r")\b",
    re.IGNORECASE,
)


def contains_profanity(text: str) -> bool:
    """Return True if *text* contains any profanity."""
    return bool(_PROFANITY_RE.search(text))


def censor_profanity(text: str) -> str:
    """Replace profanity with asterisks, preserving word length."""
    return _PROFANITY_RE.sub(lambda m: "*" * len(m.group()), text)


# ---------------------------------------------------------------------------
# Non-speech / background-noise detection
# ---------------------------------------------------------------------------

# Patterns that indicate the speech-to-text engine picked up background
# noise or filler instead of actual player speech.
_NON_SPEECH_PATTERNS: list[str] = [
    # Square-bracket sound-effect tags (common in STT output)
    r"\[.*?(?:keyboard|typing|clicking|clacking).*?\]",
    r"\[.*?(?:music|song|melody|playing).*?\]",
    r"\[.*?(?:cough|coughing|sneeze|sniffle).*?\]",
    r"\[.*?(?:laughter|laughing|giggle|chuckle).*?\]",
    r"\[.*?(?:silence|quiet|pause|no speech).*?\]",
    r"\[.*?(?:background.noise|static|feedback|buzz|hum).*?\]",
    r"\[.*?(?:footstep|walking|door|opening|closing).*?\]",
    r"\[.*?(?:phone|ringing|vibrat|notification).*?\]",
    r"\[.*?(?:engine|car|traffic|wind).*?\]",
    r"\[.*?(?:sigh|breathing|breath|gasp|yawn).*?\]",
    r"\[.*?(?:applause|clapping|cheering).*?\]",
    r"\[.*?(?:bang|crash|thud|thump|bump).*?\]",
    r"\[.*?(?:beep|ding|chime|alarm|siren).*?\]",

    # Bare noise tags
    r"^\s*\[.*?\]\s*$",

    # Things that are clearly not player speech
    r"^\s*$",                      # blank / whitespace-only
    r"^[^a-zA-Z0-9]+$",           # no alphanumeric at all (punctuation, symbols only)
    r"^[a-zA-Z]\s*$",             # single letter
    r"^(?:um|uh|er|hm|hmm|mm|mhm)\s*$",  # just filler sounds
    r"^[.,!?;:'\"()\[\]{}]+\s*$", # just punctuation
]

_NON_SPEECH_RE: re.Pattern = re.compile(
    "|".join(f"(?:{p})" for p in _NON_SPEECH_PATTERNS),
    re.IGNORECASE,
)

# If the cleaned text is shorter than this many letters, treat as non-speech.
_MIN_LETTERS_FOR_SPEECH: int = 3


def is_likely_non_speech(text: str) -> bool:
    """Return True if *text* looks like background noise, not player speech."""
    stripped = text.strip()
    if not stripped:
        return True
    # Check against the non-speech regex patterns.
    if _NON_SPEECH_RE.search(stripped):
        return True
    # Too few alphabetic characters → probably noise.
    letters = sum(c.isalpha() for c in stripped)
    if letters < _MIN_LETTERS_FOR_SPEECH:
        return True
    return False


# ---------------------------------------------------------------------------
# Combined sanitization
# ---------------------------------------------------------------------------

def sanitize_player_input(text: str) -> Tuple[str, bool, bool]:
    """Sanitize player text input.

    Returns:
        (cleaned_text, was_ignored, had_profanity)
        - cleaned_text: the sanitized version (empty string if ignored).
        - was_ignored: True if the input should be dropped entirely (non-speech).
        - had_profanity: True if profanity was detected and censored.
    """
    if is_likely_non_speech(text):
        return ("", True, False)

    if contains_profanity(text):
        return (censor_profanity(text), False, True)

    return (text, False, False)
