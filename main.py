import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
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
HEARTBEAT_INTERVAL = 3600

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# SITES
# =========================

SITES = [
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au",
        "allowed_prefix": "https://www.jbhifi.com.au",
        "js": True
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au",
        "allowed_prefix": "https://www.ebgames.com.au",
        "js": True
    },
    {
        "name": "Pokemon Center",
        "url": "https://www.pokemoncenter.com/en-au",
        "allowed_prefix": "https://www.pokemoncenter.com/en-au",
        "js": False
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au",
        "allowed_prefix": "https://www.kmart.com.au",
        "js": True
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/",
        "allowed_prefix": "https://www.officeworks.com.au/",
        "js": True
    },
    {
        "name": "Target",
        "url": "https://www.target.com.au/",
        "allowed_prefix": "https://www.target.com.au/",
        "js": True
    },
    {
        "name": "Gameology",
        "url": "https://www.gameology.com.au",
        "allowed_prefix": "https://www.gameology.com.au",
        "js": False
    }
]

# =========================
# FILTERS
# =========================

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

ALERT_KEYWORDS = [
    "pre-order", "preorder", "coming soon",
    "add to cart", "add to bag", "add to basket", "in stock", "sold out", "wishlist"
]

# =========================
# LOGGING
# =========================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

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
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

# =========================
# HASH
# =========================

def make_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# =========================
# SCRAPING (FIXED JS SUPPORT)
# =========================

def scrape(url, js=False):
    try:
        if not js:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.text, BeautifulSoup(r.text, "html.parser")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            html = page.content()
            browser.close()
            return html, BeautifulSoup(html, "html.parser")

    except Exception as e:
        log(f"❌ scrape error {url}: {e}")
        return "", BeautifulSoup("", "html.parser")

# =========================
# LINKS
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
# ANALYSIS
# =========================

def analyze_product(text):
    text = text.lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        return None

    if not any(k in text for k in TARGET_KEYWORDS):
        return None

    if "pokemon" not in text and "tcg" not in text:
        return None

    return next((s for s in ALERT_KEYWORDS if s in text), "unknown")

# =========================
# PRODUCT FETCH
# =========================

def get_product_state(url, js=False):
    html, soup = scrape(url, js)

    if not html:
        return None

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    body = soup.get_text(" ", strip=True)

    combined = f"{title}\n{body}".lower()

    return {
        "title": title,
        "hash": make_hash(combined),
        "raw": combined
    }

# =========================
# DISCORD
# =========================

def send_alert(site, url, title, status, change_type):
    log(f"🚨 {change_type} | {title}")

    requests.post(
        DISCORD_WEBHOOK,
        json={
            "content": f"🚨 {change_type} @everyone",
            "embeds": [{
                "title": "Pokémon Early Drop Radar",
                "description": f"**{site}**",
                "color": 16711680,
                "fields": [
                    {"name": "Product", "value": title[:1024]},
                    {"name": "Status", "value": status},
                    {"name": "URL", "value": url[:1024]},
                    {"name": "Time", "value": str(datetime.now())}
                ]
            }]
        },
        timeout=10
    )

# =========================
# MAIN LOOP
# =========================

def run(state):

    for site in SITES:

        log(f"🔎 scanning {site['name']}")

        html, soup = scrape(site["url"], js=site["js"])

        links = extract_product_links(
            soup,
            site["url"],
            site["allowed_prefix"]
        )

        log(f"   ↳ found {len(links)} links")

        for url in links:

            product = get_product_state(url, js=site["js"])
            if not product:
                continue

            title = product["title"]
            new_hash = product["hash"]
            raw = product["raw"]

            if url not in state:
                state[url] = {
                    "hash": new_hash,
                    "first_seen": str(datetime.now()),
                    "last_seen": str(datetime.now())
                }

                log(f"🆕 DISCOVERED: {title}")

                status = analyze_product(raw)
                if status:
                    send_alert(site["name"], url, title, status, "NEW PRODUCT")

                continue

            old_hash = state[url]["hash"]

            if old_hash != new_hash:
                log(f"⚡ CHANGE DETECTED: {title}")

                status = analyze_product(raw)
                if status:
                    send_alert(site["name"], url, title, status, "PAGE UPDATED")

            state[url]["hash"] = new_hash
            state[url]["last_seen"] = str(datetime.now())

# =========================
# START
# =========================

def main():

    state = load_state()

    log("🟢 Early Drop Radar Online (FIXED)")

    while True:
        start = time.time()

        run(state)
        save_state(state)

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))

if __name__ == "__main__":
    main()