import time
import random
import subprocess

from config import SITES, POLL_INTERVAL_MAX, POLL_INTERVAL_MIN, STATE_FILE, PRODUCTS_FILE, FIREFOX_EB_URL
from logger import log, banner
from storage import load_json
from discord_bot import send_startup, send_crash
from browser_manager import BrowserManager
from tracker import run_cycle
from api_server import ApiServer
from kmart_selenium import KmartSelenium


def launch_firefox_eb():
    try:
        subprocess.Popen([
            "firefox",
            "--new-window",
            FIREFOX_EB_URL,
        ])
        log("FIREFOX", "Opened EB Games in Firefox")
    except Exception as e:
        log("ERROR", f"Could not launch Firefox: {e}")


def has_enabled_engine(engine):
    return any(
        site.get("enabled") is not False and site.get("engine") == engine
        for site in SITES
    )


def main():
    banner()

    state = load_json(STATE_FILE, {})
    products_db = load_json(PRODUCTS_FILE, {})

    browser_manager = BrowserManager()
    kmart_engine = None
    api_server = ApiServer(state, products_db)

    try:
        api_server.start()

        browser_manager.start(SITES)

        if has_enabled_engine("kmart_selenium"):
            kmart_engine = KmartSelenium()
            kmart_engine.start()

        if has_enabled_engine("firefox_extension"):
            launch_firefox_eb()

        ok = send_startup(SITES, f"{POLL_INTERVAL_MIN}-{POLL_INTERVAL_MAX}")

        if not ok:
            log("ERROR", "Startup Discord message failed")
        else:
            log("DISCORD", "Startup Discord message sent")

        log("SYSTEM", "Tracker running")

        while True:
            start = time.time()

            try:
                run_cycle(state, products_db, browser_manager, SITES, kmart_engine)
            except Exception as e:
                log("FATAL", str(e))
                send_crash(str(e))

            sleep_time = random.randint(POLL_INTERVAL_MIN, POLL_INTERVAL_MAX)
            sleep_time += random.uniform(0, 5)

            log("SLEEP", f"Sleeping {round(sleep_time, 1)}s")
            time.sleep(sleep_time)

    finally:
        if kmart_engine:
            kmart_engine.stop()

        browser_manager.stop()
        api_server.stop()


if __name__ == "__main__":
    main()