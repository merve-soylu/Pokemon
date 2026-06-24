import requests
from bs4 import BeautifulSoup
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
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "allowed_prefix": "https://www.jbhifi.com.au",
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
    },
    {
        "name": "Pokemon Center",
        "url": "https://www.pokemoncenter.com/en-au/category/booster-packs",
        "allowed_prefix": "https://www.pokemoncenter.com/en-au",
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon-trading-cards/",
        "allowed_prefix": "https://www.kmart.com.au",
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/c/education/educational-toys--puzzles-games/kids-educational-toys-games",
        "allowed_prefix": "https://www.officeworks.com.au",
    },
    {
        "name": "Target",
        "url": "https://www.target.com.au/c/toys/trading-card-games/pokemon-cards/W1852642",
        "allowed_prefix": "https://www.target.com.au",
    },
    {
        "name": "Gameology",
        "url": "https://www.gameology.com.au/collections/pokemon",
        "allowed_prefix": "https://www.gameology.com.au",
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
# STATE
# =========================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)

            cleaned = {}
            for k in data.keys():
                if isinstance(k, str):
                    cleaned[k] = True

            log("STATE", f"Loaded {len(cleaned)} seen products")
            return cleaned

        except Exception as e:
            log("ERROR", f"State load failed: {e}")
            return {}

    log("STATE", "No existing state file found")
    return {}

def save_state(state):
    safe_state = {str(k): True for k in state.keys()}

    with open(STATE_FILE, "w") as f:
        json.dump(safe_state, f, indent=2)

    log("STATE", f"Saved {len(safe_state)} products")

# =========================
# DISCORD
# =========================

def send_alert(site, url, matches):
    log("ALERT", f"Sending Discord alert for {url}", site)

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": "@everyone 🚨 NEW PRODUCT",
            "embeds": [{
                "title": site,
                "description": url,
                "fields": [
                    {"name": "Matches", "value": ", ".join(matches)}
                ]
            }]
        },
        timeout=10
    )

# =========================
# SCRAPE CATEGORY
# =========================

def scrape(url, site_name):
    log("SCRAPE", url, site_name)

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    log("SCRAPE", f"Found {len(soup.find_all('a'))} links", site_name)
    return soup

def extract_links(soup, base_url, allowed_prefix, site_name):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href for x in [
            "/product", "/products", "/p/", "/c/",
            "/collections", "/featured", "/category"
        ]):
            links.add(href)

    log("FOUND", f"{len(links)} product links", site_name)
    return links

# =========================
# PRODUCT CHECK
# =========================

product_cache = {}

def check_product(url, site_name):
    if url in product_cache:
        return product_cache[url]

    log("CHECK", url, site_name)

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    text = (soup.title.get_text(" ", strip=True) if soup.title else "") + " " + soup.get_text(" ", strip=True)
    text = text.lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        log("BLOCKED", url, site_name)
        product_cache[url] = (False, [])
        return False, []

    matches = [k for k in TARGET_KEYWORDS if k in text]

    if not matches:
        log("SKIP", f"No keyword match -> {url}", site_name)
        product_cache[url] = (False, [])
        return False, []

    if "booster" not in text:
        log("SKIP", f"No booster -> {url}", site_name)
        product_cache[url] = (False, [])
        return False, []

    log("MATCH", f"{url} -> {matches}", site_name)

    product_cache[url] = (True, matches)
    return True, matches

# =========================
# MAIN LOOP
# =========================

def run_cycle(state):

    log("SYSTEM", "Starting scan cycle")

    for site in SITES:

        log("SITE", site["name"], site["name"])

        soup = scrape(site["url"], site["name"])
        links = extract_links(soup, site["url"], site["allowed_prefix"], site["name"])

        for url in links:

            key = f"{site['name']}::{url}"

            if key in state:
                log("SEEN", url, site["name"])
                continue

            state[key] = True
            log("NEW", url, site["name"])

            ok, matches = check_product(url, site["name"])

            if ok:
                send_alert(site["name"], url, matches)

    save_state(state)

# =========================
# MAIN
# =========================

def main():

    state = load_state()

    log("SYSTEM", "🟢 Tracker running")

    while True:
        start = time.time()

        try:
            run_cycle(state)
        except Exception as e:
            log("FATAL", str(e))

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))

if __name__ == "__main__":
    main()