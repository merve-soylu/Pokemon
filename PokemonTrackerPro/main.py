import time
import random

from config import SITES, POLL_INTERVAL, STATE_FILE, PRODUCTS_FILE
from logger import log, banner
from storage import load_json
from discord_bot import send_startup, send_crash
from browser_manager import BrowserManager
from tracker import run_cycle

def main():
    banner()

    state = load_json(STATE_FILE, {})
    products_db = load_json(PRODUCTS_FILE, {})

    browser_manager = BrowserManager()

    try:
        browser_manager.start(SITES)

        ok = send_startup(SITES, POLL_INTERVAL)

        if not ok:
            log("ERROR", "Startup Discord message failed")
        else:
            log("DISCORD", "Startup Discord message sent")

        log("SYSTEM", "Tracker running")

        while True:
            start = time.time()

            try:
                run_cycle(state, products_db, browser_manager, SITES)
            except Exception as e:
                log("FATAL", str(e))
                send_crash(str(e))

            sleep_time = max(10, POLL_INTERVAL - (time.time() - start))
            sleep_time += random.uniform(0, 5)

            log("SLEEP", f"Sleeping {round(sleep_time, 1)}s")
            time.sleep(sleep_time)

    finally:
        browser_manager.stop()

if __name__ == "__main__":
    main()