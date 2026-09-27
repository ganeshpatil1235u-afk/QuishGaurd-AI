// extension/popup/popup.js

const API        = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

let totalScans   = 0;
let totalThreats = 0;

document.addEventListener("DOMContentLoaded", function () {

  // ── Grab Elements ──────────────────────────────────────
  const scansEl   = document.getElementById("scans");
  const threatsEl = document.getElementById("threats");
  const payloadEl = document.getElementById("payload");
  const contextEl = document.getElementById("context");
  const btnEl     = document.getElementById("scanBtn");
  const outEl     = document.getElementById("out");
  const footEl    = document.getElementById("footText");

  // ── Load Saved Counters ────────────────────────────────
  chrome.storage.local.get(
    ["totalScans", "threatsBlocked"],
    function (saved) {
      totalScans   = saved.totalScans     || 0;
      totalThreats = saved.threatsBlocked || 0;
      scansEl.textContent   = totalScans;
      threatsEl.textContent = totalThreats;
    }
  );

  // ── Health Check ───────────────────────────────────────
  function checkHealth() {
    fetch(HEALTH_API)
      .then(function (r) {
        if (r.ok) {
          footEl.textContent = "✅ Backend: Online";
          footEl.style.color = "#22c55e";
        } else {
          throw new Error("not ok");
        }
      })
      .catch(function () {
        footEl.textContent = "❌ Backend Offline — run python main.py";
        footEl.style.color = "#ef4444";
      });
  }

  checkHealth();
  setInterval(checkHealth, 8000);

  // ── Scan Button ────────────────────────────────────────
  btnEl.addEventListener("click", async function () {

    const payload = payloadEl.value.trim();
    const context = contextEl.value.trim();

    if (!payload) {
      alert("Please paste a URL or UPI string first!");
      return;
    }

    // Disable button + show loading
    btnEl.disabled    = true;
    btnEl.textContent = "Scanning...";

    outEl.style.display    = "block";
    outEl.style.marginTop  = "10px";
    outEl.style.padding    = "10px";
    outEl.style.borderRadius = "8px";
    outEl.style.fontSize   = "12px";
    outEl.style.background = "#1e293b";
    outEl.style.border     = "1px solid #334155";
    outEl.style.color      = "#e2e8f0";
    outEl.textContent      = "⏳ Analyzing...";

    try {
      // ── Call Backend ─────────────────────────────────
      const response = await fetch(API, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          qr_decoded_text: payload,
          context_text:    context || null,
          scan_source:     "extension_popup"
        })
      });

      if (!response.ok) {
        throw new Error("Server returned " + response.status);
      }

      const data = await response.json();

      const isThreat =
        data.risk_level === "CRITICAL" ||
        data.risk_level === "HIGH";

      // ── Show Result ──────────────────────────────────
      outEl.style.display     = "block";
      outEl.style.border      = isThreat
        ? "1px solid #ef4444"
        : "1px solid #22c55e";
      outEl.style.color       = isThreat ? "#fca5a5" : "#86efac";
      outEl.style.background  = "#1e293b";
      outEl.innerHTML =
        "<b>" + data.risk_level + "</b>" +
        " — " + data.threat_score + " / 100" +
        "<br/><br/>" + data.verdict;

      // ── Update Counters ──────────────────────────────
      totalScans += 1;
      if (isThreat) totalThreats += 1;

      scansEl.textContent   = totalScans;
      threatsEl.textContent = totalThreats;

      // ── Save to Chrome Storage ───────────────────────
      chrome.storage.local.set({
        totalScans:     totalScans,
        threatsBlocked: totalThreats
      });

    } catch (err) {

      // ── Show Error ───────────────────────────────────
      outEl.style.display    = "block";
      outEl.style.border     = "1px solid #ef4444";
      outEl.style.color      = "#fca5a5";
      outEl.style.background = "#1e293b";
      outEl.innerHTML =
        "❌ <b>Backend unreachable</b><br/>" +
        "Make sure backend is running:<br/>" +
        "<code>python main.py</code>";

    } finally {
      btnEl.disabled    = false;
      btnEl.textContent = "Scan with AI";
    }

  });

});
