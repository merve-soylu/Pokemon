from urllib.parse import unquote

from config import (
    TARGET_KEYWORDS,
    BLOCKED_KEYWORDS,
    POKEMON_RELATED_KEYWORDS,
    URL_BLOCKED_KEYWORDS,
)

def normalise(value):
    if not value:
        return ""

    value = unquote(str(value))
    value = value.lower()
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = value.replace("%20", " ")

    return " ".join(value.split())

def combined_text(url, anchor_text=""):
    return normalise(f"{url} {anchor_text}")

def has_any(text, keywords):
    return any(k.lower() in text for k in keywords)

def classify_link_before_open(url, anchor_text=""):
    text = combined_text(url, anchor_text)

    if has_any(text, URL_BLOCKED_KEYWORDS) or has_any(text, BLOCKED_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "blocked keyword in url/title"
        }

    if not has_any(text, POKEMON_RELATED_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "not pokemon related from url/title"
        }

    if not has_any(text, TARGET_KEYWORDS):
        return {
            "should_open": False,
            "ignore_reason": "no target keyword in url/title"
        }

    return {
        "should_open": True,
        "ignore_reason": None
    }