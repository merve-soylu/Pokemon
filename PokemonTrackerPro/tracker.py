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

    if product.get("ignored"):
        state[key] = {
            "url": url,
            "title": product.get("title", url),
            "ignored": True,
            "ignore_reason": product.get("ignore_reason", "irrelevant"),
            "interesting": False
        }
        return "ignored"

    state[key] = {
        "title": product["title"],
        "url": url,
        "status": product["status"],
        "availability": product["availability"],
        "matches": product["matches"],
        "ignored": False,
        "interesting": True
    }

    products_db.setdefault(product["title"] or url, {})
    products_db[product["title"] or url][site_name] = {
        "url": url,
        "status": product["status"],
        "availability": product["availability"],
        "matches": product["matches"],
    }

    if old is None or not old.get("interesting"):
        send_product_alert(
            site_name,
            product["title"],
            url,
            product["matches"],
            product["availability"],
            "NEW VALID PRODUCT"
        )
        return "new"

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
        return "updated"

    return "seen"

def should_check_link(state, site_name, url):
    key = f"{site_name}::{url}"
    old = state.get(key)

    if old is None:
        return True

    if old.get("ignored") is True or old.get("interesting") is False:
        return False

    if old.get("interesting") is True:
        return True

    # Old state format fallback: check once and upgrade schema
    return True

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

        new_or_tracked_links = [
            url for url in links
            if should_check_link(state, name, url)
        ]

        skipped = len(links) - len(new_or_tracked_links)

        log("FOUND", f"{len(links)} links found", name)
        log("SKIP", f"{skipped} ignored/irrelevant links skipped", name)
        log("CHECK", f"{len(new_or_tracked_links)} links need checking", name)

        checked = 0
        ignored = 0
        new = 0
        updated = 0
        seen = 0

        for url in new_or_tracked_links:
            product = check_product_with_page(url, name, page)

            if product:
                checked += 1
                result = process_product(state, products_db, name, product)

                if result == "ignored":
                    ignored += 1
                elif result == "new":
                    new += 1
                elif result == "updated":
                    updated += 1
                elif result == "seen":
                    seen += 1

            time.sleep(random.uniform(0.8, 1.8))

        log(
            "DONE",
            f"Checked {checked} | New {new} | Updated {updated} | Seen {seen} | Ignored {ignored}",
            name
        )

        time.sleep(random.uniform(3, 6))

    save_json(STATE_FILE, state)
    save_json(PRODUCTS_FILE, products_db)
    browser_manager.save_session()

    log("CYCLE", f"Finished in {round(time.time() - cycle_start, 1)}s")