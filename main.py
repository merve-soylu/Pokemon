import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import time
import hashlib
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
        "name": "Pokemon Center",
        "url": "https://www.pokemoncenter.com/en-au/category/booster-packs",
        "allowed_prefix": "https://www.pokemoncenter.com/en-au",
        "js": False
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon-trading-cards/",
        "allowed_prefix": "https://www.kmart.com.au",
        "js": True
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/c/education/educational-toys--puzzles-games/kids-educational-toys-games",
        "allowed_prefix": "https://www.officeworks.com.au/",
        "js": True
    },
    {
        "name": "Target",
        "url": "https://www.target.com.au/c/toys/trading-card-games/pokemon-cards/W1852642",
        "allowed_prefix": "https://www.target.com.au/",
        "js": True
    },
    {
        "name": "Gameology",
        "url": "https://www.gameology.com.au/collections/pokemon",
        "allowed_prefix": "https://www.gameology.com.au",
        "js": False
    }
]

TARGET_KEYWORDS = [
    "sv11a", "sv11b",
    "ascended heroes",
    "30th anniversary",
    "30th collection",
    "mega forces"
]

BLOCKED_KEYWORDS = [
    "binder", "sleeves", "playmat",
    "deck box", "album", "case", "book"
]

AVAILABILITY_KEYWORDS = [
    "pre-order", "preorder", "coming soon",
    "add to cart", "add to bag", "add to basket",
    "in stock", "sold out", "wishlist"
]

# =========================
# LOGGING (ADDED)
# =========================

def log(level, msg, site=None):
    now = datetime.now().strftime("%H:%M:%S")

    if site:
        print(f"[{now}] [{level}] [{site}] {msg}")
    else:
        print(f"[{now}] [{level}] {msg}")

# =========================
# STATE
# =========================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

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
        "title": "🚨 Pokémon Drop Radar",
        "description": f"**{site}**",
        "color": 16711680,
        "fields": [
            {"name": "Product", "value": url[:1024]},
            {"name": "Matches", "value": ", ".join(targets) or "None"},
            {"name": "Time", "value": str(datetime.now())}
        ]
    }

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": "@everyone 🚨 DROP / UPDATE DETECTED",
            "embeds": [embed]
        },
        timeout=10
    )

# =========================
# SCRAPERS
# =========================

def scrape_static(url):
    log("SCRAPE", f"GET {url}")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    r.raise_for_status()
    return r.text, BeautifulSoup(r.text, "html.parser")

def scrape_js(url):
    log("SCRAPE", f"JS GET {url}")
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

def is_blocked(text):
    text = text.lower()
    return any(b in text for b in BLOCKED_KEYWORDS)

# =========================
# PRODUCT CHECK
# =========================

def check_product_page(url):
    try:
        log("CHECK", url)

        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        headings = " ".join(
            h.get_text(" ", strip=True).lower()
            for h in soup.find_all(["h1", "h2"])
        )
        body_text = soup.get_text(" ", strip=True).lower()

        combined = f"{title} {headings} {body_text}"

        if is_blocked(combined):
            log("BLOCKED", url)
            return [], [], False

        matches = [k for k in TARGET_KEYWORDS if k in combined]
        booster_ok = "booster" in combined

        return matches, [], booster_ok

    except Exception as e:
        log("ERROR", f"{url} -> {e}")
        return [], [], False

# =========================
# MAIN LOOP
# =========================

def run_cycle(known_products):

    updated = False
    log("SYSTEM", "Starting scan cycle")

    for site in SITES:

        log("SITE", f"Scraping {site['name']}", site["name"])

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

            log("FOUND", f"{len(new_links)} product links", site["name"])

            for product_url in new_links:

                matches, _, booster_ok = check_product_page(product_url)

                if not matches or not booster_ok:
                    log("SKIP", product_url, site["name"])
                    continue

                key = f"{site['name']}::{product_url}"

                r = requests.get(product_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
                soup = BeautifulSoup(r.text, "html.parser")

                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                body = soup.get_text(" ", strip=True)
                combined = f"{title} {body}".lower()

                new_hash = hashlib.sha256(combined.encode()).hexdigest()

                if key not in known_products:
                    known_products[key] = new_hash

                    log("NEW", product_url, site["name"])
                    send_alert(site["name"], product_url, matches, [])
                    updated = True
                    continue

                old_hash = known_products[key]

                if old_hash != new_hash:
                    known_products[key] = new_hash

                    log("UPDATE", product_url, site["name"])
                    send_alert(site["name"], product_url, matches, [])
                    updated = True

        except Exception as e:
            send_crash(f"{site['name']} error: {e}")
            log("CRASH", f"{site['name']} -> {e}")

    if updated:
        save_state(known_products)
        log("STATE", f"Saved ({len(known_products)} products)")

# =========================
# MAIN
# =========================

def main():

    known_products = load_state()

    discord_ping_startup()

    log("SYSTEM", "🟢 Pokémon tracker running")

    while True:

        start = time.time()

        try:
            run_cycle(known_products)

        except Exception as e:
            send_crash(str(e))
            log("FATAL", str(e))

        elapsed = time.time() - start
        time.sleep(max(5, POLL_INTERVAL - elapsed))

if __name__ == "__main__":
    main()