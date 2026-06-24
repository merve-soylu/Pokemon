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
        "allowed_prefix": "https://www.officeworks.com.au",
        "js": True
    },
    {
        "name": "Target",
        "url": "https://www.target.com.au/c/toys/trading-card-games/pokemon-cards/W1852642",
        "allowed_prefix": "https://www.target.com.au",
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

# =========================
# STATE
# =========================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, "r"))
        except:
            return {}
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

# =========================
# DISCORD
# =========================

def send_alert(site, url, matches):
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

def scrape(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    return BeautifulSoup(r.text, "html.parser")

def extract_links(soup, base_url, allowed_prefix):
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

    return links

# =========================
# PRODUCT CHECK (ONLY ONCE PER PRODUCT)
# =========================

product_cache = {}   # URL -> (valid, matches)

def check_product(url):
    if url in product_cache:
        return product_cache[url]

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    text = (soup.title.get_text(" ", strip=True) if soup.title else "") + " " + soup.get_text(" ", strip=True)
    text = text.lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        product_cache[url] = (False, [])
        return False, []

    matches = [k for k in TARGET_KEYWORDS if k in text]
    if not matches:
        product_cache[url] = (False, [])
        return False, []

    if "booster" not in text:
        product_cache[url] = (False, [])
        return False, []

    product_cache[url] = (True, matches)
    return True, matches

# =========================
# MAIN LOOP
# =========================

def run_cycle(state):

    for site in SITES:

        soup = scrape(site["url"])
        links = extract_links(soup, site["url"], site["allowed_prefix"])

        for url in links:

            key = f"{site['name']}::{url}"

            # 🔥 ONLY NEW PRODUCTS GET FULL CHECK
            if key in state:
                continue

            state[key] = True  # mark immediately

            ok, matches = check_product(url)

            if ok:
                send_alert(site["name"], url, matches)

    save_state(state)

# =========================
# MAIN
# =========================

def main():

    state = load_state()

    print("🟢 Tracker running")

    while True:
        start = time.time()

        try:
            run_cycle(state)
        except Exception as e:
            print("ERROR:", e)

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))

if __name__ == "__main__":
    main()