POLL_INTERVAL = 75

STATE_FILE = "state.json"
PRODUCTS_FILE = "products.json"

BROWSER_PROFILE_DIR = "browser_profile"

HEADLESS = False

TARGET_KEYWORDS = [
    "ascended heroes", "ascended hero", "sv11a", "sv11b",
    "30th anniversary", "30th collection",
    "mega forces",
]

AVAILABILITY_KEYWORDS = [
    "pre-order", "preorder", "pre order",
    "available now", "coming soon",
    "notify me",
    "add to cart",
    "add to basket",
    "buy now",
    "in stock",
    "order now",
    "add to bag",
    "reserve now"
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
    "book",
]

URL_BLOCKED_KEYWORDS = [
    "binder", "binders",
    "sleeve", "sleeves",
    "playmat", "play-mat", "play mat",
    "deck-box", "deckbox", "deck box",
    "album",
    "portfolio",
    "book",
]

STATUS_PRIORITY = {
    "notify me": 0,
    "coming soon": 1,
    "available now": 2,
    "pre order": 3,
    "pre-order": 3,
    "preorder": 3,
    "reserve now": 3,
    "add to cart": 4,
    "add to basket": 4,
    "add to bag": 4,
    "buy now": 5,
    "order now": 5,
    "in stock": 6,
}

SITES = [
    {
        "name": "Toymate",
        "url": "https://toymate.com.au/pokemon/?_bc_fsnf=1&Product+Category=Trading+Cards",
        "allowed_prefix": "https://toymate.com.au",
        "enabled": True,
    },
    {
        "name": "EB Games",
        "url": "https://www.ebgames.com.au/featured/pokemon-trading-card-game",
        "allowed_prefix": "https://www.ebgames.com.au",
        "enabled": True,
    },
    {
        "name": "Kmart",
        "url": "https://www.kmart.com.au/category/toys/pokemon-trading-cards/",
        "allowed_prefix": "https://www.kmart.com.au",
        "enabled": False,
    },
    {
        "name": "Officeworks",
        "url": "https://www.officeworks.com.au/shop/officeworks/search?q=pokemon%20tcg&view=grid&page=1&sortBy=bestmatch",
        "allowed_prefix": "https://www.officeworks.com.au",
        "enabled": True,
    },
    {
        "name": "JB HiFi",
        "url": "https://www.jbhifi.com.au/collections/collectibles-merchandise/pokemon-trading-cards",
        "allowed_prefix": "https://www.jbhifi.com.au",
        "enabled": True,
    },
]