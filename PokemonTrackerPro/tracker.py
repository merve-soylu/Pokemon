import time
import random

from logger import log
from scraper import scrape_category, extract_product_candidates
from product_checker import check_product_with_page
from discord_bot import send_product_alert
from storage import save_json
from config import STATE_FILE, PRODUCTS_FILE


PING_STATUS_THRESHOLD = 4  # preorder onwards


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


def should_ping(product):
    return product.get("status", -1) >= PING_STATUS_THRESHOLD


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
            product.get("ignore_reason", "irrelevant after opening"),
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
        if should_ping(product):
            send_product_alert(
                site_name,
                product["title"],
                url,
                product["matches"],
                product["availability"],
                "NEW VALID PRODUCT",
            )
            return "new_pinged"

        return "new_tracked_no_ping"

    old_status = old.get("status", -1)

    if product["status"] > old_status:
        if should_ping(product):
            send_product_alert(
                site_name,
                product["title"],
                url,
                product["matches"],
                product["availability"],
                "STATUS IMPROVED",
            )
            return "updated_pinged"

        return "updated_no_ping"

    return "seen"


def should_check_link(state, site_name, url, anchor_text):
    from link_filter import classify_link_before_open

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
            classification["ignore_reason"],
        )
        return False, classification["ignore_reason"]

    return True, "new candidate"


def run_cycle(state, products_db, browser_manager, sites, eb_firefox=None):
    cycle_start = time.time()

    log("CYCLE", "Starting scan cycle")

    for site in sites:
        if site.get("enabled") is False:
            log("SKIP", "Store disabled in config", site["name"])
            continue

        name = site["name"]

        log("STORE", "Scanning", name)

        # =========================
        # EB GAMES — SELENIUM FIREFOX
        # =========================

        if site.get("engine") == "selenium_firefox":
            if eb_firefox is None:
                log("ERROR", "EB Firefox engine missing", name)
                continue

            candidates = eb_firefox.scrape_category(site)

            to_check = []
            skipped = 0
            tracked = 0
            new_candidates = 0

            for candidate in candidates:
                should_check, reason = should_check_link(
                    state,
                    name,
                    candidate["url"],
                    candidate.get("anchor_text", ""),
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
            new_pinged = 0
            new_no_ping = 0
            updated_pinged = 0
            updated_no_ping = 0
            seen = 0

            for candidate in to_check:
                product = eb_firefox.check_product(candidate["url"], name)

                if product:
                    checked += 1
                    result = process_product(state, products_db, name, product)

                    if result == "ignored":
                        ignored += 1
                    elif result == "new_pinged":
                        new_pinged += 1
                    elif result == "new_tracked_no_ping":
                        new_no_ping += 1
                    elif result == "updated_pinged":
                        updated_pinged += 1
                    elif result == "updated_no_ping":
                        updated_no_ping += 1
                    elif result == "seen":
                        seen += 1

                time.sleep(random.uniform(1.5, 3.5))

            log(
                "DONE",
                (
                    f"Checked {checked} | "
                    f"New pinged {new_pinged} | "
                    f"New no ping {new_no_ping} | "
                    f"Updated pinged {updated_pinged} | "
                    f"Updated no ping {updated_no_ping} | "
                    f"Seen {seen} | "
                    f"Ignored after open {ignored}"
                ),
                name,
            )

            time.sleep(random.uniform(3, 6))
            continue

        # =========================
        # NORMAL STORES — PLAYWRIGHT
        # =========================

        category_page = browser_manager.get_category_page(name)
        product_page = browser_manager.get_product_page(name)

        soup = scrape_category(site, category_page)

        if not soup.find_all("a"):
            log("WARN", "No links found / blocked / empty page", name)
            continue

        candidates = extract_product_candidates(
            soup,
            site["url"],
            site["allowed_prefix"],
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
                candidate.get("anchor_text", ""),
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
        new_pinged = 0
        new_no_ping = 0
        updated_pinged = 0
        updated_no_ping = 0
        seen = 0

        for candidate in to_check:
            product = check_product_with_page(
                candidate["url"],
                name,
                product_page,
            )

            if product:
                checked += 1
                result = process_product(state, products_db, name, product)

                if result == "ignored":
                    ignored += 1
                elif result == "new_pinged":
                    new_pinged += 1
                elif result == "new_tracked_no_ping":
                    new_no_ping += 1
                elif result == "updated_pinged":
                    updated_pinged += 1
                elif result == "updated_no_ping":
                    updated_no_ping += 1
                elif result == "seen":
                    seen += 1

            time.sleep(random.uniform(0.8, 1.8))

        log(
            "DONE",
            (
                f"Checked {checked} | "
                f"New pinged {new_pinged} | "
                f"New no ping {new_no_ping} | "
                f"Updated pinged {updated_pinged} | "
                f"Updated no ping {updated_no_ping} | "
                f"Seen {seen} | "
                f"Ignored after open {ignored}"
            ),
            name,
        )

        time.sleep(random.uniform(3, 6))

    save_json(STATE_FILE, state)
    save_json(PRODUCTS_FILE, products_db)
    browser_manager.save_session()

    log("CYCLE", f"Finished in {round(time.time() - cycle_start, 1)}s")