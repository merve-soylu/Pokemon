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
HEARTBEAT_INTERVAL = 3600

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
        "js": True
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
]

# =========================
# FILTERS
# =========================

TARGET_KEYWORDS = [
    "ascended heroes",
    "sv11a",
    "sv11b",
    "30th anniversary",
    "30th collection",
    "mega forces"
]

ALERT_STATUSES = [
    "pre-order", "preorder", "pre order",
    "add to cart", "add to bag", "add to basket",
    "buy now", "in stock",
    "order now", "reserve now"
]

BLOCKED_KEYWORDS = [
    "book", "binder", "portfolio", "album",
    "sleeves", "playmat", "deck box",
    "storage", "accessory", "case"
]

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
    requests.post(DISCORD_WEBHOOK, json={"content": "🟢 Pokémon BOOSTER tracker ONLINE"}, timeout=10)

def send_heartbeat():
    requests.post(DISCORD_WEBHOOK, json={"content": "🟢 Tracker heartbeat - still running"}, timeout=10)

def send_crash(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": f"❌ TRACKER CRASH:\n```{msg}```"}, timeout=10)
    except:
        pass

def send_alert(site, url, matches, status, change_type):
    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": f"🚨 {change_type} DETECTED @everyone",
            "embeds": [{
                "title": "Pokémon Booster Alert",
                "description": f"**{site}**",
                "color": 16711680,
                "fields": [
                    {"name": "URL", "value": url[:1024]},
                    {"name": "Sets", "value": ", ".join(matches)},
                    {"name": "Status", "value": status},
                    {"name": "Time", "value": str(datetime.now())}
                ]
            }]
        },
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

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            html = page.content()
            browser.close()
            return html, BeautifulSoup(html, "html.parser")

    except Exception as e:
        print(f"[PLAYWRIGHT ERROR] {url}: {e}")
        return "", BeautifulSoup("", "html.parser")

# =========================
# LINK EXTRACTION
# =========================

def extract_product_links(soup, base_url, allowed_prefix):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href for x in ["/product", "/products/", "/p/"]):
            links.add(href)

    return links

# =========================
# PRODUCT VALIDATION (FIXED CORE LOGIC)
# =========================

def check_product_page(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
        h1 = soup.find("h1")
        h1_text = h1.get_text(" ", strip=True).lower() if h1 else ""
        body = soup.get_text(" ", strip=True).lower()

        combined = f"{title} {h1_text} {body}"

        # MUST be Pokémon-related
        pokemon_ok = any(x in combined for x in ["pokemon", "pokémon", "tcg"])

        # MUST be booster-related (strict filter)
        booster_ok = "booster" in combined

        if not pokemon_ok or not booster_ok:
            return None, None

        # BLOCK unwanted categories BEFORE state
        if any(b in combined for b in BLOCKED_KEYWORDS):
            return None, None

        # must match at least one target set
        matches = [k for k in TARGET_KEYWORDS if k in combined]
        if not matches:
            return None, None

        # status detection
        status_hits = [k for k in ALERT_STATUSES if k in combined]
        status = status_hits[0] if status_hits else "unknown"

        return matches, status

    except:
        return None, None

# =========================
# MAIN CYCLE (FIXED STATE LOGIC)
# =========================

def run_cycle(state):

    for site in SITES:

        try:
            if site["js"]:
                html, soup = scrape_js(site["url"])
            else:
                html, soup = scrape_static(site["url"])

            if not html:
                continue

            links = extract_product_links(
                soup,
                site["url"],
                site["allowed_prefix"]
            )

            for url in links:

                # STEP 1: validate BEFORE touching state
                matches, status = check_product_page(url)

                # ❌ DO NOT STORE INVALID PRODUCTS
                if not matches:
                    continue

                # STEP 2: initialize state only for valid products
                if url not in state:
                    state[url] = {
                        "status": None,
                        "first_seen": str(datetime.now())
                    }

                old_status = state[url]["status"]

                # NEW PRODUCT (first time ever seen valid booster product)
                if old_status is None and status != "unknown":
                    send_alert(site["name"], url, matches, status, "NEW PRODUCT")

                # STATUS CHANGE (only meaningful transitions)
                elif old_status != status and status != "unknown":
                    send_alert(site["name"], url, matches, status, "STATUS CHANGE")

                # STEP 3: update state ONLY for valid products
                state[url]["status"] = status
                state[url]["last_seen"] = str(datetime.now())

        except Exception as e:
            send_crash(f"{site['name']}: {e}")

# =========================
# MAIN LOOP
# =========================

def main():

    state = load_state()

    discord_ping_startup()
    print("🟢 Pokémon tracker running")

    last_heartbeat = time.time()

    while True:

        start = time.time()

        try:
            run_cycle(state)
            save_state(state)

            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL:
                send_heartbeat()
                last_heartbeat = time.time()

        except Exception as e:
            send_crash(str(e))

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))

# =========================
# START
# =========================

if __name__ == "__main__":
    main()