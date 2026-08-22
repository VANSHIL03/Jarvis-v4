"""
JARVIS v4 - Personal Memory Categories

Section 6 of the specification is explicit that JARVIS must not blindly store
every piece of information. Each remembered item is therefore classified, and the
category -- not the caller -- decides three things:

  * whether it is written to disk at all (EPHEMERAL never is),
  * how long it survives (SHORT_TERM expires),
  * whether it may be stored automatically (SENSITIVE may not, ever).

SENSITIVE is the important one: passwords, tokens, card numbers and keys are
never auto-stored, and even an explicit request is refused by
memory.redaction.SecretScanner unless the user has deliberately configured a
secure store. See [[jarvis-memory-privacy]].
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Optional


class MemoryCategory(str, Enum):
    """The ten categories from the specification, in escalating persistence."""

    EPHEMERAL = "ephemeral"
    SHORT_TERM = "short_term"
    PREFERENCE = "preference"
    PERSONAL_FACT = "personal_fact"
    PROJECT = "project"
    CONTACT = "contact"
    ROUTINE = "routine"
    TASK = "task"
    IMPORTANT = "important"
    SENSITIVE = "sensitive"

    @classmethod
    def parse(cls, value, default: "MemoryCategory" = None) -> "MemoryCategory":
        """Coerces a loose string (LLM output, old DB rows) into a category."""
        fallback = default if default is not None else cls.PERSONAL_FACT
        if isinstance(value, cls):
            return value
        if not value:
            return fallback
        key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        for member in cls:
            if key == member.value or key == member.name.lower():
                return member
        # Legacy rows written before categories existed.
        legacy = {
            "user": cls.PERSONAL_FACT,
            "preferences": cls.PREFERENCE,
            "user_preference": cls.PREFERENCE,
            "fact": cls.PERSONAL_FACT,
            "general": cls.PERSONAL_FACT,
            "secret": cls.SENSITIVE,
            "credential": cls.SENSITIVE,
        }
        return legacy.get(key, fallback)


#: category -> (persisted, ttl_days, requires_explicit_request, mask_when_shown)
_RULES: Dict[MemoryCategory, tuple] = {
    MemoryCategory.EPHEMERAL:     (False, None, False, False),
    MemoryCategory.SHORT_TERM:    (True,     7, False, False),
    MemoryCategory.PREFERENCE:    (True,  None, False, False),
    MemoryCategory.PERSONAL_FACT: (True,  None, False, False),
    MemoryCategory.PROJECT:       (True,  None, False, False),
    MemoryCategory.CONTACT:       (True,  None, False, False),
    MemoryCategory.ROUTINE:       (True,  None, False, False),
    MemoryCategory.TASK:          (True,    30, False, False),
    MemoryCategory.IMPORTANT:     (True,  None, False, False),
    MemoryCategory.SENSITIVE:     (True,  None,  True,  True),
}


def is_persisted(category: MemoryCategory) -> bool:
    """False for EPHEMERAL, which lives only inside the current conversation."""
    return _RULES[category][0]


def ttl_days(category: MemoryCategory) -> Optional[int]:
    """Days before the memory expires, or None to keep it indefinitely."""
    return _RULES[category][1]


def requires_explicit_request(category: MemoryCategory) -> bool:
    """True when only a literal 'remember this' may create the memory."""
    return _RULES[category][2]


def is_masked_when_shown(category: MemoryCategory) -> bool:
    """True when 'show me what you remember' must not print the raw value."""
    return _RULES[category][3]


#: Hinglish headings used by the "show me what you remember about me" reply.
DISPLAY_LABELS: Dict[MemoryCategory, str] = {
    MemoryCategory.EPHEMERAL: "Abhi ki baat",
    MemoryCategory.SHORT_TERM: "Kuch dino ki baatein",
    MemoryCategory.PREFERENCE: "Aapki pasand",
    MemoryCategory.PERSONAL_FACT: "Aapke baare mein",
    MemoryCategory.PROJECT: "Projects",
    MemoryCategory.CONTACT: "Contacts",
    MemoryCategory.ROUTINE: "Routine",
    MemoryCategory.TASK: "Tasks",
    MemoryCategory.IMPORTANT: "Important",
    MemoryCategory.SENSITIVE: "Sensitive (chhupa hua)",
}


# --------------------------------------------------------------- classifier
# Ordered: the first pattern that matches wins, so SENSITIVE cues are tested
# before the softer preference/routine cues.
_CUES = (
    (MemoryCategory.SENSITIVE, (
        r"\bpass(?:word|wd|code)\b", r"\bpin\b", r"\bcvv\b", r"\botp\b",
        r"\bapi[\s_-]?key\b", r"\bsecret\b", r"\btoken\b", r"\bcredential",
        r"\bprivate[\s_-]?key\b", r"\bcard\s*(?:number|no)\b",
        r"\baadhaar\b", r"\baadhar\b", r"\bupi\s*pin\b",
        r"\bbank\b.*\b(?:account|login|password)\b",
    )),
    (MemoryCategory.CONTACT, (
        r"\b(?:phone|mobile|contact)\s*(?:number|no)\b",
        r"\bnumber\s+(?:hai|is)\b", r"\bemail\s*(?:id|address)\b",
    )),
    (MemoryCategory.PROJECT, (
        r"\bproject\b", r"\brepo(?:sitory)?\b", r"\bcodebase\b",
        r"\bdeadline\b.*\bproject\b", r"\bclient\b",
    )),
    (MemoryCategory.ROUTINE, (
        r"\broz\b", r"\bdaily\b", r"\bevery\s+(?:day|morning|night|monday|week)\b",
        r"\bhar\s+(?:din|roz|subah|raat|hafte)\b", r"\broutine\b", r"\bschedule\b",
        r"\bhabit\b",
    )),
    (MemoryCategory.TASK, (
        r"\bremind\b", r"\byaad\s+dila\b", r"\btask\b", r"\bto-?do\b",
        r"\bkarna\s+hai\b", r"\bdeadline\b", r"\bexam\b", r"\bmeeting\b",
    )),
    (MemoryCategory.PREFERENCE, (
        r"\b(?:i|mujhe|mai|main|mera|meri)\b.*\b(?:like|prefer|pasand|favou?rite)\b",
        r"\bpasand\b", r"\bfavou?rite\b", r"\bprefer\b", r"\bhate\b",
        r"\bnapasand\b", r"\balways\s+use\b",
    )),
    (MemoryCategory.IMPORTANT, (
        r"\bimportant\b", r"\bzaroori\b", r"\bnever\s+forget\b",
        r"\bbahut\s+zaroori\b", r"\bkabhi\s+mat\s+bhool\b",
    )),
    (MemoryCategory.SHORT_TERM, (
        r"\btoday\b", r"\baaj\b", r"\bkal\b", r"\btomorrow\b", r"\bthis\s+week\b",
        r"\bis\s+hafte\b", r"\babhi\b",
    )),
)


def classify_fact(text: str, default: MemoryCategory = MemoryCategory.PERSONAL_FACT) -> MemoryCategory:
    """
    Guesses the category of a free-form memory.

    Only used to *route* a memory; it is never the safety boundary. Secrets are
    caught by SecretScanner regardless of what this returns, because a password
    phrased unusually must still be refused.
    """
    if not text or not str(text).strip():
        return default
    lowered = str(text).lower()
    for category, patterns in _CUES:
        for pattern in patterns:
            if re.search(pattern, lowered):
                return category
    return default


def slugify(text: str, max_len: int = 48) -> str:
    """
    Stable key fragment for a free-form fact.

    Facts are keyed ``fact_<slug>`` because ``user_facts.key_name`` is UNIQUE:
    writing every "remember ..." under one fixed key made each new memory
    overwrite the previous one, so only a single free-form fact could exist.
    """
    slug = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    if not slug:
        slug = "note"
    return slug[:max_len].rstrip("_")


__all__ = [
    "MemoryCategory",
    "DISPLAY_LABELS",
    "is_persisted",
    "ttl_days",
    "requires_explicit_request",
    "is_masked_when_shown",
    "classify_fact",
    "slugify",
]
