import os
import requests
from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

def discord_post(payload):
    if not DISCORD_WEBHOOK:
        return

    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    except:
        pass

def send_startup(sites, poll_interval):
    names = "\n".join([f"✅ {s['name']}" for s in sites])

    discord_post({
        "content": "🟢 Pokémon Tracker Pro ONLINE",
        "embeds": [{
            "title": "Tracker Started",
            "description": f"Watching:\n{names}\n\nPolling every {poll_interval}s"
        }]
    })

def send_product_alert(site, title, url, matches, availability, alert_type="NEW PRODUCT"):
    discord_post({
        "content": "@everyone 🚨 Pokémon product alert",
        "embeds": [{
            "title": f"🚨 {alert_type}",
            "description": title or "Product detected",
            "fields": [
                {"name": "Store", "value": site},
                {"name": "URL", "value": url[:1000]},
                {"name": "Matches", "value": ", ".join(matches) or "None"},
                {"name": "Status", "value": ", ".join(availability) or "None"},
            ]
        }]
    })

def send_crash(message):
    discord_post({
        "content": f"❌ Pokémon Tracker crashed:\n```{message}```"
    })