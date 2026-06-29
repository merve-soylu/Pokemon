import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

from config import FIREFOX_PROFILE_DIR
from logger import log
from scraper import extract_product_candidates
from product_checker import parse_product_soup


class EBGamesFirefox:
    def __init__(self):
        self.driver = None

    def start(self):
        options = Options()
        options.profile = FIREFOX_PROFILE_DIR

        # Visible Firefox
        options.add_argument("--width=1280")
        options.add_argument("--height=720")

        self.driver = webdriver.Firefox(options=options)
        log("SELENIUM", "Firefox started for EB Games")

    def stop(self):
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

    def human_pause(self, min_s=1.0, max_s=3.0):
        time.sleep(random.uniform(min_s, max_s))

    def scroll_page(self, rounds=6):
        for _ in range(rounds):
            distance = random.randint(600, 1600)
            self.driver.execute_script(f"window.scrollBy(0, {distance});")
            self.human_pause(0.8, 1.8)

    def page_soup(self):
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def scrape_category(self, site):
        name = site["name"]
        url = site["url"]

        log("SELENIUM", f"Loading {url}", name)

        try:
            self.driver.get(url)
            self.human_pause(5, 8)

            self.scroll_page(8)

            soup = self.page_soup()

            if not soup.find_all("a"):
                log("WARN", "No EB links found", name)
                return []

            candidates = extract_product_candidates(
                soup,
                site["url"],
                site["allowed_prefix"]
            )

            log("FOUND", f"{len(candidates)} EB candidates", name)
            return candidates

        except Exception as e:
            log("ERROR", f"EB category failed: {e}", name)
            return []

    def check_product(self, url, site_name):
        try:
            log("SELENIUM", f"Checking {url}", site_name)

            self.driver.get(url)
            self.human_pause(3, 6)

            soup = self.page_soup()

            return parse_product_soup(url, site_name, soup)

        except Exception as e:
            log("ERROR", f"EB product failed: {e}", site_name)
            return None