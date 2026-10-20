// Price Bot – เก็บราคา
//
// Runs only when YOU click the toolbar button, press Alt+Shift+P, or right-click
// selected text and choose "เก็บราคา". It reads the page you already have open
// and opens Price Bot's small capture window. It never loads marketplace pages
// by itself.
//
// Why an extension instead of the bookmark button: browsers now stop public
// websites (e.g. Facebook) from opening pages on your own computer
// (localhost), which shows up as "about:blank#blocked". Windows opened by an
// extension aren't affected by that.

const DEFAULT_BASE = "http://localhost:8000";

async function baseUrl() {
  const { base } = await chrome.storage.local.get("base");
  return (base || DEFAULT_BASE).replace(/\/+$/, "");
}

// Injected into the page you're looking at. Must be self-contained.
function readPage() {
  function meta(n) {
    const e = document.querySelector(`meta[property="${n}"],meta[name="${n}"],meta[itemprop="${n}"]`);
    return e ? e.getAttribute("content") || "" : "";
  }
  const sel = String(window.getSelection ? window.getSelection() : "").trim();
  let price = "";
  try {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      const d = JSON.parse(s.textContent);
      for (const x of [].concat(d["@graph"] || d)) {
        let o = x && x.offers;
        if (o) { o = [].concat(o)[0]; price = String(o.price || o.lowPrice || ""); }
        if (price) break;
      }
      if (price) break;
    }
  } catch (e) { /* page has malformed JSON-LD - ignore */ }
  price = price || meta("product:price:amount") || meta("og:price:amount") || meta("price");
  // Last resort (e.g. Facebook item pages, which have no price metadata):
  // the first "฿1,234" / "1,234 บาท" visible on the page. Shown as a guess.
  let guess = "";
  if (!price && !sel) {
    const m = (document.body ? document.body.innerText : "").match(/(?:฿|THB)\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?บาท/);
    if (m) { price = m[0]; guess = "1"; }
  }
  return {
    url: location.href,
    title: meta("og:title") || document.title,
    price,
    guess,
    sel: sel.slice(0, 300),
    image: meta("og:image"),
  };
}

async function capture(tab, selectionText) {
  let data = { url: tab.url || "", title: tab.title || "", price: "", sel: selectionText || "", image: "" };
  try {
    const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: readPage });
    if (res && res.result) data = { ...res.result, sel: selectionText || res.result.sel };
  } catch (e) {
    // Browser-internal pages (edge://, chrome://, the web store) can't be read - still open the form.
  }
  const url = `${await baseUrl()}/capture?${new URLSearchParams(data)}`;
  await chrome.windows.create({ url, type: "popup", width: 580, height: 820, focused: true });
}

chrome.action.onClicked.addListener((tab) => capture(tab));

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "pricebot-capture", title: "เก็บราคา \"%s\" เข้า Price Bot", contexts: ["selection"] });
  chrome.contextMenus.create({ id: "pricebot-capture-page", title: "เก็บราคาหน้านี้เข้า Price Bot", contexts: ["page", "image", "link"] });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  capture(tab, info.menuItemId === "pricebot-capture" ? info.selectionText : "");
});
