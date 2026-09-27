// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

// In-memory counters
let totalScans = 0;
let totalThreats = 0;

// Get elements using EXACT IDs from popup.html
const scansEl   = document.getElementById("scans");
const threatsEl = document.getElementById("threats");
const payloadEl = document.getElementById("payload");
const contextEl = document.getElementById("context");
const scanBtn   = document.getElementById("scanBtn");
const outEl     = document.getElementById("out");
const footEl    = document.querySelector(".foot");

// Load saved counters from Chrome storage
function loadStats() {
  try {
    chrome.storage.local.get(["totalScans", "threatsBlocked"], (data) => {
      totalScans  = data.totalScans    || 0;
      totalThreats = data.threatsBlocked || 0;
      scansEl.textContent   = totalScans;
      threatsEl.textContent = totalThreats;
    });
  } catch (e) {
    scansEl.textContent   = 0;
    threatsEl.textContent = 0;
  }
}

// Save and show updated counters
function addScan(isThreat) {
  totalScans += 1;
  if (isThreat) totalThreats += 1;

  // Directly update the DOM numbers
  scansEl.textContent   = totalScans;
  threatsEl.textContent = totalThreats;

  // Save to Chrome storage
  try {
    chrome.storage.local.set({
      totalScans:     totalScans,
      threatsBlocked: totalThreats
    });
  } catch (e) {
    console.log("Storage save failed (not critical):", e);
  }
}

// Show result in the out div
function showResult(data) {
  const isThreat = data.risk_level === "CRITICAL" || data.risk_level === "HIGH";

  outEl.className = "out " + (isThreat ? "crit" : "safe");
  outEl.style.display = "block";
  outEl.innerHTML = `<b>${data.risk_level}</b> — ${data.threat_score}/100<br/>${data.verdict}`;
}

// Check backend health and update footer text
async function checkHealth() {
  try {
    const res = await fetch(HEALTH_API, {
      method: "GET",
      signal: AbortSignal.timeout(4000)
    });
    if (res.ok) {
      footEl.textContent = "✅ Backend: Online | Manifest V3";
      footEl.style.color = "#22c55e";
    } else {
      throw new Error("not ok");
    }
  } catch (e) {
    footEl.textContent = "❌ Backend: Offline | Start python main.py";
    footEl.style.color = "#ef4444";
  }
}

// Scan button click
scanBtn.addEventListener("click", async () => {
  const payload = payloadEl.value.trim();
  const context = contextEl.value.trim();

  if (!payload) {
    alert("Please paste a URL or UPI string first!");
    return;
  }

  // Loading state
  scanBtn.disabled = true;
  scanBtn.textContent = "Scanning...";
  outEl.className = "out";
  outEl.style.display = "block";
  outEl.innerHTML = "⏳ Analyzing...";

  try {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        qr_decoded_text: payload,
        context_text:    context || null,
        scan_source:     "extension_popup"
      })
    });

    if (!res.ok) throw new Error("HTTP " + res.status);

    const data = await res.json();

    // Show verdict
    showResult(data);

    // Update counters
    const isThreat = data.risk_level === "CRITICAL" || data.risk_level === "HIGH";
    addScan(isThreat);

  } catch (err) {
    outEl.className = "out crit";
    outEl.style.display = "block";
    outEl.textContent = "❌ Backend unreachable. Run: python main.py";
    console.error("Scan error:", err);
  } finally {
    scanBtn.disabled = false;
    scanBtn.textContent = "Scan with AI";
  }
});

// Run on load
loadStats();
checkHealth();
setInterval(checkHealth, 10000);
