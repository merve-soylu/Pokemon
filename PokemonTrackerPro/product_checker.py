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
    "pokemon",
    "pokemon tcg",
    "pokemon-tcg",
    "trading card",
    "trading-card",
    "tin",
    "mini tin",
]

BUY_BOX_SELECTORS = [
    "[class*=productView]",
    "[class*=ProductView]",
    "[class*=product-detail]",
    "[class*=ProductDetail]",
    "[class*=product-info]",
    "[class*=ProductInfo]",
    "[class*=product-main]",
    "[class*=ProductMain]",
    "[class*=product-form]",
    "[class*=ProductForm]",
    "[class*=buy-box]",
    "[class*=BuyBox]",
    "[id*=product]",
    "[id*=Product]",
    "main",
]

PURCHASE_SELECTORS = [
    "button",
    "[role=button]",
    "input[type=submit]",
    "input[type=button]",
    "form[action*=cart]",
    "form[action*=Cart]",
    "[class*=stock]",
    "[class*=Stock]",
    "[id*=stock]",
    "[id*=Stock]",
    "[class*=availability]",
    "[class*=Availability]",
    "[id*=availability]",
    "[id*=Availability]",
    "[class*=add-to-cart]",
    "[class*=AddToCart]",
    "[id*=add-to-cart]",
    "[id*=AddToCart]",
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
    return bool(matched_phrases(text, keywords))


def highest_status(availability):
    return max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])


def get_product_identity_text(soup, url):
    title = soup.title.get_text(" ", strip=True) if soup.title else url

    headings = " ".join(
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2"])
    )

    return title, f"{title} {headings}"


def is_hidden_or_disabled(element):
    style = (element.get("style") or "").lower().replace(" ", "")
    classes = " ".join(element.get("class") or []).lower()

    if element.has_attr("hidden"):
        return True
    if element.has_attr("disabled"):
        return True
    if element.get("aria-hidden") == "true":
        return True
    if "display:none" in style:
        return True
    if "visibility:hidden" in style:
        return True
    if any(x in classes for x in ["hidden", "disabled", "is-disabled", "visually-hidden"]):
        return True

    return False


def extract_visible_text_from_element(element):
    parts = []

    text = element.get_text(" ", strip=True)
    if text:
        parts.append(text)

    for attr in [
        "aria-label",
        "value",
        "title",
        "data-button-text",
        "data-label",
        "data-testid",
        "name",
    ]:
        value = element.get(attr)
        if value:
            parts.append(value)

    return " ".join(parts)


def get_buy_box(soup):
    for selector in BUY_BOX_SELECTORS:
        element = soup.select_one(selector)
        if element:
            return element

    return soup


def get_purchase_area_texts(soup):
    buy_box = get_buy_box(soup)
    texts = []

    for selector in PURCHASE_SELECTORS:
        for element in buy_box.select(selector):
            if is_hidden_or_disabled(element):
                continue

            text = extract_visible_text_from_element(element)
            if text:
                texts.append(text)

    if not texts:
        fallback = buy_box.get_text(" ", strip=True)
        if fallback and len(fallback) < 2500:
            texts.append(fallback)

    seen = set()
    unique = []

    for text in texts:
        cleaned = normalise(text)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)

    return unique


def extract_availability(soup):
    purchase_texts = get_purchase_area_texts(soup)
    purchase_blob = " ".join(purchase_texts)

    found = matched_phrases(purchase_blob, AVAILABILITY_KEYWORDS)

    if not found:
        return []

    online_purchase_statuses = [
        "in stock",
        "buy now",
        "order now",
        "add to cart",
        "add to bag",
        "add to basket",
        "pre-order",
        "preorder",
        "pre order",
        "available now",
    ]

    unavailable_statuses = [
        "out of stock",
        "sold out",
        "notify me",
    ]

    offline_only_statuses = [
        "in-store only",
        "in store only",
        "instore only",
        "click and collect",
        "collect in store",
    ]

    online_found = [s for s in found if s in online_purchase_statuses]
    unavailable_found = [s for s in found if s in unavailable_statuses]
    offline_found = [s for s in found if s in offline_only_statuses]

    if online_found:
        return [max(online_found, key=lambda x: STATUS_PRIORITY.get(x, -1))]

    if unavailable_found:
        return [max(unavailable_found, key=lambda x: STATUS_PRIORITY.get(x, -1))]

    if offline_found:
        return [max(offline_found, key=lambda x: STATUS_PRIORITY.get(x, -1))]

    return [max(found, key=lambda x: STATUS_PRIORITY.get(x, -1))]


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
        return parse_product_soup(url, site, soup)

    except Exception as e:
        log("ERROR", f"Product check failed: {e}", site)
        return None


def parse_product_soup(url, site, soup):
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
        booster_ok = has_any_phrase(full_text_lower, VALID_PRODUCT_WORDS)

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