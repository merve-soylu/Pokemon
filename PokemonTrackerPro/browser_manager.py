import os
from playwright.sync_api import sync_playwright
from config import SESSION_FILE, HEADLESS
from logger import log

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.pages = {}

    def start(self, sites):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=HEADLESS,
            slow_mo=30
        )

        storage_state = SESSION_FILE if os.path.exists(SESSION_FILE) else None

        self.context = self.browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        for site in sites:
            self.pages[site["name"]] = self.context.new_page()
            log("PAGE", "Persistent page created", site["name"])

    def get_page(self, site_name):
        return self.pages[site_name]

    def save_session(self):
        try:
            self.context.storage_state(path=SESSION_FILE)
        except Exception as e:
            log("ERROR", f"Failed to save session: {e}")

    def stop(self):
        self.save_session()

        try:
            self.context.close()
        except:
            pass

        try:
            self.browser.close()
        except:
            pass

        try:
            self.playwright.stop()
        except:
            pass