import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
from urllib.parse import urlsplit, urlunsplit, urljoin

# =========================
# CONFIG
# =========================

DISCORD_WEBHOOK = "YOUR_WEBHOOK_HERE"
STATE_FILE = "state.json"

SITES = [
    {
        "name": "Pokemon Center",
        "url": "https://www.pokemoncenter.com/en-au/category/tcg-cards",
        "js": False
    },
    {
        "name": "Gameology",
        "url": "https://www.gameology.com.au/collections/pokemon",
        "js": False
    },
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "js": True
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "js": True
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon/",
        "js": True
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/c/education/educational-toys--puzzles-games/kids-educational-toys-games",
        "js": True
    }
]

TARGET_KEYWORDS = [
    "ascended heroes", "sv11a",
    "pitch black", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces", "pitch-black",
    "ascended-heroes"
]

# Only used AFTER product page is detected
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
# STATE (TRACK ALL PRODUCTS)
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
        json={"content": "✅ Pokémon Product Tracker ONLINE (Delta Mode)"},
        timeout=10
    )

def send_alert(site, url, targets, availability):
    embed = {
        "title": "🚨 NEW POKÉMON PRODUCT DETECTED",
        "description": f"**{site}** new product listing found",
        "color": 16711680,
        "fields": [
            {"name": "Product URL", "value": url[:1024]},
            {"name": "Matches", "value": ", ".join(targets) or "None"},
            {"name": "Status Signals", "value": ", ".join(availability) or "None"},
            {"name": "Time", "value": str(datetime.now())}
        ]
    }

    requests.post(
        DISCORD_WEBHOOK,
        json={"embeds": [embed]},
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
# PRODUCT LINK EXTRACTION (CORE FIX)
# =========================

def extract_product_links(soup, base_url):
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        full_url = urljoin(base_url, href)

        # STRICT FILTER: only real product pages
        if "/product" in full_url or "/products/" in full_url:
            links.add(full_url.split("?")[0].rstrip("/"))

    return links

# =========================
# PRODUCT CHECK
# =========================

def check_product_page(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()

        text = r.text.lower()

        matches = [k for k in TARGET_KEYWORDS if k in text]
        availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

        return matches, availability

    except:
        return [], []

# =========================
# MAIN LOGIC
# =========================

def main():

    known_products = load_state()
    updated = False

    for site in SITES:

        try:
            if site["js"]:
                html, soup = scrape_js(site["url"])
            else:
                html, soup = scrape_static(site["url"])

            new_product_links = extract_product_links(soup, site["url"])

            for product_url in new_product_links:

                key = f"{site['name']}::{product_url}"

                # ONLY NEW PRODUCTS
                if key in known_products:
                    continue

                # Now inspect product page
                targets, availability = check_product_page(product_url)

                # Only alert if relevant Pokémon set exists
                if targets:

                    send_alert(
                        site["name"],
                        product_url,
                        targets,
                        availability
                    )

                    print(f"[{datetime.now()}] NEW DROP: {product_url}")

                known_products.add(key)
                updated = True

        except Exception as e:
            print(f"{site['name']} error: {e}")

    if updated:
        save_state(known_products)

# =========================
# STARTUP
# =========================

if __name__ == "__main__":
    discord_ping_startup()
    main()