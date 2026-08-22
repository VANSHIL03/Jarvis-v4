"""
JARVIS v4 - Secret Detection & Redaction

Two hard rules from the specification are enforced here, in one place:

  * Section 6 -- never store passwords, authentication tokens, credit card
    numbers, banking credentials, private keys or API keys.
  * Section 27 -- never log passwords, tokens or sensitive secrets.

MemoryManager consults this before anything reaches SQLite or the FAISS vector
store, so a credential spoken in passing is masked in both.

Section 27's logging half is NOT yet wired: utils/logger.py has no RedactingFilter,
so a secret interpolated into a log message still reaches logs/jarvis.log verbatim.
The obvious fix is circular -- utils.logger is imported by nearly everything, and
`memory/__init__.py` eagerly imports MemoryManager, so importing this module from
the logger would both cycle and pull an ~8s sentence-transformer load into every
`import utils.logger`. Closing it means making the memory package import lazily
first. Until then, callers must not interpolate raw user text into log messages.

Card numbers are Luhn-checked rather than matched on length alone, so a 16-digit
order ID is not mistaken for a payment card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Pattern, Tuple

MASK = "[REDACTED]"

# Words that often follow "password"/"key" without being a secret, so
# "password manager use karta hoon" is not treated as a credential.
_VALUE_STOPWORDS = {
    "manager", "managers", "protected", "protection", "reset", "resetting",
    "change", "changed", "changing", "strength", "field", "box", "hint",
    "policy", "prompt", "screen", "page", "kaise", "kya", "kyun", "kyu",
    "bhool", "bhul", "bhoolna", "forgot", "forget", "karo", "karna", "kar",
    "karta", "karte", "dalna", "daal", "dena", "wala", "wali", "nahi", "mat",
    "hai", "hain", "tha", "is", "are", "was", "the", "a", "an", "my", "mera",
    "meri", "mujhe", "yaad", "remember", "save", "store", "secure", "safe",
    "strong", "weak", "empty", "blank", "unknown", "kuch", "koi", "bhi",
    "and", "or", "for", "to", "of", "in", "on", "at", "se", "ka", "ki", "ke",
    "ko", "par", "me", "mein", "use", "using", "kabhi", "always", "never",
}

_TRIM_CHARS = " \t\r\n.,;:!?'\"()[]{}<>"


def luhn_valid(digits: str) -> bool:
    """Standard Luhn checksum, used to separate real card numbers from IDs."""
    digits = re.sub(r"\D", "", digits or "")
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = ord(char) - 48
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _looks_like_secret_value(value: str) -> bool:
    """Rejects captures that are ordinary words rather than credentials."""
    cleaned = (value or "").strip(_TRIM_CHARS)
    if len(cleaned) < 4:
        return False
    if cleaned.lower() in _VALUE_STOPWORDS:
        return False
    # A bare short word with no digits/symbols is usually prose, not a secret.
    if len(cleaned) < 6 and cleaned.isalpha():
        return False
    return True


def _looks_like_credential_token(value: str) -> bool:
    """
    Stricter test, used when no "is"/"=" connector separated keyword from value.

    "change my password tomorrow" puts an innocent word right after the keyword,
    so adjacency alone cannot imply a secret. A real credential sitting there
    mixes letters with digits, or is long and non-alphabetic.
    """
    cleaned = (value or "").strip(_TRIM_CHARS)
    if not _looks_like_secret_value(cleaned):
        return False
    has_digit = any(char.isdigit() for char in cleaned)
    has_alpha = any(char.isalpha() for char in cleaned)
    if has_digit and has_alpha:
        return True
    return len(cleaned) >= 12 and bool(re.search(r"[^A-Za-z]", cleaned))


def _digits_luhn(value: str) -> bool:
    return luhn_valid(value)


@dataclass(frozen=True)
class SecretPattern:
    """One detector: what it finds, how to describe it, how to verify it."""

    name: str
    label: str                                   # Hinglish description for the user
    regex: Pattern[str]
    value_group: int = 0                         # 0 = whole match is the secret
    validator: Optional[Callable[[str], bool]] = None


@dataclass(frozen=True)
class SecretMatch:
    name: str
    label: str
    start: int
    end: int
    value: str


#: Credential keywords, shared by the three sentence shapes below.
#: Order matters: the longest phrasing must come first, or the bare `secret`
#: alternative wins and the capture group grabs the next *word* instead of the
#: value. That is how "aws secret access key wJal..." went undetected -- `secret`
#: matched, the value captured was "access", and the validator correctly rejected
#: it as prose, so the real key sailed through.
_SECRET_WORDS = (
    r"(?:pass\s*word|password|passwd|pwd|passcode|paasword"
    r"|secret[\s_-]?access[\s_-]?key|access[\s_-]?key[\s_-]?id|access[\s_-]?key"
    r"|api[\s_-]?key|secret[\s_-]?key|access[\s_-]?token|auth[\s_-]?token"
    r"|refresh[\s_-]?token|client[\s_-]?secret|private[\s_-]?key"
    r"|licence[\s_-]?key|license[\s_-]?key|app[\s_-]?secret|secret)"
)
_VALUE = r"['\"]?([^\s'\"]{4,})"

PATTERNS: Tuple[SecretPattern, ...] = (
    SecretPattern(
        "private_key", "private key",
        re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END[A-Z ]*PRIVATE KEY-----)?",
                   re.IGNORECASE),
    ),
    SecretPattern(
        "openai_key", "API key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b"),
    ),
    SecretPattern(
        "anthropic_key", "API key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{6,}\b"),
    ),
    SecretPattern(
        "github_token", "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
    ),
    SecretPattern(
        "google_api_key", "Google API key",
        re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b"),
    ),
    SecretPattern(
        "aws_key", "AWS access key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ),
    SecretPattern(
        "slack_token", "Slack token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    ),
    SecretPattern(
        "jwt", "authentication token",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),
    ),
    SecretPattern(
        "bearer_token", "authentication token",
        re.compile(r"\bbearer\s+([A-Za-z0-9._\-]{16,})", re.IGNORECASE),
        value_group=1,
    ),
    # "password is X", "api key = X", "client_secret: X"
    SecretPattern(
        "credential_assigned", "password ya API key",
        re.compile(_SECRET_WORDS + r"\s*(?:is|are|=|:|->)\s*" + _VALUE, re.IGNORECASE),
        value_group=1,
        validator=_looks_like_secret_value,
    ),
    # Hinglish: "mera password Hunter2xyz hai"
    SecretPattern(
        "credential_hinglish", "password ya API key",
        re.compile(_SECRET_WORDS + r"\s+" + _VALUE + r"['\"]?\s+(?:hai|hain)\b", re.IGNORECASE),
        value_group=1,
        validator=_looks_like_secret_value,
    ),
    # Bare adjacency: only when the value itself looks like a credential.
    SecretPattern(
        "credential_adjacent", "password ya API key",
        re.compile(_SECRET_WORDS + r"\s+" + _VALUE, re.IGNORECASE),
        value_group=1,
        validator=_looks_like_credential_token,
    ),
    SecretPattern(
        "pin", "PIN",
        re.compile(r"\b(?:upi\s*pin|atm\s*pin|card\s*pin|mpin|pin\s*(?:code|number)?)\b"
                   r"\s*(?:is|hai|=|:)?\s*(\d{4,8})\b", re.IGNORECASE),
        value_group=1,
    ),
    SecretPattern(
        "cvv", "card CVV",
        re.compile(r"\b(?:cvv|cvc|csc)\b\s*(?:is|hai|=|:)?\s*(\d{3,4})\b", re.IGNORECASE),
        value_group=1,
    ),
    SecretPattern(
        "otp", "OTP",
        re.compile(r"\b(?:otp|one[\s-]?time[\s-]?password|verification\s*code)\b"
                   r"\s*(?:is|hai|=|:)?\s*(\d{4,8})\b", re.IGNORECASE),
        value_group=1,
    ),
    SecretPattern(
        "aadhaar", "Aadhaar number",
        re.compile(r"\b(?:aadhaar|aadhar|uidai|uid)\b\s*(?:number|no|is|hai|=|:)?\s*"
                   r"(\d{4}\s?\d{4}\s?\d{4})\b", re.IGNORECASE),
        value_group=1,
    ),
    SecretPattern(
        "bank_account", "bank account number",
        re.compile(r"\b(?:account\s*(?:number|no|num)|a/c(?:\s*no)?|ifsc)\b"
                   r"\s*(?:is|hai|=|:)?\s*([A-Za-z0-9]{9,20})\b", re.IGNORECASE),
        value_group=1,
    ),
    SecretPattern(
        "card_number", "card number",
        re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])"),
        validator=_digits_luhn,
    ),
)


class SecretScanner:
    """
    Finds credentials in free text.

    Deliberately biased toward false positives on the *storage* path: refusing
    to remember something harmless is a minor annoyance, while quietly
    embedding a password into the vector store is not recoverable.
    """

    def __init__(self, patterns: Optional[Tuple[SecretPattern, ...]] = None):
        self.patterns = patterns or PATTERNS

    def scan(self, text: str) -> List[SecretMatch]:
        """All non-overlapping secrets found, ordered by position."""
        if not text:
            return []
        text = str(text)
        found: List[SecretMatch] = []

        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                group = pattern.value_group
                try:
                    value = match.group(group) if group else match.group(0)
                except (IndexError, re.error):  # pragma: no cover - defensive
                    value = match.group(0)
                if value is None:
                    continue
                if pattern.validator and not pattern.validator(value):
                    continue
                if group:
                    start, end = match.span(group)
                else:
                    start, end = match.span(0)
                found.append(SecretMatch(pattern.name, pattern.label, start, end, value))

        # Drop matches contained inside an earlier, longer match.
        found.sort(key=lambda m: (m.start, -(m.end - m.start)))
        deduped: List[SecretMatch] = []
        for match in found:
            if any(match.start >= kept.start and match.end <= kept.end for kept in deduped):
                continue
            deduped.append(match)
        return deduped

    def contains_secret(self, text: str) -> bool:
        return bool(self.scan(text))

    def redact(self, text: str, mask: str = MASK) -> str:
        """Replaces every detected secret with a mask, keeping surrounding text."""
        matches = self.scan(text)
        if not matches:
            return text
        out = str(text)
        for match in sorted(matches, key=lambda m: m.start, reverse=True):
            out = out[: match.start] + mask + out[match.end:]
        return out

    def describe(self, matches: List[SecretMatch]) -> str:
        """Hinglish phrase naming what was found, for the refusal reply."""
        if not matches:
            return ""
        labels: List[str] = []
        for match in matches:
            if match.label not in labels:
                labels.append(match.label)
        if len(labels) == 1:
            return labels[0]
        return ", ".join(labels[:-1]) + f" aur {labels[-1]}"

    def refusal_reply(self, text: str) -> str:
        """The spoken response when a memory request contains a credential."""
        found = self.describe(self.scan(text))
        what = found or "sensitive information"
        return (
            f"Sir, isme {what} hai, aur main security ke liye passwords, tokens, "
            "card numbers ya keys kabhi save nahi karta. Baaki koi bhi baat "
            "khushi se yaad rakh loonga."
        )


#: Shared instance -- the scanner is stateless, so one is enough.
scanner = SecretScanner()


def contains_secret(text: str) -> bool:
    return scanner.contains_secret(text)


def redact(text: str, mask: str = MASK) -> str:
    return scanner.redact(text, mask)


__all__ = [
    "SecretScanner",
    "SecretMatch",
    "SecretPattern",
    "PATTERNS",
    "MASK",
    "scanner",
    "contains_secret",
    "redact",
    "luhn_valid",
]
