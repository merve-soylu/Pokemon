import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import time
from urllib.parse import urljoin

# =========================
# CONFIG
# =========================

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1519121141862760628/3yxReFPKTxZ4xhMmhSRGQsJaVdab0n8yKsV3l1DVdvryH6GrTnLUCfzYXedh4nLFJiph"
STATE_FILE = "state.json"

POLL_INTERVAL = 30

SITES = [
    {
        "name": "Pokemon Center",
        "url": "https://www.pokemoncenter.com/en-au/category/tcg-cards",
        "allowed_prefix": "https://www.pokemoncenter.com/en-au",
        "js": False
    },
    {
        "name": "Gameology",
        "url": "https://www.gameology.com.au/collections/pokemon",
        "allowed_prefix": "https://www.gameology.com.au",
        "js": False
    },
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "allowed_prefix": "https://www.jbhifi.com.au",
        "js": True
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
        "js": True
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon/",
        "allowed_prefix": "https://www.kmart.com.au/category/toys/pokemon",
        "js": True
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/c/education/educational-toys--puzzles-games/kids-educational-toys-games",
        "allowed_prefix": "https://www.officeworks.com.au",
        "js": True
    }
]

TARGET_KEYWORDS = [
    "ascended heroes", "sv11a",
    "pitch black", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces", "mega evolution",
]

AVAILABILITY_KEYWORDS = [
    "pre-order", "preorder",
    "available now", "coming soon",
    "notify me",
    "add to cart",
    "buy now",
    "in stock",
    "order now",
    "reserve now"
]

# =========================
# STATE
# =========================

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(state)), f, indent=2)

# =========================
# DISCORD
# =========================

def discord_ping_startup():
    requests.post(
        DISCORD_WEBHOOK,
        json={"content": "🟢 Pokémon tracker ONLINE"},
        timeout=10
    )

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
    embed = {
        "title": "🚨 NEW POKÉMON PRODUCT DETECTED",
        "description": f"**{site}** new Pokémon product found",
        "color": 16711680,
        "fields": [
            {"name": "Product URL", "value": url[:1024]},
            {"name": "Matches", "value": ", ".join(targets) or "None"},
            {"name": "Status", "value": ", ".join(availability) or "None"},
            {"name": "Time", "value": str(datetime.now())}
        ]
    }

    requests.post(
        DISCORD_WEBHOOK,
        json={"content": "@everyone 🚨 NEW POKÉMON PRODUCT DETECTED", "embeds": [embed]},
        timeout=10
    )

# =========================
# SCRAPERS
# =========================

def scrape_static(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    return r.text, BeautifulSoup(r.text, "html.parser")

def scrape_js(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        html = page.content()
        browser.close()

    return html, BeautifulSoup(html, "html.parser")

# =========================
# PRODUCT EXTRACTION
# =========================

def extract_product_links(soup, base_url, allowed_prefix):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if "/product" in href or "/products/" in href or "/p/" in href:
            links.add(href)

    return links

# =========================
# PRODUCT CHECK (BOOSTER FILTER ADDED)
# =========================

def check_product_page(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()

        text = r.text.lower()

        matches = [k for k in TARGET_KEYWORDS if k in text]
        availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

        # 🔥 NEW BOOSTER FILTER
        booster_ok = "booster" in text

        return matches, availability, booster_ok

    except:
        return [], [], False

# =========================
# ONE FULL SCAN CYCLE
# =========================

def run_cycle(known_products):

    updated = False

    for site in SITES:

        try:
            if site["js"]:
                html, soup = scrape_js(site["url"])
            else:
                html, soup = scrape_static(site["url"])

            new_links = extract_product_links(
                soup,
                site["url"],
                site["allowed_prefix"]
            )

            for product_url in new_links:

                key = f"{site['name']}::{product_url}"

                if key in known_products:
                    continue

                matches, availability, booster_ok = check_product_page(product_url)

                # 🔥 ONLY ALERT IF:
                # - Pokémon match exists
                # - AND product contains "booster"
                if matches and booster_ok:

                    send_alert(site["name"], product_url, matches, availability)
                    print(f"[{datetime.now()}] BOOSTER DROP: {product_url}")

                known_products.add(key)
                updated = True

        except Exception as e:
            send_crash(f"{site['name']} error: {e}")
            print(f"{site['name']} error: {e}")

    if updated:
        save_state(known_products)

# =========================
# MAIN LOOP (REAL TIME)
# =========================

def main():

    known_products = load_state()

    discord_ping_startup()

    print("🟢 Pokémon tracker running...")

    while True:

        start = time.time()

        try:
            run_cycle(known_products)

        except Exception as e:
            send_crash(str(e))

        elapsed = time.time() - start
        sleep_time = max(5, POLL_INTERVAL - elapsed)

        time.sleep(sleep_time)

# =========================
# START
# =========================

if __name__ == "__main__":
    main()