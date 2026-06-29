import random

POLL_INTERVAL_MIN = 70
POLL_INTERVAL_MAX = 110

STATE_FILE = "state.json"
PRODUCTS_FILE = "products.json"

BROWSER_PROFILE_DIR = "browser_profile"
HEADLESS = False

API_HOST = "127.0.0.1"
API_PORT = 8765

FIREFOX_EB_URL = "https://www.ebgames.com.au/featured/pokemon-trading-card-game"

TARGET_KEYWORDS = [
    "ascended heroes", "ascended hero", "sv11a", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces",
]

BLOCKED_KEYWORDS = [
    "binder", "binders",
    "sleeve", "sleeves",
    "playmat", "play mat",
    "deck box", "deckbox",
    "album",    "pin"
    "portfolio",
    "book",
]

URL_BLOCKED_KEYWORDS = BLOCKED_KEYWORDS

POKEMON_RELATED_KEYWORDS = [
    "pokemon",
    "pokémon",
    "tcg",
    "trading card",
    "trading-card",
    "booster",
]

AVAILABILITY_KEYWORDS = [
    "out of stock",
    "sold out",
    "notify me",
    "coming soon",
    "in-store only",
    "in store only",
    "instore only",
    "click and collect",
    "collect in store",
    "pre-order",
    "preorder",
    "pre order",
    "add to cart",
    "add to bag",
    "add to basket",
    "buy now",
    "order now",
    "available now",
    "in stock",
]

STATUS_PRIORITY = {
    "out of stock": 0,
    "sold out": 0,
    "notify me": 1,
    "coming soon": 2,
    "in-store only": 2,
    "in store only": 2,
    "instore only": 2,
    "click and collect": 2,
    "collect in store": 2,
    "available now": 3,
    "pre order": 4,
    "pre-order": 4,
    "preorder": 4,
    "add to cart": 5,
    "add to bag": 5,
    "add to basket": 5,
    "buy now": 6,
    "order now": 6,
    "in stock": 7,
}

VALID_PRODUCT_WORDS = [
    "booster",
    "booster pack",
    "booster box",
    "blister",
    "bundle",
    "box",
    "tin",
    "mini tin",
    "etb",
]

SITES = [
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
        "enabled": True,
        "engine": "firefox_extension"
    },
    {
        "name": "Toymate",
        "url": "https://toymate.com.au/pokemon/?_bc_fsnf=1&Product+Category=Trading+Cards",
        "allowed_prefix": "https://toymate.com.au",
        "enabled": True,
        "engine": "playwright",
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon-trading-cards/",
        "allowed_prefix": "https://www.kmart.com.au",
        "enabled": True,
        "engine": "kmart_selenium",
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/search?q=pokemon&view=grid&page=1&sortBy=bestmatch",
        "allowed_prefix": "https://www.officeworks.com.au",
        "enabled": True,
        "engine": "playwright",
    },
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "allowed_prefix": "https://www.jbhifi.com.au",
        "enabled": True,
        "engine": "playwright",
    },
]