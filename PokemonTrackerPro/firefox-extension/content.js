const TARGET_KEYWORDS = [
  "ascended heroes",
  "ascended hero",
  "sv11a",
  "sv11b",
  "30th anniversary",
  "30th collection",
];

const BLOCKED_KEYWORDS = [
  "binder",
  "binders",
  "sleeve",
  "sleeves",
  "playmat",
  "play mat",
  "deck box",
  "deckbox",
  "album",
  "portfolio",
  "book",
  "pin",
  "sticker",
  "accessory"
];

const VALID_PRODUCT_WORDS = [
  "booster",
  "booster pack",
  "booster box",
  "blister",
  "bundle",
  "tin",
  "mini tin",
  "pokemon",
  "pokemon tcg",
  "etb"
];

const AVAILABILITY_KEYWORDS = [
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
  "in stock"
];

const STATUS_PRIORITY = {
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
  "in stock": 7
};

function norm(text) {
  return String(text || "")
    .toLowerCase()
    .replaceAll("-", " ")
    .replaceAll("_", " ")
    .replace(/\s+/g, " ")
    .trim();
}

function hasAny(text, list) {
  const clean = norm(text);
  return list.some(k => clean.includes(norm(k)));
}

function matched(text, list) {
  const clean = norm(text);
  return list.filter(k => clean.includes(norm(k)));
}

function bestStatus(statuses) {
  if (!statuses.length) return -1;
  return Math.max(...statuses.map(s => STATUS_PRIORITY[s] ?? -1));
}

function isHiddenOrDisabled(el) {
  const styleAttr = (el.getAttribute("style") || "").toLowerCase().replace(/\s+/g, "");
  const classAttr = (el.getAttribute("class") || "").toLowerCase();

  if (el.hasAttribute("hidden")) return true;
  if (el.hasAttribute("disabled")) return true;
  if (el.getAttribute("aria-hidden") === "true") return true;
  if (styleAttr.includes("display:none")) return true;
  if (styleAttr.includes("visibility:hidden")) return true;

  if (
    classAttr.includes("hidden") ||
    classAttr.includes("disabled") ||
    classAttr.includes("is-disabled") ||
    classAttr.includes("visually-hidden")
  ) {
    return true;
  }

  return false;
}

function getBuyBox(doc) {
  const selectors = [
    "[class*=productView]",
    "[class*=ProductView]",
    "[class*=product-detail]",
    "[class*=ProductDetail]",
    "[class*=product-info]",
    "[class*=ProductInfo]",
    "[class*=product-main]",
    "[class*=ProductMain]",
    "[class*=product-form]",
    "[class*=ProductForm]",
    "[class*=buy-box]",
    "[class*=BuyBox]",
    "[id*=product]",
    "[id*=Product]",
    "main"
  ];

  for (const selector of selectors) {
    const el = doc.querySelector(selector);
    if (el) return el;
  }

  return doc.body || doc;
}

function extractAvailability(doc) {
  const buyBox = getBuyBox(doc);

  const selectors = [
    "button",
    "[role=button]",
    "input[type=submit]",
    "input[type=button]",
    "form[action*=cart]",
    "form[action*=Cart]",
    "[class*=stock]",
    "[class*=Stock]",
    "[class*=availability]",
    "[class*=Availability]",
    "[id*=stock]",
    "[id*=Stock]",
    "[id*=availability]",
    "[id*=Availability]",
    "[class*=add-to-cart]",
    "[class*=AddToCart]",
    "[id*=add-to-cart]",
    "[id*=AddToCart]"
  ];

  let text = "";

  for (const selector of selectors) {
    buyBox.querySelectorAll(selector).forEach(el => {
      if (isHiddenOrDisabled(el)) return;

      text += " " + (el.innerText || el.textContent || "");
      text += " " + (el.value || "");
      text += " " + (el.getAttribute("aria-label") || "");
      text += " " + (el.getAttribute("title") || "");
      text += " " + (el.getAttribute("data-button-text") || "");
      text += " " + (el.getAttribute("data-label") || "");
    });
  }

  if (!text.trim()) {
    const fallback = buyBox.innerText || buyBox.textContent || "";
    if (fallback.length < 2500) {
      text = fallback;
    }
  }

  const found = matched(text, AVAILABILITY_KEYWORDS);

  if (!found.length) return [];

  const online = found.filter(s =>
    [
      "in stock",
      "buy now",
      "order now",
      "add to cart",
      "add to bag",
      "add to basket",
      "pre-order",
      "preorder",
      "pre order",
      "available now"
    ].includes(s)
  );

  const unavailable = found.filter(s =>
    [
      "out of stock",
      "sold out",
      "notify me"
    ].includes(s)
  );

  const offline = found.filter(s =>
    [
      "in-store only",
      "in store only",
      "instore only",
      "click and collect",
      "collect in store"
    ].includes(s)
  );

  if (online.length) {
    return [online.sort((a, b) => STATUS_PRIORITY[b] - STATUS_PRIORITY[a])[0]];
  }

  if (unavailable.length) {
    return [unavailable.sort((a, b) => STATUS_PRIORITY[b] - STATUS_PRIORITY[a])[0]];
  }

  if (offline.length) {
    return [offline.sort((a, b) => STATUS_PRIORITY[b] - STATUS_PRIORITY[a])[0]];
  }

  return [found.sort((a, b) => STATUS_PRIORITY[b] - STATUS_PRIORITY[a])[0]];
}

function extractCandidates() {
  const candidates = new Map();

  document.querySelectorAll("a[href]").forEach(a => {
    const url = new URL(a.href, location.href).href.split("?")[0];
    const title = a.innerText || "";
    const combined = `${url} ${title}`;

    if (!url.startsWith("https://www.ebgames.com.au")) return;
    if (!hasAny(combined, ["pokemon", "pokémon", "tcg", "trading card", "booster"])) return;
    if (!hasAny(combined, TARGET_KEYWORDS)) return;
    if (!hasAny(combined, VALID_PRODUCT_WORDS)) return;
    if (hasAny(combined, BLOCKED_KEYWORDS)) return;

    candidates.set(url, { url, title });
  });

  return Array.from(candidates.values());
}

async function checkProduct(candidate) {
  const res = await fetch(candidate.url, { credentials: "include" });
  const html = await res.text();

  const doc = new DOMParser().parseFromString(html, "text/html");
  const text = norm(doc.body?.innerText || doc.body?.textContent || "");

  const title =
    doc.querySelector("h1")?.innerText ||
    doc.querySelector("h1")?.textContent ||
    doc.querySelector("title")?.innerText ||
    doc.querySelector("title")?.textContent ||
    candidate.title ||
    candidate.url;

  const identity = norm(title);

  if (!hasAny(text, ["pokemon", "pokémon"])) return null;
  if (!hasAny(text, TARGET_KEYWORDS)) return null;
  if (!hasAny(`${identity} ${text}`, VALID_PRODUCT_WORDS)) return null;
  if (hasAny(identity, BLOCKED_KEYWORDS)) return null;

  const availability = extractAvailability(doc);
  const matches = matched(text, TARGET_KEYWORDS);

  return {
    title,
    url: candidate.url,
    matches,
    availability,
    status: bestStatus(availability)
  };
}

async function runEBScan() {
  const pageText = norm(document.body?.innerText || "");

  if (
    pageText.includes("verify you are human") ||
    pageText.includes("verifying you are human") ||
    pageText.includes("just a moment")
  ) {
    console.log("EB tracker: still on verification page");
    return;
  }

  const candidates = extractCandidates();
  const products = [];

  for (const candidate of candidates) {
    try {
      const product = await checkProduct(candidate);
      if (product) products.push(product);

      await new Promise(r => setTimeout(r, 800 + Math.random() * 1200));
    } catch (e) {
      console.error("EB product check failed", candidate.url, e);
    }
  }

  if (products.length) {
    browser.runtime.sendMessage({
      type: "EB_PRODUCTS_FOUND",
      products
    });
  }

  console.log(`EB tracker scanned ${candidates.length} candidates, valid products: ${products.length}`);
}

setTimeout(runEBScan, 5000);