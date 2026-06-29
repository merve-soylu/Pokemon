import random

POLL_INTERVAL = random.randint(70, 110)

STATE_FILE = "state.json"
PRODUCTS_FILE = "products.json"

BROWSER_PROFILE_DIR = "browser_profile"
FIREFOX_PROFILE_DIR = "/home/merve/.mozilla/firefox/ebgames-profile"

HEADLESS = False

TARGET_KEYWORDS = [
    "ascended heroes", "ascended hero", "sv11a", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces",
]

AVAILABILITY_KEYWORDS = [
    # Offline / unavailable
    "out of stock",
    "sold out",
    "notify me",
    "coming soon",

    # In-store only
    "in-store only",
    "in store only",
    "instore only",
    "in-store",
    "in store",
    "click and collect",
    "collect in store",

    # Online purchasing
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

POKEMON_RELATED_KEYWORDS = [
    "pokemon",
    "pokémon",
    "tcg",
    "trading card",
    "trading-card",
    "booster",
]

BLOCKED_KEYWORDS = [
    "binder", "binders",
    "sleeve", "sleeves",
    "playmat", "play mat",
    "deck box", "deckbox",
    "album",
    "portfolio",
    "book", "pin", 
    "sticker",
    "poster"
]

URL_BLOCKED_KEYWORDS = [
    "binder", "binders",
    "sleeve", "sleeves",
    "playmat", "play-mat", "play mat",
    "deck-box", "deckbox", "deck box",
    "album",
    "portfolio",
    "book", "pin", 
    "sticker",
    "poster"
]

STATUS_PRIORITY = {
    # Not purchasable
    "out of stock": 0,
    "sold out": 0,
    "notify me": 1,

    # Interesting but not online
    "coming soon": 2,
    "in-store only": 2,
    "in store only": 2,
    "instore only": 2,
    "in-store": 2,
    "in store": 2,
    "click and collect": 2,
    "collect in store": 2,

    # Online preorder
    "available now": 3,
    "pre order": 4,
    "pre-order": 4,
    "preorder": 4,

    # Purchasable
    "add to cart": 5,
    "add to bag": 5,
    "add to basket": 5,

    "buy now": 6,
    "order now": 6,
    "in stock": 7,
}

SITES = [
    {
        "name": "Toymate",
        "url": "https://toymate.com.au/pokemon/?_bc_fsnf=1&Product+Category=Trading+Cards",
        "allowed_prefix": "https://toymate.com.au",
        "enabled": True,
        "engine": "playwright",
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
        "enabled": True,
        "engine": "selenium_firefox",
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon-trading-cards/",
        "allowed_prefix": "https://www.kmart.com.au",
        "enabled": True,
        "engine": "selenium_firefox",
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/search?q=pokemon%20tcg&view=grid&page=1&sortBy=bestmatch",
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