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

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================
# LOGGING
# =========================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# =========================
# SITES
# =========================

SITES = [
    {"name": "JB HiFi", "url": "https://www.jbhifi.com.au", "prefix": "https://www.jbhifi.com.au"},
    {"name": "EB Games", "url": "https://www.ebgames.com.au", "prefix": "https://www.ebgames.com.au"},
    {"name": "Pokemon Center", "url": "https://www.pokemoncenter.com/en-au", "prefix": "https://www.pokemoncenter.com/en-au"},
    {"name": "Kmart", "url": "https://www.kmart.com.au", "prefix": "https://www.kmart.com.au"},
    {"name": "Officeworks", "url": "https://www.officeworks.com.au/", "prefix": "https://www.officeworks.com.au/"},
    {"name": "Target", "url": "https://www.target.com.au/", "prefix": "https://www.target.com.au/"},
    {"name": "Gameology", "url": "https://www.gameology.com.au", "prefix": "https://www.gameology.com.au"},
]

# =========================
# FILTERS
# =========================

TARGET_KEYWORDS = [
    "sv11a", "sv11b",
    "ascended heroes",
    "30th anniversary",
    "30th collection",
    "mega forces",
    "booster"
]

BLOCKED_KEYWORDS = [
    "binder", "sleeves", "playmat",
    "deck box", "album", "case", "book"
]

# =========================
# STATE
# =========================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"❌ state save failed: {e}")

# =========================
# DISCORD
# =========================

def send_discord(title, url, site, event_type):
    if not DISCORD_WEBHOOK:
        log("⚠️ Missing Discord webhook")
        return

    msg = {
        "content": f"🚨 @everyone {event_type}",
        "embeds": [
            {
                "title": title[:256],
                "description": f"**Site:** {site}\n**Event:** {event_type}",
                "url": url,
                "color": 16711680,
                "fields": [
                    {"name": "Link", "value": url},
                    {"name": "Time", "value": str(datetime.now())}
                ]
            }
        ]
    }

    try:
        requests.post(DISCORD_WEBHOOK, json=msg, timeout=10)
    except:
        log("⚠️ Discord failed")

# =========================
# SCRAPER
# =========================

def scrape(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

# =========================
# LINK EXTRACTION
# =========================

def extract_links(soup, base, prefix):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"]).split("?")[0]

        if href.startswith(prefix) and ("/product" in href or "/p/" in href):
            links.add(href)

    return links

# =========================
# PRODUCT ANALYSIS
# =========================

def is_relevant(text):
    text = text.lower()

    if any(b in text for b in BLOCKED_KEYWORDS):
        return False

    if not any(k in text for k in TARGET_KEYWORDS):
        return False

    return True

# =========================
# PRODUCT CHECK
# =========================

def check_product(url):
    try:
        soup = scrape(url)

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        body = soup.get_text(" ", strip=True)

        combined = f"{title} {body}".lower()

        return {
            "title": title,
            "hash": hashlib.sha256(combined.encode()).hexdigest(),
            "text": combined
        }

    except Exception as e:
        log(f"❌ product error {url}: {e}")
        return None

# =========================
# MAIN LOOP
# =========================

def run(state):

    for site in SITES:
        log(f"🔎 scanning {site['name']}")

        try:
            soup = scrape(site["url"])
            links = extract_links(soup, site["url"], site["prefix"])

            log(f"   ↳ {len(links)} product links")

            for url in links:

                product = check_product(url)
                if not product:
                    continue

                title = product["title"]
                new_hash = product["hash"]
                text = product["text"]

                relevant = is_relevant(text)

                # =====================
                # NEW PRODUCT
                # =====================
                if url not in state:
                    state[url] = {
                        "hash": new_hash,
                        "first_seen": str(datetime.now())
                    }

                    log(f"🆕 NEW: {title}")

                    if relevant:
                        send_discord(title, url, site["name"], "NEW PRODUCT")

                    continue

                old_hash = state[url]["hash"]

                # =====================
                # CHANGED PRODUCT
                # =====================
                if old_hash != new_hash:
                    log(f"⚡ UPDATED: {title}")

                    if relevant:
                        send_discord(title, url, site["name"], "UPDATED PRODUCT")

                # =====================
                # UPDATE STATE
                # =====================
                state[url]["hash"] = new_hash
                state[url]["last_seen"] = str(datetime.now())

        except Exception as e:
            log(f"❌ site error {site['name']}: {e}")

# =========================
# START
# =========================

def main():

    state = load_state()

    log("🟢 Tracker ONLINE")
    send_discord("Tracker Started", "N/A", "SYSTEM", "STARTUP")

    while True:
        start = time.time()

        run(state)
        save_state(state)

        log(f"💾 state saved ({len(state)} products tracked)")

        time.sleep(max(5, POLL_INTERVAL - (time.time() - start)))

if __name__ == "__main__":
    main()