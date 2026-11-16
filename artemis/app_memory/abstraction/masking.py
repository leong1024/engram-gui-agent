import re
from collections.abc import Callable

from artemis.app_memory.abstraction.constants import MAX_LABEL_CHARS
from artemis.app_memory.abstraction.elements import Element

TextRule = Callable[[str], str]
ElementRule = Callable[[Element], Element]

_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_DATE = re.compile(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}")
_TIME = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?", re.IGNORECASE)
_DURATION = re.compile(r"\d+\s*(?:h|hr|hrs|min|mins|m|s|sec|secs|d)\b", re.IGNORECASE)
_CURRENCY = re.compile(r"[$€£¥₹]\s*\d[\d.,]*|\d[\d.,]*\s*[$€£¥₹]")
_PERCENT = re.compile(r"\d[\d.,]*\s*%")
_PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_NUMBER = re.compile(r"\d+")


def mask_email(text: str) -> str:
    return _EMAIL.sub("<EMAIL>", text)


def mask_url(text: str) -> str:
    return _URL.sub("<URL>", text)


def mask_date(text: str) -> str:
    return _DATE.sub("<DATE>", text)


def mask_time(text: str) -> str:
    return _TIME.sub("<TIME>", text)


def mask_currency(text: str) -> str:
    return _CURRENCY.sub("<CURRENCY>", text)


def mask_percent(text: str) -> str:
    return _PERCENT.sub("<PERCENT>", text)


def mask_duration(text: str) -> str:
    return _DURATION.sub("<DURATION>", text)


def mask_phone(text: str) -> str:
    return _PHONE.sub("<PHONE>", text)


def mask_number(text: str) -> str:
    return _NUMBER.sub("<NUM>", text)


TEXT_RULES: tuple[TextRule, ...] = (
    mask_email,
    mask_url,
    mask_date,
    mask_time,
    mask_currency,
    mask_percent,
    mask_duration,
    mask_phone,
    mask_number,
)


def mask_text(text: str) -> str:
    for rule in TEXT_RULES:
        text = rule(text)
    return text


def _drop_long(text: str) -> str:
    return "" if len(text) > MAX_LABEL_CHARS else text


def drop_field_content(element: Element) -> Element:
    if not element.editable:
        return element
    return element.with_labels(element.hint, element.content_desc)


def drop_long_labels(element: Element) -> Element:
    return element.with_labels(_drop_long(element.text), _drop_long(element.content_desc))


def mask_labels(element: Element) -> Element:
    return element.with_labels(mask_text(element.text), mask_text(element.content_desc))


ELEMENT_RULES: tuple[ElementRule, ...] = (
    drop_field_content,
    drop_long_labels,
    mask_labels,
)


def mask_element(element: Element) -> Element:
    for rule in ELEMENT_RULES:
        element = rule(element)
    return element
