// extension/background.js
const API = "http://localhost:8000/api/scan";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "quishguard_scan",
    title: "🛡️ Scan with QuishGuard AI",
    contexts: ["selection", "link", "image", "page"]
  });
  chrome.storage.local.set({
    totalScans: 0,
    threatsBlocked: 0
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "quishguard_scan") return;
  const payload =
    info.selectionText ||
    info.linkUrl ||
    info.srcUrl ||
    info.pageUrl;
  if (!payload) return;
  await scanPayload(payload);
});

async function scanPayload(text, contextText = "") {
  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        qr_decoded_text: text,
        context_text: contextText || null,
        scan_source: "chrome_extension"
      })
    });
    const data = await res.json();
    const blocked =
      data.risk_level === "CRITICAL" ||
      data.risk_level === "HIGH" ? 1 : 0;
    chrome.storage.local.get(
      ["totalScans", "threatsBlocked"],
      (s) => {
        chrome.storage.local.set({
          totalScans: (s.totalScans || 0) + 1,
          threatsBlocked: (s.threatsBlocked || 0) + blocked
        });
      }
    );
    return data;
  } catch (e) {
    return {
      error: String(e),
      risk_level: "UNKNOWN",
      threat_score: 0,
      verdict: "Backend unreachable"
    };
  }
}

chrome.runtime.onMessage.addListener((msg, _s, sendResponse) => {
  if (msg.type === "QG_STATS") {
    chrome.storage.local.get(
      ["totalScans", "threatsBlocked"],
      sendResponse
    );
    return true;
  }
});
