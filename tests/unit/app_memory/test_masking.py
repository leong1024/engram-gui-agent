import random
import re
import string

import pytest

from tests.unit.app_memory.fixtures import screens

ALPHABET = string.ascii_letters + string.digits + " .,:;/@+-()%$#_٣۴５"
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
SEEDS = range(200)


def _random_text(seed: int) -> str:
    rng = random.Random(seed)
    return "".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 60)))


def _screen_with_texts(texts: list[str], *, editable: bool) -> list[dict]:
    extra = [
        screens.element(
            "android.widget.EditText" if editable else "android.widget.TextView",
            (40, 2305, 1000, 2335),
            rid=f"app:id/extra_{'abcdefghij'[index % 10]}",
            text=text,
            desc=text,
            editable=editable,
        )
        for index, text in enumerate(texts)
    ]
    return screens.settings() + extra


@pytest.mark.parametrize("seed", SEEDS)
def test_no_digit_or_email_survives_in_static_tokens(abstract_of, seed):
    text = _random_text(seed)
    email = f"user{seed}@mail{seed}.example.com"
    elements = _screen_with_texts([text, f"contact {email} now"], editable=False)
    tokens = abstract_of(elements).static_tokens
    assert not any(ch.isdigit() for token in tokens for ch in token), tokens
    assert not any(EMAIL.search(token) for token in tokens), tokens


@pytest.mark.parametrize("seed", SEEDS)
def test_text_field_content_never_survives(abstract_of, seed):
    secret = f"hunter{seed}-{_random_text(seed)}".replace(" ", "")
    elements = _screen_with_texts([secret], editable=True)
    tokens = abstract_of(elements).static_tokens
    assert not any(secret in token for token in tokens)


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("Battery 87%", "Battery <PERCENT>"),
        ("Updated 10:42 AM", "Updated <TIME>"),
        ("Due 2026-11-16", "Due <DATE>"),
        ("Pay $12.50", "Pay <CURRENCY>"),
        ("Call +1 (555) 123-4567", "Call <PHONE>"),
        ("mail me at a.b@example.org", "mail me at <EMAIL>"),
        ("see https://example.com/x?y=1", "see <URL>"),
        ("Wi-Fi 6", "Wi-Fi <NUM>"),
    ],
)
def test_variable_patterns_become_placeholders(abstract_of, raw, masked):
    elements = _screen_with_texts([raw], editable=False)
    assert masked in abstract_of(elements).static_tokens


def test_long_text_is_content_and_is_dropped(abstract_of):
    long_text = "This sentence is clearly article content, not a label"
    assert len(long_text) > 40
    elements = _screen_with_texts([long_text], editable=False)
    assert long_text not in abstract_of(elements).static_tokens


def test_text_at_the_limit_is_kept(abstract_of):
    label = "x" * 40
    elements = _screen_with_texts([label], editable=False)
    assert label in abstract_of(elements).static_tokens


def test_list_item_text_never_reaches_the_state(abstract_of):
    people = {"Alice Smith": "Dinner at 7?", "Bob Jones": "Call me 555-0100"}
    tokens = abstract_of(screens.messages(people), package="com.google.android.apps.messaging")
    joined = " ".join(tokens.static_tokens)
    assert "Alice" not in joined and "Bob" not in joined and "Dinner" not in joined


def test_text_field_hint_is_kept(abstract_of):
    tokens = abstract_of(screens.settings(query="my private query")).static_tokens
    assert "Search settings" in tokens
    assert "my private query" not in tokens
