import re
from bs4 import BeautifulSoup

from config import TARGET_KEYWORDS, BLOCKED_KEYWORDS, AVAILABILITY_KEYWORDS, STATUS_PRIORITY
from scraper import is_blocked_html, wait_for_challenge, human_pause
from logger import log


VALID_PRODUCT_WORDS = [
    "booster",
    "booster pack",
    "booster box",
    "blister",
    "bundle",
    "box",
    "tin",
    "mini tin",
    "tcg",
    "trading card",
    "elite trainer",
    "etb",
]


def normalise(value):
    if not value:
        return ""

    value = str(value).lower()
    value = value.replace("-", " ")
    value = value.replace("_", " ")
    value = value.replace("%20", " ")

    return " ".join(value.split())


def phrase_match(text, phrase):
    text = normalise(text)
    phrase = normalise(phrase)

    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def has_any_phrase(text, keywords):
    return any(phrase_match(text, keyword) for keyword in keywords)


def matched_phrases(text, keywords):
    return [keyword for keyword in keywords if phrase_match(text, keyword)]


def highest_status(availability):
    return max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])


def get_product_identity_text(soup, url):
    title = soup.title.get_text(" ", strip=True) if soup.title else url

    headings = " ".join(
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2"])
    )

    return title, f"{title} {headings}"


def check_product_with_page(url, site, page):
    try:
        human_pause(page, 800, 2200)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        human_pause(page, 2500, 4500)

        html = wait_for_challenge(page, site, max_rounds=8)

        if is_blocked_html(html):
            log("BLOCKED", f"Product blocked: {url}", site)
            return None

        soup = BeautifulSoup(page.content(), "html.parser")

        full_text = soup.get_text(" ", strip=True)
        full_text_lower = normalise(full_text)

        title, product_identity_text = get_product_identity_text(soup, url)
        product_identity_lower = normalise(product_identity_text)

        if not has_any_phrase(full_text_lower, ["pokemon", "pokémon"]):
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "not pokemon related"
            }

        # IMPORTANT:
        # Blocked keywords are ONLY checked against title/headings,
        # not the whole page body. The body often contains recommendations like sleeves/binders.
        blocked_matches = matched_phrases(product_identity_lower, BLOCKED_KEYWORDS)

        if blocked_matches:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": f"blocked keyword in title/headings: {', '.join(blocked_matches)}"
            }

        matches = matched_phrases(full_text_lower, TARGET_KEYWORDS)
        availability = matched_phrases(full_text_lower, AVAILABILITY_KEYWORDS)

        booster_ok = has_any_phrase(product_identity_lower, VALID_PRODUCT_WORDS)

        # fallback: sometimes title is weak but the page has product text clearly saying TCG/tin/booster
        if not booster_ok:
            booster_ok = has_any_phrase(full_text_lower, [
                "booster pack",
                "booster box",
                "mini tin",
                "pokemon tcg",
                "trading card game",
            ])

        if not matches:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "no target keyword"
            }

        if not booster_ok:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "not booster/tcg/tin product"
            }

        return {
            "title": title,
            "url": url,
            "ignored": False,
            "matches": matches,
            "availability": availability,
            "status": highest_status(availability),
            "booster_ok": booster_ok,
        }

    except Exception as e:
        log("ERROR", f"Product check failed: {e}", site)
        return None