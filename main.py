import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import os
import time
import random
from urllib.parse import urljoin
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
STATE_FILE = "state.json"

POLL_INTERVAL = 75  # slower = fewer blocks

SITES = [
    {
        "name": "Toymate",
        "url": "https://toymate.com.au/pokemon/?_bc_fsnf=1&Product+Category=Trading+Cards",
        "allowed_prefix": "https://toymate.com.au",
        "js": True
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
        "js": True
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/c/education/educational-toys--puzzles-games/kids-educational-toys-games",
        "allowed_prefix": "https://www.officeworks.com.au",
        "js": True
    },
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "allowed_prefix": "https://www.jbhifi.com.au",
        "js": True
    },
]

TARGET_KEYWORDS = [
    "ascended heroes", "ascended hero", "sv11a", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces",
]

BLOCKED_KEYWORDS = [
    "binder", "sleeves", "playmat",
    "deck box", "album", "case", "book"
]

AVAILABILITY_KEYWORDS = [
    "pre-order", "preorder", "pre order",
    "available now", "coming soon",
    "notify me",
    "add to cart",
    "add to basket",
    "buy now",
    "in stock",
    "order now",
    "add to bag",
    "reserve now"
]

STATUS_PRIORITY = {
    "notify me": 0,
    "coming soon": 1,
    "available now": 2,
    "pre order": 3,
    "pre-order": 3,
    "preorder": 3,
    "reserve now": 3,
    "add to cart": 4,
    "add to basket": 4,
    "add to bag": 4,
    "buy now": 5,
    "order now": 5,
    "in stock": 6
}

# =========================
# LOGGING
# =========================

def log(level, msg, site=None):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{level}] [{site}] {msg}" if site else f"[{now}] [{level}] {msg}")

# =========================
# STATE
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)

        cleaned = {}
        for k, v in data.items():
            if isinstance(v, dict):
                cleaned[k] = {
                    "status": v.get("status", -1),
                    "availability": v.get("availability", []),
                    "matches": v.get("matches", [])
                }
        return cleaned

    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# =========================
# DISCORD
# =========================

def send_alert(site, url, targets, availability):
    try:
        embed = {
            "title": "🚨 PRODUCT DETECTED",
            "description": f"{site} product found",
            "fields": [
                {"name": "URL", "value": url[:1000]},
                {"name": "Matches", "value": ", ".join(targets) or "None"},
                {"name": "Status", "value": ", ".join(availability) or "None"},
            ]
        }

        requests.post(DISCORD_WEBHOOK, json={"content": "@everyone", "embeds": [embed]}, timeout=10)
    except:
        pass

# =========================
# SCRAPING
# =========================

def scrape_static(url, site):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        return BeautifulSoup(r.text, "html.parser")
    except:
        return BeautifulSoup("", "html.parser")


def scrape_js(url, site, context):
    log("SCRAPE", f"JS render {url}", site)

    page = context.new_page()

    html = ""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # STEP 1: give initial JS challenge time
        page.wait_for_timeout(3000)

        # STEP 2: WAIT FOR EITHER REDIRECT OR STABILITY
        for _ in range(6):  # ~30 seconds max wait loop
            html = page.content().lower()

            # If we reached real content, break early
            if "product" in html or "add to cart" in html or "in stock" in html:
                break

            # If still on challenge page, wait a bit more
            if any(x in html for x in [
                "just a moment",
                "checking your browser",
                "cf-browser-verification",
                "attention required"
            ]):
                log("WAIT", "Bot check still resolving...", site)
                page.wait_for_timeout(5000)

            else:
                # page changed, likely redirected
                break

        # STEP 3: final scroll (after redirect likely completed)
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        html = page.content()

    except Exception as e:
        log("ERROR", f"goto failed: {e}", site)

    finally:
        page.close()

    if not html:
        return BeautifulSoup("", "html.parser")

    lower = html.lower()

    if any(x in lower for x in [
        "just a moment",
        "checking your browser",
        "cf-browser-verification"
    ]):
        log("BLOCKED", "Still on verification page after wait", site)
        return BeautifulSoup("", "html.parser")

    return BeautifulSoup(html, "html.parser")

# =========================
# PRODUCT EXTRACTION
# =========================

def extract_product_links(soup, base_url, allowed_prefix, site):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href for x in ["/product", "/products", "/p/", "/search", "pokemon", "tcg"]):
            links.add(href)

    return links

# =========================
# PRODUCT CHECK
# =========================

cache = {}

def check_product(url):
    if url in cache:
        return cache[url]

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    except:
        return [], [], False

    soup = BeautifulSoup(r.text, "html.parser")

    text = soup.get_text(" ", strip=True).lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        cache[url] = ([], [], False)
        return cache[url]

    matches = [k for k in TARGET_KEYWORDS if k in text]
    availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

    booster_ok = any(x in text for x in ["booster", "tcg", "booster pack", "tin"])

    cache[url] = (matches, availability, booster_ok)
    return cache[url]

# =========================
# MAIN LOOP
# =========================

def run_cycle(state, page):

    for site in SITES:

        name = site["name"]

        soup = scrape_js(site["url"], name, page) if site["js"] else scrape_static(site["url"], name)

        if not soup.find_all("a"):
            log("WARN", "Empty or blocked page", name)
            continue

        links = extract_product_links(soup, site["url"], site["allowed_prefix"], name)

        for url in links:

            key = f"{name}::{url}"

            matches, availability, ok = check_product(url)

            status = max([STATUS_PRIORITY.get(x, -1) for x in availability] + [-1])

            old = state.get(key)

            if old is None or status > old.get("status", -1):

                state[key] = {
                    "status": status,
                    "availability": availability,
                    "matches": matches
                }

                if matches and ok:
                    send_alert(name, url, matches, availability)

        time.sleep(random.uniform(2, 5))  # prevents aggressive bursts

    save_state(state)

# =========================
# MAIN
# =========================

def main():

    state = load_state()

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
            viewport={"width": 1280, "height": 720}
        )

        page = context.new_page()

        while True:
            start = time.time()

            run_cycle(state, page)

            sleep_time = max(10, POLL_INTERVAL - (time.time() - start))
            time.sleep(sleep_time + random.uniform(0, 5))

if __name__ == "__main__":
    main()