// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

// DOM elements
const scanBtn = document.getElementById("scanBtn");
const payloadInput = document.getElementById("payload");
const contextInput = document.getElementById("context");
const resultDiv = document.getElementById("out") || document.getElementById("result");
const scansCount = document.getElementById("scans");
const threatsCount = document.getElementById("threats");

// Load counters from Chrome local storage on startup
function refreshStats() {
  chrome.storage.local.get(["totalScans", "threatsBlocked"], (stats) => {
    if (scansCount) scansCount.textContent = stats.totalScans || 0;
    if (threatsCount) threatsCount.textContent = stats.threatsBlocked || 0;
  });
}

// Update stats after a successful scan
function incrementStats(riskLevel) {
  const isThreat = riskLevel === "CRITICAL" || riskLevel === "HIGH";
  
  chrome.storage.local.get(["totalScans", "threatsBlocked"], (stats) => {
    const newScans = (stats.totalScans || 0) + 1;
    const newThreats = (stats.threatsBlocked || 0) + (isThreat ? 1 : 0);
    
    chrome.storage.local.set({
      totalScans: newScans,
      threatsBlocked: newThreats
    }, () => {
      // Immediately update UI numbers on screen
      if (scansCount) scansCount.textContent = newScans;
      if (threatsCount) threatsCount.textContent = newThreats;
    });
  });
}

// Scan button click handler
scanBtn.addEventListener("click", async () => {
  const payload = payloadInput.value.trim();
  const context = contextInput ? contextInput.value.trim() : "";
  
  if (!payload) return;
  
  scanBtn.disabled = true;
  scanBtn.textContent = "Scanning...";
  
  if (resultDiv) {
    resultDiv.classList.remove("hidden", "crit", "safe", "critical", "high", "medium");
    resultDiv.innerHTML = "Scanning with AI...";
    resultDiv.style.display = "block";
  }
  
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
      throw new Error(`Server returned ${response.status}`);
    }
    
    const data = await response.json();
    
    // 1. Display verdict
    const bad = data.risk_level === "CRITICAL" || data.risk_level === "HIGH";
    if (resultDiv) {
      resultDiv.classList.add(bad ? "crit" : "safe");
      resultDiv.innerHTML = `<b>[${data.risk_level}] ${data.threat_score}/100</b><br/>${data.verdict}`;
    }
    
    // 2. Increment & save counters!
    incrementStats(data.risk_level);
    
  } catch (error) {
    if (resultDiv) {
      resultDiv.classList.add("crit");
      resultDiv.textContent = "Backend unreachable on localhost:8000. Is python main.py running?";
    }
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = "Scan with AI";
  }
});

// Initialize on load
document.addEventListener("DOMContentLoaded", () => {
  refreshStats();
  if (payloadInput) payloadInput.focus();
});
