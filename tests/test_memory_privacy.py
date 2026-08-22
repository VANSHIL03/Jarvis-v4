"""
Tests for the memory privacy layer (Sections 6, 14 and 27).

Section 6 is a prohibition, not a preference: "Do NOT blindly store literally
every piece of information", and never passwords, tokens, card numbers, banking
credentials, private keys or API keys. Two things make that hard to get right:

  * there are *two* stores. A secret refused by SQLite but embedded into FAISS is
    still on disk and still semantically searchable, so both are checked
    separately here -- and "forget" is only honoured if it clears both.
  * the vector store is a pickle of raw text. There is no schema to hide behind;
    if the string went in, it is in the file.

So the assertions below deliberately read the raw bytes of jarvis.db and the raw
document list of the vector store rather than trusting the return value of the
call that was supposed to refuse.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from memory.categories import (
    MemoryCategory,
    classify_fact,
    is_masked_when_shown,
    is_persisted,
    requires_explicit_request,
    ttl_days,
)
from memory.redaction import MASK, SecretScanner, contains_secret, luhn_valid, redact


# --------------------------------------------------------------------------
# Isolation. MemoryManager reads settings at construction and loading the
# sentence-transformer costs ~8s, so one instance is shared per module against a
# temporary data dir and wiped between tests.
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def shared_memory(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("memory_privacy")
    saved = (settings.DATA_DIR, settings.DB_PATH, settings.VECTOR_DB_DIR)
    settings.DATA_DIR = data_dir
    settings.DB_PATH = data_dir / "jarvis.db"
    settings.VECTOR_DB_DIR = data_dir

    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    try:
        yield manager
    finally:
        settings.DATA_DIR, settings.DB_PATH, settings.VECTOR_DB_DIR = saved


@pytest.fixture
def memory(shared_memory):
    shared_memory.forget_everything()
    shared_memory.vector_store.clear()
    shared_memory._skip_next_embedding = False
    return shared_memory


def db_bytes(memory):
    """Raw SQLite file contents -- the only honest check for 'never stored'."""
    from pathlib import Path

    path = Path(memory.db.db_path)
    if not path.exists():
        return b""
    return path.read_bytes()


def vector_texts(memory):
    return [str(doc.get("text", "")) for doc in memory.vector_store.documents]


# --------------------------------------------------------------------------
# The scanner
# --------------------------------------------------------------------------
SECRETS = [
    "mera gmail password Hunter2Secret! hai",
    "my password is Tr0ub4dor&3",
    "the api key is sk-proj-AbCdEf1234567890XyZwVu",
    "github token ghp_AbCd1234EfGh5678IjKl9012MnOp3456",
    "my card number is 4111 1111 1111 1111",
    "atm pin 4291 hai",
    "aws secret access key wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "-----BEGIN RSA PRIVATE KEY-----MIIEowIBAAKCAQEA-----END RSA PRIVATE KEY-----",
]

INNOCENT = [
    "mera favourite editor VS Code hai",
    "I prefer dark mode in all my apps",
    "meeting kal subah 10 baje hai",
    "my sister's name is Ananya",
    "remind me to submit the DBMS assignment on Friday",
    "I am learning about password hashing and bcrypt",
    "change my password tomorrow",
    "my office access key card is in my bag",
    "the secret to good code is small functions",
]


@pytest.mark.parametrize("text", SECRETS)
def test_scanner_detects_secrets(text):
    assert contains_secret(text) is True, f"missed a secret in {text!r}"


@pytest.mark.parametrize("text", INNOCENT)
def test_scanner_does_not_flag_innocent_text(text):
    """
    A scanner that flags everything is a scanner nobody can use.

    The last case matters most: talking *about* passwords is not a password, and
    refusing to remember "I am learning about password hashing" would be wrong.
    """
    assert contains_secret(text) is False, f"false positive on {text!r}"


@pytest.mark.parametrize("text", SECRETS)
def test_redaction_removes_the_value_and_keeps_the_shape(text):
    cleaned = redact(text)
    assert MASK in cleaned
    assert cleaned != text


def test_redaction_does_not_leave_the_secret_behind():
    cleaned = redact("my password is Tr0ub4dor&3 ok")
    assert "Tr0ub4dor&3" not in cleaned


def test_luhn_rejects_a_random_16_digit_number():
    """
    Without the checksum, every order number and ID becomes a "card number".

    4111 1111 1111 1111 is the standard Visa test number and passes; the second
    is a digit off and must not.
    """
    assert luhn_valid("4111111111111111") is True
    assert luhn_valid("4111111111111112") is False


def test_scanner_describes_findings_without_quoting_them():
    """Section 27: the log line that reports a refusal must not contain the secret."""
    scanner = SecretScanner()
    matches = scanner.scan("my password is Tr0ub4dor&3")
    description = scanner.describe(matches)
    assert description
    assert "Tr0ub4dor&3" not in description
    assert "Tr0ub4dor&3" not in scanner.refusal_reply("my password is Tr0ub4dor&3")


# --------------------------------------------------------------------------
# Secrets never reach either store
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text", SECRETS)
def test_remember_refuses_a_secret(memory, text):
    result = memory.remember(text, explicit=True)
    assert result["stored"] is False
    assert result["reason"] == "sensitive"
    assert result["speech_reply"], "refused without telling the user why"


def test_a_refused_secret_never_reaches_sqlite(memory):
    secret = "Tr0ub4dor&3"
    memory.remember(f"mera password {secret} hai", explicit=True)

    assert secret.encode() not in db_bytes(memory)
    assert all(secret not in f.get("value_data", "") for f in memory.get_all_facts())


def test_a_refused_secret_never_reaches_the_vector_store(memory):
    """
    FAISS is the store that is easy to forget about.

    A refusal that only guards SQLite still leaves the plaintext in
    vector_store.pkl, and retrieve_relevant_memory() would happily surface it in
    the next planner prompt.
    """
    secret = "sk-proj-AbCdEf1234567890XyZwVu"
    memory.remember(f"the api key is {secret}", explicit=True)

    assert memory.vector_store.count() == 0
    assert all(secret not in text for text in vector_texts(memory))


def test_an_explicit_request_does_not_override_the_refusal(memory):
    """
    "Remember this: my password is X" is still refused.

    Section 6 allows an explicit exception only when a secure store has been
    deliberately configured, which it has not been here.
    """
    result = memory.remember("remember this: my password is Tr0ub4dor&3", explicit=True)
    assert result["stored"] is False
    assert b"Tr0ub4dor" not in db_bytes(memory)


def test_a_secret_spoken_in_conversation_is_redacted_before_storage(memory):
    """
    Section 27 applies to dialogue too.

    The user can say a password out loud in passing; the transcript row and its
    embedding must both be scrubbed, because both are written to disk.
    """
    memory.record_turn("privacy_test", "user", "my password is Tr0ub4dor&3 by the way")

    assert b"Tr0ub4dor" not in db_bytes(memory)
    assert all("Tr0ub4dor" not in text for text in vector_texts(memory))

    turns = memory.get_dialogue_context(session_id="privacy_test", turns=4)
    assert turns, "the turn was dropped entirely instead of redacted"
    assert all("Tr0ub4dor" not in str(t.get("content", "")) for t in turns)


# --------------------------------------------------------------------------
# Ordinary memories do get stored
# --------------------------------------------------------------------------
def test_an_ordinary_fact_is_stored_in_both_stores(memory):
    result = memory.remember("mera favourite editor VS Code hai", explicit=True)
    assert result["stored"] is True
    assert result["key"]

    assert any("VS Code" in f["value_data"] for f in memory.get_all_facts())
    assert any("VS Code" in text for text in vector_texts(memory))


def test_multiple_facts_all_survive(memory):
    """
    Regression: every free-form fact used to be written under one fixed key.

    user_facts.key_name is UNIQUE, so each new "remember ..." overwrote the last
    and only a single free-form memory could ever exist. Keys are slugged per
    fact now.
    """
    facts = [
        "mera favourite editor VS Code hai",
        "I prefer dark mode in all my apps",
        "my sister's name is Ananya",
        "mera college project Jarvis hai",
    ]
    keys = set()
    for text in facts:
        result = memory.remember(text, explicit=True)
        assert result["stored"] is True, text
        keys.add(result["key"])

    assert len(keys) == len(facts), "facts collided on the same key"
    stored = " | ".join(f["value_data"] for f in memory.get_all_facts())
    for text in facts:
        assert text in stored, f"lost: {text}"


def test_an_empty_memory_is_refused_politely(memory):
    result = memory.remember("   ", explicit=True)
    assert result["stored"] is False
    assert result["reason"] == "empty"


# --------------------------------------------------------------------------
# Forgetting clears both stores
# --------------------------------------------------------------------------
def test_forget_about_clears_sqlite(memory):
    memory.remember("mera college project Jarvis hai", explicit=True)
    assert any("Jarvis" in f["value_data"] for f in memory.get_all_facts())

    result = memory.forget_about("Jarvis")
    assert result["deleted"] > 0
    assert not any("Jarvis" in f["value_data"] for f in memory.get_all_facts())


def test_forget_about_clears_the_vector_store(memory):
    """
    Deleting from one store only would let JARVIS recall what it just forgot.

    The vector store keeps documents in a list pickled to disk, so deletion means
    rebuilding the index -- easy to skip, and invisible until recall surfaces the
    "forgotten" text again.
    """
    memory.remember("mera college project Jarvis hai", explicit=True)
    assert any("Jarvis" in text for text in vector_texts(memory))

    memory.forget_about("Jarvis")
    assert all("Jarvis" not in text for text in vector_texts(memory))
    assert memory.recall("Jarvis")["count"] == 0


def test_forget_about_an_unknown_topic_says_so(memory):
    result = memory.forget_about("quidditch")
    assert result["deleted"] == 0
    assert "kuch yaad nahi tha" in result["speech_reply"]


def test_forget_about_leaves_unrelated_memories_alone(memory):
    """"Forget about X" is not "forget everything"."""
    memory.remember("mera college project Jarvis hai", explicit=True)
    memory.remember("I prefer dark mode in all my apps", explicit=True)

    memory.forget_about("Jarvis")
    assert any("dark mode" in f["value_data"] for f in memory.get_all_facts())
    assert any("dark mode" in text for text in vector_texts(memory))


def test_forget_key_removes_from_both_stores(memory):
    key = memory.remember("mera favourite editor VS Code hai", explicit=True)["key"]
    result = memory.forget_key(key)
    assert result["deleted"] > 0
    assert not any(f["key_name"] == key for f in memory.get_all_facts())
    assert all("VS Code" not in text for text in vector_texts(memory))


def test_forget_last_removes_the_most_recent_memory(memory):
    memory.remember("I prefer dark mode in all my apps", explicit=True)
    memory.remember("mera favourite editor VS Code hai", explicit=True)

    result = memory.forget_last()
    assert result["deleted"] > 0
    assert "VS Code" in result["forgotten"]
    assert any("dark mode" in f["value_data"] for f in memory.get_all_facts())


def test_forget_everything_empties_both_stores(memory):
    for text in ("mera project Jarvis hai", "I prefer dark mode", "my sister is Ananya"):
        memory.remember(text, explicit=True)

    memory.forget_everything()
    assert memory.vector_store.count() == 0
    assert not [f for f in memory.get_all_facts() if f["key_name"].startswith("fact_")]


def test_do_not_remember_drops_the_embedding_and_suppresses_the_next(memory):
    """
    "Do not remember this" refers both backwards and forwards in practice.

    The SQLite dialogue row survives so the conversation stays coherent, but
    nothing is indexed for semantic recall.
    """
    memory.record_turn("dnr", "user", "I am interviewing at Zoho next week")
    assert any("Zoho" in text for text in vector_texts(memory))

    result = memory.do_not_remember(session_id="dnr")
    assert result["deleted"] >= 1
    assert all("Zoho" not in text for text in vector_texts(memory))

    before = memory.vector_store.count()
    memory.record_turn("dnr", "user", "and the salary discussion is confidential")
    assert memory.vector_store.count() == before, "next turn was embedded anyway"


# --------------------------------------------------------------------------
# Showing what is remembered
# --------------------------------------------------------------------------
def test_list_memories_groups_by_category(memory):
    memory.remember("I prefer dark mode in all my apps", explicit=True)
    memory.remember("mera college project Jarvis hai", explicit=True)

    listing = memory.list_memories()
    assert listing["count"] >= 2
    assert listing["grouped"]
    assert listing["speech_reply"]


def test_list_memories_masks_sensitive_rows(memory):
    """
    Answering "show me what you remember" must not itself be the leak.

    Nothing sensitive can be stored through remember(), so this writes the row
    directly -- the point is that the *display* path masks it regardless of how
    it got there.
    """
    memory.db.store_free_fact(
        category=MemoryCategory.SENSITIVE.value,
        value_data="vault-code-8891",
        ttl_days=None,
        source="test",
        explicit=True,
        sensitive=True,
    )
    listing = memory.list_memories(mask_sensitive=True)
    assert "vault-code-8891" not in listing["speech_reply"]
    assert "[hidden]" in listing["speech_reply"]


def test_recall_does_not_return_sensitive_rows(memory):
    memory.db.store_free_fact(
        category=MemoryCategory.SENSITIVE.value,
        value_data="vault-code-8891",
        ttl_days=None,
        source="test",
        explicit=True,
        sensitive=True,
    )
    result = memory.recall("vault")
    assert all("vault-code-8891" not in hit for hit in result["memories"])


def test_list_memories_on_an_empty_store_is_not_an_error(memory):
    listing = memory.list_memories()
    facts = [f for f in memory.get_all_facts() if f["key_name"].startswith("fact_")]
    assert not facts
    assert listing["speech_reply"]


# --------------------------------------------------------------------------
# Category rules
# --------------------------------------------------------------------------
def test_ephemeral_memories_are_never_persisted():
    assert is_persisted(MemoryCategory.EPHEMERAL) is False
    assert is_persisted(MemoryCategory.PERSONAL_FACT) is True


def test_sensitive_requires_an_explicit_request_and_is_masked():
    assert requires_explicit_request(MemoryCategory.SENSITIVE) is True
    assert is_masked_when_shown(MemoryCategory.SENSITIVE) is True
    assert requires_explicit_request(MemoryCategory.PREFERENCE) is False
    assert is_masked_when_shown(MemoryCategory.PREFERENCE) is False


def test_short_term_ttl_follows_the_setting():
    """Phase 14 made this configurable; the table value is only a fallback."""
    saved = settings.MEMORY_SHORT_TERM_TTL_DAYS
    try:
        settings.MEMORY_SHORT_TERM_TTL_DAYS = 3
        assert ttl_days(MemoryCategory.SHORT_TERM) == 3
        settings.MEMORY_SHORT_TERM_TTL_DAYS = 0      # nonsense: ignore, don't expire instantly
        assert ttl_days(MemoryCategory.SHORT_TERM) == 7
    finally:
        settings.MEMORY_SHORT_TERM_TTL_DAYS = saved


def test_permanent_categories_have_no_ttl():
    assert ttl_days(MemoryCategory.PREFERENCE) is None
    assert ttl_days(MemoryCategory.PERSONAL_FACT) is None


def test_classifier_routes_obvious_cues():
    assert classify_fact("mera password kuch bhi hai") is MemoryCategory.SENSITIVE
    assert classify_fact("mujhe dark mode pasand hai") is MemoryCategory.PREFERENCE
    assert classify_fact("roz subah 6 baje uthta hoon") is MemoryCategory.ROUTINE
    assert classify_fact("remind me to submit the assignment") is MemoryCategory.TASK
    assert classify_fact("mera project Jarvis hai") is MemoryCategory.PROJECT


def test_category_parse_handles_legacy_and_junk_values():
    assert MemoryCategory.parse("user") is MemoryCategory.PERSONAL_FACT
    assert MemoryCategory.parse("preferences") is MemoryCategory.PREFERENCE
    assert MemoryCategory.parse("secret") is MemoryCategory.SENSITIVE
    assert MemoryCategory.parse("") is MemoryCategory.PERSONAL_FACT
    assert MemoryCategory.parse("gibberish", MemoryCategory.PROJECT) is MemoryCategory.PROJECT
