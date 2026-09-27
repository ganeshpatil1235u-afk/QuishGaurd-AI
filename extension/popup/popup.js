// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

let totalScans = 0;
let totalThreats = 0;

document.addEventListener("DOMContentLoaded", function () {

  // Get elements AFTER DOM loads
  const scansEl   = document.getElementById("scans");
  const threatsEl = document.getElementById("threats");
  const payloadEl = document.getElementById("payload");
  const contextEl = document.getElementById("context");
  const scanBtn   = document.getElementById("scanBtn");
  const outEl     = document.getElementById("out");
  const footEl    = document.querySelector(".foot");

  // Load saved stats from Chrome storage
  chrome.storage.local.get(["totalScans", "threatsBlocked"], function(data) {
    totalScans   = data.totalScans     || 0;
    totalThreats = data.threatsBlocked || 0;
    scansEl.textContent   = totalScans;
    threatsEl.textContent = totalThreats;
  });

  // Check backend health
  function checkHealth() {
    fetch(HEALTH_API)
      .then(function(res) {
        if (res.ok) {
          footEl.textContent = "✅ Backend: Online | Manifest V3";
          footEl.style.color = "#22c55e";
        } else {
          throw new Error("offline");
        }
      })
      .catch(function() {
        footEl.textContent = "❌ Backend: Offline | Run python main.py";
        footEl.style.color = "#ef4444";
      });
  }

  // Run health check immediately and every 8 seconds
  checkHealth();
  setInterval(checkHealth, 8000);

  // Update counters on screen
  function updateCounters(isThreat) {
    totalScans += 1;
    if (isThreat) totalThreats += 1;

    // Update screen numbers directly
    scansEl.textContent   = totalScans;
    threatsEl.textContent = totalThreats;

    // Save to Chrome storage
    chrome.storage.local.set({
      totalScans:     totalScans,
      threatsBlocked: totalThreats
    });
  }

  // Show result in output div
  function showResult(data) {
    const isThreat = 
      data.risk_level === "CRITICAL" || 
      data.risk_level === "HIGH";

    // IMPORTANT: Remove "hidden" class AND set display block
    outEl.classList.remove("hidden");
    outEl.style.display = "block";

    // Set color class
    outEl.classList.remove("crit", "safe");
    outEl.classList.add(isThreat ? "crit" : "safe");

    // Show result text
    outEl.innerHTML = 
      "<b>" + data.risk_level + "</b>" +
      " — " + data.threat_score + "/100" +
      "<br/>" + data.verdict;

    return isThreat;
  }

  // Scan button click
  scanBtn.addEventListener("click", async function() {
    const payload = payloadEl.value.trim();
    const context = contextEl.value.trim();

    if (!payload) {
      alert("Please paste a URL or UPI string first!");
      return;
    }

    // Show loading
    scanBtn.disabled = true;
    scanBtn.textContent = "Scanning...";

    // Show analyzing message
    outEl.classList.remove("hidden");
    outEl.style.display = "block";
    outEl.classList.remove("crit", "safe");
    outEl.textContent = "⏳ Analyzing threat...";

    try {
      const response = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          qr_decoded_text: payload,
          context_text:    context || null,
          scan_source:     "extension_popup"
        })
      });

      if (!response.ok) {
        throw new Error("Server error: " + response.status);
      }

      const data = await response.json();
      console.log("Scan result:", data);

      // Show result
      const isThreat = showResult(data);

      // Update counters
      updateCounters(isThreat);

      console.log("Counters updated - Scans:", totalScans, "Threats:", totalThreats);

    } catch (err) {
      console.error("Scan failed:", err);

      outEl.classList.remove("hidden");
      outEl.style.display = "block";
      outEl.classList.remove("safe");
      outEl.classList.add("crit");
      outEl.textContent = 
        "❌ Cannot reach backend.\n" +
        "Make sure python main.py is running!";
    } finally {
      scanBtn.disabled = false;
      scanBtn.textContent = "Scan with AI";
    }
  });

});
