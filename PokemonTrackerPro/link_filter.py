import re
from urllib.parse import unquote

from config import (
    TARGET_KEYWORDS,
    BLOCKED_KEYWORDS,
    POKEMON_RELATED_KEYWORDS,
    URL_BLOCKED_KEYWORDS,
    VALID_PRODUCT_WORDS,
)

def normalise(value):
    if not value:
        return ""

    value = unquote(str(value)).lower()
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = value.replace("%20", " ")

    return " ".join(value.split())

def phrase_match(text, phrase):
    phrase = normalise(phrase)
    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None

def has_any_phrase(text, keywords):
    return any(phrase_match(text, keyword) for keyword in keywords)

def classify_link_before_open(url, anchor_text=""):
    text = normalise(f"{url} {anchor_text}")

    if has_any_phrase(text, URL_BLOCKED_KEYWORDS) or has_any_phrase(text, BLOCKED_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "blocked keyword in url/title"
        }

    if not has_any_phrase(text, POKEMON_RELATED_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "not pokemon related from url/title"
        }

    if not has_any_phrase(text, TARGET_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "no target keyword in url/title"
        }
    
    if not has_any_phrase(text, VALID_PRODUCT_WORDS):
        return {
            "should_open": False,
            "ignore_reason": "no valid product type in url/title"
        }

    return {
        "should_open": True,
        "ignore_reason": None
    }