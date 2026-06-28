from playwright.sync_api import sync_playwright
from config import BROWSER_PROFILE_DIR, HEADLESS
from logger import log

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.category_pages = {}
        self.product_pages = {}

    def start(self, sites):
        self.playwright = sync_playwright().start()

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            headless=HEADLESS,
            slow_mo=40,
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        for site in sites:
            name = site["name"]
            self.category_pages[name] = self.context.new_page()
            self.product_pages[name] = self.context.new_page()
            log("PAGE", "Category + product pages created", name)

    def get_category_page(self, site_name):
        return self.category_pages[site_name]

    def get_product_page(self, site_name):
        return self.product_pages[site_name]

    def get_page(self, site_name):
        # backwards compatibility
        return self.get_category_page(site_name)

    def save_session(self):
        pass

    def stop(self):
        try:
            self.context.close()
        except:
            pass

        try:
            self.playwright.stop()
        except:
            pass