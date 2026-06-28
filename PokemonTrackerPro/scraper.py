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

NEXT_TEXTS = [
    "Next",
    "Next Page",
    "Next page",
    "›",
    ">",
]

def is_blocked_html(html):
    return any(signal in html.lower() for signal in BLOCK_SIGNALS)

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

def extract_product_candidates(soup, base_url, allowed_prefix):
    candidates = {}

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("?")[0]
        anchor_text = a.get_text(" ", strip=True)

        if not href.startswith(allowed_prefix):
            continue

        href_lower = href.lower()
        anchor_lower = anchor_text.lower()

        if any(x in href_lower for x in [
            "/account",
            "/cart",
            "/login",
            "/wishlist",
            "/blog",
            "/pages/",
        ]):
            continue

        looks_like_product_url = any(x in href_lower for x in [
            "/product",
            "/products",
            "/p/",
            "/item",
        ])

        looks_like_product_text = any(x in anchor_lower for x in [
            "booster",
            "blister",
            "bundle",
            "box",
            "tin",
            "etb",
            "elite trainer",
            "tcg",
            "trading card",
            "pokemon",
            "pokémon",
        ])

        if not looks_like_product_url and not looks_like_product_text:
            continue

        candidates[href] = {
            "url": href,
            "anchor_text": anchor_text,
        }

    return list(candidates.values())

def get_next_page_url(page, current_url, allowed_prefix):
    # 1. Try rel="next"
    try:
        href = page.locator('a[rel="next"]').first.get_attribute("href", timeout=1500)
        if href:
            next_url = urljoin(current_url, href)
            if next_url.startswith(allowed_prefix):
                return next_url
    except:
        pass

    # 2. Try aria-label next buttons/links
    selectors = [
        'a[aria-label*="Next"]',
        'button[aria-label*="Next"]',
        'a[title*="Next"]',
        'button[title*="Next"]',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                href = locator.get_attribute("href")
                if href:
                    next_url = urljoin(current_url, href)
                    if next_url.startswith(allowed_prefix):
                        return next_url
                return "__CLICK_NEXT__"
        except:
            pass

    # 3. Try visible text: Next, >, ›
    for text in NEXT_TEXTS:
        try:
            locator = page.get_by_text(text, exact=True).first
            if locator.count() > 0 and locator.is_visible():
                href = locator.get_attribute("href")
                if href:
                    next_url = urljoin(current_url, href)
                    if next_url.startswith(allowed_prefix):
                        return next_url
                return "__CLICK_NEXT__"
        except:
            pass

    return None

def scrape_one_category_page(site, page, url):
    name = site["name"]

    log("SCRAPE", f"Loading {url}", name)

    try:
        human_pause(page, 1000, 3000)

        page.goto(url, wait_until="domcontentloaded", timeout=70000)
        human_pause(page, 5000, 7000)

        html = wait_for_challenge(page, name)

        if is_blocked_html(html):
            log("BLOCKED", "Access denied / bot page remained", name)
            return BeautifulSoup("", "html.parser"), None

        scroll_to_bottom(page, name)
        click_load_more(page, name)
        scroll_to_bottom(page, name)

        soup = BeautifulSoup(page.content(), "html.parser")
        next_page = get_next_page_url(page, page.url, site["allowed_prefix"])

        return soup, next_page

    except Exception as e:
        log("ERROR", str(e), name)
        return BeautifulSoup("", "html.parser"), None

def scrape_category(site, page, max_pages=5):
    all_html = ""
    visited = set()
    current_url = site["url"]

    for page_num in range(1, max_pages + 1):
        if current_url in visited:
            break

        visited.add(current_url)

        log("PAGE", f"Category page {page_num}/{max_pages}", site["name"])

        soup, next_page = scrape_one_category_page(site, page, current_url)

        if soup.find_all("a"):
            all_html += str(soup)

        if not next_page:
            break

        if next_page == "__CLICK_NEXT__":
            try:
                old_url = page.url

                clicked = False
                for text in NEXT_TEXTS:
                    try:
                        locator = page.get_by_text(text, exact=True).first
                        if locator.count() > 0 and locator.is_visible():
                            locator.click(timeout=4000)
                            clicked = True
                            break
                    except:
                        pass

                if not clicked:
                    break

                human_pause(page, 3000, 5000)

                if page.url == old_url:
                    break

                current_url = page.url

            except:
                break
        else:
            current_url = next_page

        human_pause(page, 2500, 4500)

    return BeautifulSoup(all_html, "html.parser")