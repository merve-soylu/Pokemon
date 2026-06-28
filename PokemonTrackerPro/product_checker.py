from bs4 import BeautifulSoup
from config import TARGET_KEYWORDS, BLOCKED_KEYWORDS, AVAILABILITY_KEYWORDS, STATUS_PRIORITY
from scraper import is_blocked_html, wait_for_challenge
from logger import log

def highest_status(availability):
    return max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])

def check_product_with_page(url, site, page):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        html = wait_for_challenge(page, site)

        if is_blocked_html(html):
            log("BLOCKED", f"Product blocked: {url}", site)
            return None

        soup = BeautifulSoup(page.content(), "html.parser")
        text = soup.get_text(" ", strip=True).lower()

        title = ""
        if soup.title:
            title = soup.title.get_text(" ", strip=True)

        if any(b in text for b in BLOCKED_KEYWORDS):
            return None

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

        return {
            "title": title,
            "url": url,
            "matches": matches,
            "availability": availability,
            "status": highest_status(availability),
            "booster_ok": booster_ok,
        }

    except Exception as e:
        log("ERROR", f"Product check failed: {e}", site)
        return None