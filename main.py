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
        "name": "Big W",
        "url": "https://www.bigw.com.au/toys/trading-cards/pokemon-trading-cards/c/681510201",
        "allowed_prefix": "https://www.bigw.com.au",
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
        "name": "Target",
        "url": "https://www.target.com.au/c/toys/trading-card-games/pokemon-cards/W1852642",
        "allowed_prefix": "https://www.target.com.au",
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
    "ascended heroes", "sv11a", "sv11b",
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

    requests.post(
        DISCORD_WEBHOOK,
        json={"content": "@everyone 🚨 BOOSTER DROP DETECTED", "embeds": [embed]},
        timeout=10
    )

# =========================
# SCRAPERS
# =========================

def scrape_static(url, site):
    log("SCRAPE", url, site)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    log("SCRAPE", f"Found {len(soup.find_all('a'))} links", site)
    return soup

def scrape_js(url, site):
    log("SCRAPE", f"JS render {url}", site)

    with sync_playwright() as p:
        log("SCRAPE", "Opening browser", site)
        browser = p.chromium.launch(headless=True, args=[
            "--disable-http2",
            "--disable-features=IsolateOrigins,site-per-process"
            
        ])
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebkit/537.36 Chrome/137.0.0.0 Safari/537.36"
        )
        
        if site == Big
        log("SCRAPE", "Loading page", site)
        try: 
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
        except Exception as e:
            log("ERROR", f"goto failed: {e}", site)
            raise
        
        log("SCRAPE", "Page loaded", site)

        # 🔥 scroll to force lazy-loaded products
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    log("SCRAPE", f"Found {len(soup.find_all('a'))} links", site)
    return soup

def scrape_js_dumb(url, site):
    log("SCRAPE", f"BIG W dumb render {url}", site)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-http2",
                "--disable-dev-shm-usage",
                "--no-sandbox"
            ]
        )

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
        )

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # minimal wait only
            page.wait_for_timeout(2500)

            # single gentle scroll
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1000)

        except Exception as e:
            log("ERROR", f"Big W load failed: {e}", site)
            browser.close()
            raise

        html = page.content()
        browser.close()

    return BeautifulSoup(html, "html.parser")

def scrape_api_fallback(url, site):
    log("SCRAPE", f"API/JSON fallback {url}", site)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        captured = []

        def handle_response(response):
            try:
                if any(x in response.url.lower() for x in [
                    "product", "search", "category", "plp", "collection", "graphql", "api"
                ]):
                    captured.append(response)
            except:
                pass

        page.on("response", handle_response)

        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        html = page.content()
        browser.close()

    # Try extracting JSON from responses
    all_text = html.lower()

    for r in captured:
        try:
            if "application/json" in r.headers.get("content-type", ""):
                data = r.json()
                all_text += json.dumps(data).lower()
        except:
            pass

    return BeautifulSoup(all_text, "html.parser")

# =========================
# PRODUCT EXTRACTION
# =========================

def extract_product_links(soup, base_url, allowed_prefix, site):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        # MUCH broader capture (critical fix)
        if any(x in href for x in [
            "/product", "/products", "/p/",
            "/c/", "/search", "/item",
            "pokemon", "trading", "tcg"
        ]):
            links.add(href)

    log("FOUND", f"{len(links)} product links", site)
    return links

# =========================
# PRODUCT CHECK
# =========================

product_cache = {}

def check_product_page(url, site):
    if url in product_cache:
        return product_cache[url]

    log("CHECK", url, site)

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    headings = " ".join(h.get_text(" ", strip=True).lower() for h in soup.find_all(["h1", "h2"]))
    body = soup.get_text(" ", strip=True).lower()

    combined = f"{title} {headings} {body}"

    # FIXED: correct variable (was "text")
    if any(b in combined for b in BLOCKED_KEYWORDS):
        log("BLOCKED", url, site)
        product_cache[url] = ([], [], False)
        return [], [], False

    matches = [k for k in TARGET_KEYWORDS if k in combined]
    availability = [k for k in AVAILABILITY_KEYWORDS if k in combined]

    booster_ok = any(x in combined for x in [
        "booster",
        "booster pack",
        "booster box",
        "tcg",
        "trading card"
    ])

    product_cache[url] = (matches, availability, booster_ok)

    log("MATCH", f"{url} -> {matches}", site)

    return matches, availability, booster_ok

# =========================
# MAIN LOOP
# =========================

def run_cycle(known_products):

    log("SYSTEM", "Starting scan cycle")

    for site in SITES:

        name = site["name"]

        try:
            if name in ["Big W", "Kmart", "Target", "Pokemon Center"]:
                soup = scrape_api_fallback(site["url"], name)
            else:
                soup = scrape_static(site["url"], name) if not site["js"] else scrape_js(site["url"], name)

            links = extract_product_links(
                soup,
                site["url"],
                site["allowed_prefix"],
                name
            )

            for url in links:

                key = f"{name}::{url}"

                if key in known_products:
                    log("SEEN", url, name)
                    continue

                known_products.add(key)
                log("NEW", url, name)

                matches, availability, booster_ok = check_product_page(url, name)

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
