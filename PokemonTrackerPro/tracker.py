import time
import random

from logger import log
from scraper import scrape_category, extract_product_candidates
from product_checker import check_product_with_page
from discord_bot import send_product_alert
from storage import save_json
from config import STATE_FILE, PRODUCTS_FILE
from link_filter import classify_link_before_open

def state_key(site_name, url):
    return f"{site_name}::{url}"

def mark_ignored(state, site_name, url, title, reason):
    key = state_key(site_name, url)

    state[key] = {
        "url": url,
        "title": title or url,
        "ignored": True,
        "interesting": False,
        "ignore_reason": reason,
    }

def process_product(state, products_db, site_name, product):
    url = product["url"]
    key = state_key(site_name, url)

    old = state.get(key)

    if product.get("ignored"):
        mark_ignored(
            state,
            site_name,
            url,
            product.get("title", url),
            product.get("ignore_reason", "irrelevant after opening")
        )
        return "ignored"

    state[key] = {
        "title": product["title"],
        "url": url,
        "status": product["status"],
        "availability": product["availability"],
        "matches": product["matches"],
        "ignored": False,
        "interesting": True,
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

def should_check_link(state, site_name, url, anchor_text):
    key = state_key(site_name, url)
    old = state.get(key)

    if old is not None:
        if old.get("ignored") is True or old.get("interesting") is False:
            return False, "already ignored"

        if old.get("interesting") is True:
            return True, "tracked product"

    classification = classify_link_before_open(url, anchor_text)

    if not classification["should_open"]:
        mark_ignored(
            state,
            site_name,
            url,
            anchor_text or url,
            classification["ignore_reason"]
        )
        return False, classification["ignore_reason"]

    return True, "new candidate"

def run_cycle(state, products_db, browser_manager, sites):
    cycle_start = time.time()

    log("CYCLE", "Starting scan cycle")

    for site in sites:
        if site.get("enabled") is False:
            log("SKIP", "Store disabled in config", site["name"])
            continue
        name = site["name"]
        page = browser_manager.get_page(name)

        log("STORE", "Scanning", name)

        soup = scrape_category(site, page)

        if not soup.find_all("a"):
            log("WARN", "No links found / blocked / empty page", name)
            continue

        candidates = extract_product_candidates(
            soup,
            site["url"],
            site["allowed_prefix"]
        )

        to_check = []
        skipped = 0
        tracked = 0
        new_candidates = 0

        for candidate in candidates:
            should_check, reason = should_check_link(
                state,
                name,
                candidate["url"],
                candidate.get("anchor_text", "")
            )

            if should_check:
                to_check.append(candidate)
                if reason == "tracked product":
                    tracked += 1
                else:
                    new_candidates += 1
            else:
                skipped += 1

        log("FOUND", f"{len(candidates)} candidates", name)
        log("SKIP", f"{skipped} skipped before opening", name)
        log("CHECK", f"{len(to_check)} to open ({tracked} tracked, {new_candidates} new)", name)

        checked = 0
        ignored = 0
        new = 0
        updated = 0
        seen = 0

        for candidate in to_check:
            product = check_product_with_page(
                candidate["url"],
                name,
                page
            )

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
            f"Checked {checked} | New {new} | Updated {updated} | Seen {seen} | Ignored after open {ignored}",
            name
        )

        time.sleep(random.uniform(3, 6))

    save_json(STATE_FILE, state)
    save_json(PRODUCTS_FILE, products_db)
    browser_manager.save_session()

    log("CYCLE", f"Finished in {round(time.time() - cycle_start, 1)}s")