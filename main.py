import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
from urllib.parse import urlsplit, urlunsplit

# =========================
# CONFIG
# =========================

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1519121141862760628/3yxReFPKTxZ4xhMmhSRGQsJaVdab0n8yKsV3l1DVdvryH6GrTnLUCfzYXedh4nLFJiph"
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
    }
]

TARGET_KEYWORDS = [
    "ascended heroes", "sv11a",
    "pitch black", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces", "mega evolution"
]

AVAILABILITY_KEYWORDS = [
    "pre-order", "preorder",
    "available now", "coming soon",
    "notify me", "add to cart",
    "buy now", "in stock",
    "order now", "reserve now"
]

URL_KEYWORDS = [
    "ascended", "heroes",
    "pitch", "black",
    "anniversary", "30th",
    "mega", "forces"
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
        json={"content": "✅ Raspberry Pi Pokémon monitor is ONLINE"},
        timeout=10
    )

def send_alert(site, url, targets, availability):
    embed = {
        "title": "🚨 Pokémon Drop Signal",
        "description": f"**{site}** detected activity",
        "color": 16711680,
        "fields": [
            {"name": "URL", "value": url[:1024]},
            {"name": "Targets", "value": ", ".join(targets) or "None"},
            {"name": "Status", "value": ", ".join(availability) or "None"},
            {"name": "Time", "value": str(datetime.now())}
        ]
    }

    requests.post(
        DISCORD_WEBHOOK,
        json={"embeds": [embed]},
        timeout=10
    )

# =========================
# URL NORMALISER
# =========================

def normalize(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip("/"), "", ""))

# =========================
# SCRAPER (STATIC)
# =========================

def scrape_static(url):
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20
    )
    r.raise_for_status()

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    return html.lower(), soup

# =========================
# SCRAPER (JS SITES)
# =========================

def scrape_js(url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        content = page.content()
        browser.close()

    return content.lower(), BeautifulSoup(content, "html.parser")

# =========================
# CHECK SITE
# =========================

def check_site(site):
    try:
        if site["js"]:
            text, soup = scrape_js(site["url"])
        else:
            text, soup = scrape_static(site["url"])

        targets = [k for k in TARGET_KEYWORDS if k in text]
        availability = [k for k in AVAILABILITY_KEYWORDS if k in text]

        urls = []
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(k in href for k in URL_KEYWORDS):
                urls.append(a["href"])

        return {
            "targets": list(set(targets)),
            "availability": list(set(availability)),
            "urls": list(set(urls))
        }

    except Exception as e:
        print(f"{site['name']} error: {e}")
        return None

# =========================
# MAIN
# =========================

def main():

    known = load_state()
    updated = False

    for site in SITES:

        result = check_site(site)
        if not result:
            continue

        for url in result["urls"]:

            key = f"{site['name']}::{normalize(url)}"

            if key in known:
                continue

            send_alert(
                site["name"],
                url,
                result["targets"],
                result["availability"]
            )

            known.add(key)
            updated = True

            print(f"[{datetime.now()}] ALERT: {site['name']} -> {url}")

    if updated:
        save_state(known)

# =========================
# STARTUP BEHAVIOUR
# =========================

if __name__ == "__main__":
    discord_ping_startup()
    main()