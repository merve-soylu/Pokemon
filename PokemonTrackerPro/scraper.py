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
    "Load more",
    "Show more",
    "View more",
]

def is_blocked_html(html):
    lower = html.lower()
    return any(signal in lower for signal in BLOCK_SIGNALS)

def human_pause(page, min_ms=900, max_ms=2200):
    page.wait_for_timeout(random.randint(min_ms, max_ms))

    try:
        page.mouse.move(
            random.randint(150, 900),
            random.randint(120, 650),
            steps=random.randint(10, 30)
        )
    except:
        pass

def wait_for_challenge(page, site, max_rounds=12):
    for i in range(max_rounds):
        html = page.content()

        if is_blocked_html(html):
            log("WAIT", f"Verification/access page detected ({i + 1}/{max_rounds})", site)
            human_pause(page, 4000, 6000)
            continue

        return html

    log("BLOCKED", "Still blocked after waiting", site)
    return page.content()

def scroll_to_bottom(page, site, max_rounds=12):
    previous_height = -1

    for i in range(max_rounds):
        page.mouse.wheel(0, random.randint(2500, 4500))
        human_pause(page, 900, 1600)

        try:
            height = page.evaluate("document.body.scrollHeight")
        except:
            break

        if height == previous_height:
            log("SCROLL", f"Finished after {i + 1} scrolls", site)
            break

        previous_height = height

def click_load_more(page, site, max_clicks=12):
    clicks = 0

    for _ in range(max_clicks):
        clicked = False

        for text in LOAD_MORE_TEXTS:
            try:
                locator = page.get_by_text(text, exact=False)

                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click(timeout=4000)
                    clicks += 1
                    clicked = True
                    log("LOAD_MORE", f"Clicked {text}", site)
                    human_pause(page, 1800, 3000)
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
        human_pause(page, 1000, 3000)

        page.goto(url, wait_until="domcontentloaded", timeout=70000)
        human_pause(page, 5000, 7000)

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

def extract_product_candidates(soup, base_url, allowed_prefix):
    candidates = {}

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]

        if not href.startswith(allowed_prefix):
            continue

        anchor_text = a.get_text(" ", strip=True)

        href_lower = href.lower()
        anchor_lower = anchor_text.lower()

        if not any(x in href_lower or x in anchor_lower for x in [
            "/product", "/products", "/p/", "/item",
            "pokemon", "pokémon", "tcg", "trading-card", "trading card",
            "booster"
        ]):
            continue

        candidates[href] = {
            "url": href,
            "anchor_text": anchor_text,
        }

    return list(candidates.values())