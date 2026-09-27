// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

// In-memory counter backup for instant UI updates
let localScans = 0;
let localThreats = 0;

// Update counter UI elements
function updateCountersUI(scans, threats) {
  const scansElem = document.getElementById("scans");
  const threatsElem = document.getElementById("threats");
  
  if (scansElem) scansElem.textContent = scans;
  if (threatsElem) threatsElem.textContent = threats;
}

// Load saved stats on startup
function loadStats() {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["totalScans", "threatsBlocked"], (stats) => {
      localScans = stats.totalScans || 0;
      localThreats = stats.threatsBlocked || 0;
      updateCountersUI(localScans, localThreats);
    });
  } else {
    updateCountersUI(localScans, localThreats);
  }
}

// Increment counters after each scan
function recordScan(isThreat) {
  localScans += 1;
  if (isThreat) localThreats += 1;

  // Immediate live UI update
  updateCountersUI(localScans, localThreats);

  // Save to Chrome local storage
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({
      totalScans: localScans,
      threatsBlocked: localThreats
    });
  }
}

// Check Backend Health API
async function checkHealth() {
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");

  try {
    const res = await fetch(HEALTH_API, { 
      method: "GET",
      signal: AbortSignal.timeout(3000) 
    });
    
    if (res.ok) {
      if (statusDot) statusDot.className = "status-dot online";
      if (statusText) statusText.textContent = "Backend: Online";
      return true;
    } else {
      throw new Error("Backend offline");
    }
  } catch (err) {
    if (statusDot) statusDot.className = "status-dot offline";
    if (statusText) statusText.textContent = "Backend: Offline";
    return false;
  }
}

// Initialize Popup
document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  checkHealth();

  // Re-check backend health every 8 seconds
  setInterval(checkHealth, 8000);

  const scanBtn = document.getElementById("scanBtn");
  const payloadInput = document.getElementById("payload");
  const contextInput = document.getElementById("context");
  const outDiv = document.getElementById("out") || document.getElementById("result");

  if (!scanBtn) return;

  scanBtn.addEventListener("click", async () => {
    const payload = payloadInput ? payloadInput.value.trim() : "";
    const context = contextInput ? contextInput.value.trim() : "";

    if (!payload) {
      alert("Please paste a URL or UPI payload first.");
      return;
    }

    scanBtn.disabled = true;
    scanBtn.textContent = "Scanning...";

    try {
      const response = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          qr_decoded_text: payload,
          context_text: context || null,
          scan_source: "extension_popup"
        })
      });

      if (!response.ok) {
        throw new Error("Server HTTP error " + response.status);
      }

      const data = await response.json();
      const isThreat = data.risk_level === "CRITICAL" || data.risk_level === "HIGH";

      // 1. Display verdict output box
      if (outDiv) {
        outDiv.className = "out " + (isThreat ? "crit" : "safe");
        outDiv.style.display = "block";
        outDiv.innerHTML = `<b>[${data.risk_level}] ${data.threat_score}/100</b><br/>${data.verdict}`;
      }

      // 2. Increment counters!
      recordScan(isThreat);

    } catch (err) {
      console.error("Scan error:", err);
      if (outDiv) {
        outDiv.className = "out crit";
        outDiv.style.display = "block";
        outDiv.textContent = "Error: Backend unreachable on localhost:8000";
      }
    } finally {
      scanBtn.disabled = false;
      scanBtn.textContent = "Scan with AI";
    }
  });
});
