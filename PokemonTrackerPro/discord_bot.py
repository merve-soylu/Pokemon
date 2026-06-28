import os
import requests
from dotenv import load_dotenv
from logger import log

load_dotenv()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

def discord_post(payload):
    if not DISCORD_WEBHOOK:
        log("ERROR", "DISCORD_WEBHOOK missing. Check .env file.")
        return False

    try:
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)

        if response.status_code not in [200, 204]:
            log("ERROR", f"Discord failed: {response.status_code} {response.text}")
            return False

        log("DISCORD", "Message sent successfully")
        return True

    except Exception as e:
        log("ERROR", f"Discord exception: {e}")
        return False

def send_startup(sites, poll_interval):
    names = "\n".join(f"• {site['name']}" for site in sites)

    return discord_post({
        "content": "🟢 Pokémon Tracker Pro is now ONLINE!",
        "embeds": [{
            "title": "🟢 Tracker Started Successfully",
            "color": 0x57F287,
            "fields": [
                {"name": "Watching Stores", "value": names or "None", "inline": False},
                {"name": "Poll Interval", "value": f"{poll_interval} seconds", "inline": True},
                {"name": "Status", "value": "✅ Running", "inline": True}
            ],
            "footer": {"text": "Pokemon Tracker Pro v2"}
        }]
    })

def send_product_alert(site, title, url, matches, availability, alert_type="NEW PRODUCT"):
    return discord_post({
        "content": "@everyone 🚨 Pokémon product alert",
        "embeds": [{
            "title": f"🚨 {alert_type}",
            "description": title or "Product detected",
            "color": 0xED4245,
            "fields": [
                {"name": "Store", "value": site or "Unknown", "inline": True},
                {"name": "URL", "value": url[:1000] if url else "No URL", "inline": False},
                {"name": "Matches", "value": ", ".join(matches) if matches else "None", "inline": True},
                {"name": "Status", "value": ", ".join(availability) if availability else "None", "inline": True},
            ]
        }]
    })

def send_crash(message):
    return discord_post({
        "content": f"❌ Pokémon Tracker crashed:\n```{message}```"
    })