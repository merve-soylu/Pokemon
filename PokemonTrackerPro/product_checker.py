from bs4 import BeautifulSoup
from config import TARGET_KEYWORDS, BLOCKED_KEYWORDS, AVAILABILITY_KEYWORDS, STATUS_PRIORITY
from scraper import is_blocked_html, wait_for_challenge, human_pause
from logger import log

def highest_status(availability):
    return max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])

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
        text = soup.get_text(" ", strip=True).lower()

        title = soup.title.get_text(" ", strip=True) if soup.title else url

        if "pokemon" not in text and "pokémon" not in text:
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "not pokemon related"
            }

        if any(b in text for b in BLOCKED_KEYWORDS):
            return {
                "title": title,
                "url": url,
                "ignored": True,
                "ignore_reason": "blocked keyword"
            }

        matches = [k for k in TARGET_KEYWORDS if k in text]
        availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

        booster_ok = any(x in text for x in [
            "booster",
            "booster pack",
            "booster box",
            "tcg",
            "trading card",
            "tin"
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
                "ignore_reason": "not booster/tcg product"
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