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
SESSION_FILE = "session.json"

POLL_INTERVAL = 75

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
    "in stock",
    "buy now",
    "order now"
]

STATUS_PRIORITY = {
    "notify me": 0,
    "coming soon": 1,
    "available now": 2,
    "pre order": 3,
    "pre-order": 3,
    "preorder": 3,
    "add to cart": 4,
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
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# =========================
# SESSION STORAGE
# =========================

def load_session():
    if os.path.exists(SESSION_FILE):
        return SESSION_FILE
    return None

def save_session(context):
    try:
        context.storage_state(path=SESSION_FILE)
    except Exception as e:
        log("ERROR", f"Failed saving session: {e}")

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

        requests.post(
            DISCORD_WEBHOOK,
            json={"content": "@everyone", "embeds": [embed]},
            timeout=10
        )
    except:
        pass

# =========================
# SCRAPING
# =========================

def scrape_js(url, site, context):
    log("SCRAPE", url, site)

    page = context.new_page()
    html = ""

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # give time for bot challenge redirect
        page.wait_for_timeout(6000)

        # wait loop for real content
        for _ in range(6):
            html = page.content().lower()

            if any(x in html for x in ["add to cart", "in stock", "product"]):
                break

            if any(x in html for x in ["just a moment", "checking your browser"]):
                log("WAIT", "Bot check still running...", site)
                page.wait_for_timeout(5000)
            else:
                break

        # mimic user scroll
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        html = page.content()

    except Exception as e:
        log("ERROR", str(e), site)

    finally:
        page.close()

    return BeautifulSoup(html or "", "html.parser")

# =========================
# PRODUCT PARSING
# =========================

def extract_links(soup, base_url, allowed_prefix):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href for x in ["/product", "/products", "/p/", "pokemon", "tcg"]):
            links.add(href)

    return links

def check_product(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    except:
        return [], [], False

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True).lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        return [], [], False

    matches = [k for k in TARGET_KEYWORDS if k in text]
    availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

    booster_ok = any(x in text for x in ["booster", "tcg", "tin"])

    return matches, availability, booster_ok

# =========================
# MAIN CYCLE
# =========================

def run_cycle(state, context):

    for site in SITES:

        name = site["name"]

        soup = scrape_js(site["url"], name, context)

        if not soup.find_all("a"):
            log("WARN", "Empty or blocked page", name)
            continue

        links = extract_links(soup, site["url"], site["allowed_prefix"])

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

        time.sleep(random.uniform(2, 4))

    save_state(state)

# =========================
# MAIN
# =========================

def main():

    state = load_state()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False,  # IMPORTANT
            slow_mo=50
        )

        context = browser.new_context(
            storage_state=load_session(),  # <-- SESSION REUSE
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
            locale="en-AU"
        )

        log("SYSTEM", "Tracker running (persistent session + visible browser)")

        try:
            while True:
                start = time.time()

                run_cycle(state, context)

                save_session(context)  # <-- SAVE COOKIES EVERY LOOP

                sleep_time = max(10, POLL_INTERVAL - (time.time() - start))
                time.sleep(sleep_time + random.uniform(0, 3))

        finally:
            save_session(context)
            browser.close()

if __name__ == "__main__":
    main()