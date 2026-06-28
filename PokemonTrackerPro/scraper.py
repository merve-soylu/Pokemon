import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from logger import log

BLOCK_SIGNALS = [
    "just a moment",
    "checking your browser",
    "cf-browser-verification",
    "attention required",
    "access denied",
    "akamai",
]

LOAD_MORE_TEXTS = [
    "Load More",
    "Show More",
    "See More",
    "View More",
]

def is_blocked_html(html):
    lower = html.lower()
    return any(signal in lower for signal in BLOCK_SIGNALS)

def wait_for_challenge(page, site):
    for _ in range(12):
        html = page.content()

        if is_blocked_html(html):
            log("WAIT", "Verification/access page detected; waiting naturally", site)
            page.wait_for_timeout(5000)
            continue

        return html

    log("BLOCKED", "Still blocked after waiting", site)
    return page.content()

def scroll_to_bottom(page, site, max_rounds=10):
    previous_height = 0

    for i in range(max_rounds):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(random.randint(900, 1600))

        height = page.evaluate("document.body.scrollHeight")

        if height == previous_height:
            log("SCROLL", f"Finished after {i + 1} scrolls", site)
            break

        previous_height = height

def click_load_more(page, site, max_clicks=10):
    clicks = 0

    for _ in range(max_clicks):
        clicked = False

        for text in LOAD_MORE_TEXTS:
            locator = page.get_by_text(text, exact=False)

            try:
                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click(timeout=3000)
                    page.wait_for_timeout(random.randint(1500, 2500))
                    clicks += 1
                    clicked = True
                    log("LOAD_MORE", f"Clicked {text}", site)
                    break
            except:
                pass

        if not clicked:
            break

    return clicks

def scrape_category(site, page):
    name = site["name"]
    url = site["url"]

    log("SCRAPE", f"Loading {url}", name)

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=70000)
        page.wait_for_timeout(4000)

        html = wait_for_challenge(page, name)

        if is_blocked_html(html):
            log("BLOCKED", "Access denied / bot page remained", name)
            return BeautifulSoup("", "html.parser")

        scroll_to_bottom(page, name)
        click_load_more(page, name)
        scroll_to_bottom(page, name)

        return BeautifulSoup(page.content(), "html.parser")

    except Exception as e:
        log("ERROR", str(e), name)
        return BeautifulSoup("", "html.parser")

def extract_product_links(soup, base_url, allowed_prefix):
    links = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        if any(x in href.lower() for x in [
            "/product", "/products", "/p/", "/item",
            "pokemon", "tcg", "trading-card"
        ]):
            links.add(href)

    return sorted(links)