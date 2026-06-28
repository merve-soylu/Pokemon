import time
import random
from logger import log
from scraper import scrape_category, extract_product_links
from product_checker import check_product_with_page
from discord_bot import send_product_alert
from storage import save_json
from config import STATE_FILE, PRODUCTS_FILE

def process_product(state, products_db, site_name, product):
    url = product["url"]
    key = f"{site_name}::{url}"

    old = state.get(key)

    state[key] = {
        "title": product["title"],
        "url": url,
        "status": product["status"],
        "availability": product["availability"],
        "matches": product["matches"],
    }

    products_db.setdefault(product["title"] or url, {})
    products_db[product["title"] or url][site_name] = {
        "url": url,
        "status": product["status"],
        "availability": product["availability"],
        "matches": product["matches"],
    }

    if not product["matches"] or not product["booster_ok"]:
        return

    if old is None:
        send_product_alert(
            site_name,
            product["title"],
            url,
            product["matches"],
            product["availability"],
            "NEW PRODUCT"
        )
        return

    old_status = old.get("status", -1)

    if product["status"] > old_status:
        send_product_alert(
            site_name,
            product["title"],
            url,
            product["matches"],
            product["availability"],
            "STATUS IMPROVED"
        )

def run_cycle(state, products_db, browser_manager, sites):
    cycle_start = time.time()

    log("CYCLE", "Starting scan cycle")

    for site in sites:
        name = site["name"]
        page = browser_manager.get_page(name)

        log("STORE", "Scanning", name)

        soup = scrape_category(site, page)

        if not soup.find_all("a"):
            log("WARN", "No links found / blocked / empty page", name)
            continue

        links = extract_product_links(
            soup,
            site["url"],
            site["allowed_prefix"]
        )

        log("FOUND", f"{len(links)} product/category links", name)

        checked = 0

        for url in links:
            product = check_product_with_page(url, name, page)

            if product:
                checked += 1
                process_product(state, products_db, name, product)

            time.sleep(random.uniform(0.8, 1.8))

        log("DONE", f"Checked {checked} products", name)

        time.sleep(random.uniform(3, 6))

    save_json(STATE_FILE, state)
    save_json(PRODUCTS_FILE, products_db)
    browser_manager.save_session()

    log("CYCLE", f"Finished in {round(time.time() - cycle_start, 1)}s")