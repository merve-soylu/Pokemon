import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import os
import time
from urllib.parse import urljoin
from dotenv import load_dotenv

# =========================
# CONFIG
# =========================

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
STATE_FILE = "state.json"

POLL_INTERVAL = 30

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
    if site:
        print(f"[{now}] [{level}] [{site}] {msg}")
    else:
        print(f"[{now}] [{level}] {msg}")

# =========================
# STATE (FIXED + SANITISED)
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)

        cleaned = {}

        for k, v in data.items():
            if not isinstance(v, dict):
                continue

            cleaned[k] = {
                "status": v.get("status", -1),
                "availability": v.get("availability", []),
                "matches": v.get("matches", [])
            }

        return cleaned

    except Exception as e:
        print("STATE LOAD ERROR:", e)
        return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# =========================
# DISCORD
# =========================

def discord_ping_startup():
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": "🟢 Pokémon tracker ONLINE"}, timeout=10)
    except:
        pass


def send_crash(message):
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": f"❌ Pokémon tracker CRASHED:\n```{message}```"},
            timeout=10
        )
    except:
        pass


def send_alert(site, url, targets, availability):
    log("ALERT", "Sending Discord alert", site)

    embed = {
        "title": "🚨 NEW POKéMON PRODUCT DETECTED",
        "description": f"**{site}** Pokémon booster product found",
        "color": 16711680,
        "fields": [
            {"name": "Product URL", "value": url[:1024]},
            {"name": "Matches", "value": ", ".join(targets) or "None"},
            {"name": "Status", "value": ", ".join(availability) or "None"},
            {"name": "Time", "value": str(datetime.now())}
        ]
    }

    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": "@everyone 🚨 BOOSTER DROP DETECTED", "embeds": [embed]},
            timeout=10
        )
    except:
        pass

# =========================
# SCRAPERS
# =========================

def scrape_static(url, site):
    log("SCRAPE", url, site)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    return soup


def scrape_js(url, site):
    log("SCRAPE", f"JS render {url}", site)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
        except Exception as e:
            log("ERROR", f"goto failed: {e}", site)
            browser.close()
            raise

        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        html = page.content()
        browser.close()

    return BeautifulSoup(html, "html.parser")

# =========================
# PRODUCT EXTRACTION
# =========================

def extract_product_links(soup, base_url, allowed_prefix, site):
    links = set()

    for a in soup.find_all("a", href=True):
        href_raw = a.get("href")
        if not href_raw:
            continue

        href = urljoin(base_url, href_raw).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href for x in [
            "/product", "/products", "/p/",
            "/c/", "/search", "/item",
            "pokemon", "trading", "tcg"
        ]):
            links.add(href)

    log("FOUND", f"{len(links)} product links", site)
    return links


def highest_status(statuses):
    return max([STATUS_PRIORITY.get(s, -1) for s in statuses] + [-1])

# =========================
# PRODUCT CHECK (FIXED URL SAFETY)
# =========================

product_cache = {}

def check_product_page(url, site):
    if not url or not isinstance(url, str):
        log("ERROR", f"Invalid URL skipped: {url}", site)
        return [], [], False

    if url in product_cache:
        return product_cache[url]

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    except Exception as e:
        log("ERROR", f"request failed: {e}", site)
        return [], [], False

    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    headings = " ".join(h.get_text(" ", strip=True).lower()
                        for h in soup.find_all(["h1", "h2"]))
    body = soup.get_text(" ", strip=True).lower()

    combined = f"{title} {headings} {body}"

    if any(b in combined for b in BLOCKED_KEYWORDS):
        product_cache[url] = ([], [], False)
        return [], [], False

    matches = [k for k in TARGET_KEYWORDS if k in combined]
    availability = [k for k in AVAILABILITY_KEYWORDS if k in combined]

    booster_ok = any(x in combined for x in [
        "booster", "booster pack", "booster box", "tcg", "trading card", "tin"
    ])

    product_cache[url] = (matches, availability, booster_ok)

    return matches, availability, booster_ok

# =========================
# MAIN LOOP
# =========================

def run_cycle(known_products):

    log("SYSTEM", "Starting scan cycle")

    for site in SITES:

        name = site["name"]

        try:
            soup = scrape_static(site["url"], name) if not site["js"] else scrape_js(site["url"], name)

            links = extract_product_links(
                soup,
                site["url"],
                site["allowed_prefix"],
                name
            )

            for url in links:

                if not url:
                    continue

                key = f"{name}::{url}"

                matches, availability, booster_ok = check_product_page(url, name)

                old = known_products.get(key)
                current_status = highest_status(availability)

                if old is None:
                    known_products[key] = {
                        "status": current_status,
                        "availability": availability,
                        "matches": matches
                    }

                    if matches and booster_ok:
                        send_alert(name, url, matches, availability)

                else:
                    old_status = old.get("status", -1)

                    if current_status > old_status:
                        known_products[key]["status"] = current_status
                        known_products[key]["availability"] = availability
                        known_products[key]["matches"] = matches

                        if matches and booster_ok:
                            send_alert(name, url, matches, availability)

        except Exception as e:
            log("ERROR", str(e), name)
            send_crash(f"{name} error: {e}")

    save_state(known_products)
    log("STATE", f"Saved {len(known_products)} products")

# =========================
# MAIN
# =========================

def main():

    known_products = load_state()

    discord_ping_startup()
    log("SYSTEM", "🟢 Tracker running")

    while True:
        start = time.time()

        try:
            run_cycle(known_products)
        except Exception as e:
            send_crash(str(e))
            log("FATAL", str(e))

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))


if __name__ == "__main__":
    main()
