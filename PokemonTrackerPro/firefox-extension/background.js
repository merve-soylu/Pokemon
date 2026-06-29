const CATEGORY_URL = "https://www.ebgames.com.au/featured/pokemon-trading-card-game";
const POLL_MINUTES = 2;

browser.runtime.onInstalled.addListener(() => {
  browser.alarms.create("ebgames-refresh", {
    periodInMinutes: POLL_MINUTES
  });
});

browser.alarms.create("ebgames-refresh", {
  periodInMinutes: POLL_MINUTES
});

browser.alarms.onAlarm.addListener(async () => {
  const tabs = await browser.tabs.query({ url: "https://www.ebgames.com.au/*" });

  if (tabs.length > 0) {
    await browser.tabs.update(tabs[0].id, {
      url: CATEGORY_URL
    });
  } else {
    await browser.tabs.create({
      url: CATEGORY_URL
    });
  }
});

browser.runtime.onMessage.addListener(async (message) => {
  if (message.type !== "EB_PRODUCTS_FOUND") return;

  try {
    await fetch("http://127.0.0.1:8765/ebgames/products", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        products: message.products
      })
    });
  } catch (e) {
    console.error("Failed to send EB products to local tracker", e);
  }
});