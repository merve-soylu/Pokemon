import re
from bs4 import BeautifulSoup

from config import (
    TARGET_KEYWORDS,
    BLOCKED_KEYWORDS,
    AVAILABILITY_KEYWORDS,
    STATUS_PRIORITY,
)
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


def matched_phrases(text, keywords):
    return [keyword for keyword in keywords if phrase_match(text, keyword)]


def has_any_phrase(text, keywords):
    return len(matched_phrases(text, keywords)) > 0


def highest_status(availability):
    return max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])


def get_product_identity_text(soup, url):
    title = soup.title.get_text(" ", strip=True) if soup.title else url

    headings = " ".join(
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2"])
    )

    return title, f"{title} {headings}"


def get_product_area_text(soup):
    """
    Only search product/purchase-specific areas for availability.
    This avoids false statuses from recommended products, footers,
    menus, scripts, and unrelated page content.
    """
    selectors = [
        "h1",
        "h2",
        "button",
        "[role=button]",
        "form[action*=cart]",
        "form[action*=Cart]",
        "[class*=stock]",
        "[class*=Stock]",
        "[class*=availability]",
        "[class*=Availability]",
        "[class*=available]",
        "[class*=Available]",
        "[class*=purchase]",
        "[class*=Purchase]",
        "[class*=product-form]",
        "[class*=ProductForm]",
        "[class*=add-to-cart]",
        "[class*=AddToCart]",
        "[id*=stock]",
        "[id*=Stock]",
        "[id*=availability]",
        "[id*=Availability]",
        "[id*=product-form]",
        "[id*=ProductForm]",
        "[id*=add-to-cart]",
        "[id*=AddToCart]",
    ]

    parts = []

    for selector in selectors:
        for element in soup.select(selector):
            text = element.get_text(" ", strip=True)
            if text:
                parts.append(text)

            aria = element.get("aria-label")
            if aria:
                parts.append(aria)

            value = element.get("value")
            if value:
                parts.append(value)

            title = element.get("title")
            if title:
                parts.append(title)

    return " ".join(parts)


def extract_availability(soup):
    product_area_text = normalise(get_product_area_text(soup))

    availability = matched_phrases(product_area_text, AVAILABILITY_KEYWORDS)

    has_in_store_only = has_any_phrase(product_area_text, [
        "in-store only",
        "in store only",
        "instore only",
        "in-store",
        "in store",
        "click and collect",
        "collect in store",
    ])

    has_online_purchase = has_any_phrase(product_area_text, [
        "pre-order",
        "preorder",
        "pre order",
        "add to cart",
        "add to bag",
        "add to basket",
        "buy now",
        "order now",
        "in stock",
        "available now",
    ])

    if has_in_store_only and not has_online_purchase:
        return ["in-store only"]

    return availability


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
                "ignore_reason": "not pokemon related",
            }

        blocked_matches = matched_phrases(product_identity_lower, BLOCKED_KEYWORDS)

        if blocked_matches:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": f"blocked keyword in title/headings: {', '.join(blocked_matches)}",
            }

        matches = matched_phrases(full_text_lower, TARGET_KEYWORDS)
        availability = extract_availability(soup)

        booster_ok = has_any_phrase(product_identity_lower, VALID_PRODUCT_WORDS)

        if not booster_ok:
            booster_ok = has_any_phrase(full_text_lower, [
                "booster pack",
                "booster box",
                "mini tin",
                "tin"
            ])

        if not matches:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "no target keyword",
            }

        if not booster_ok:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "not booster/tcg/tin product",
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