// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";

function refreshStats() {
  chrome.runtime.sendMessage({ type: "QG_STATS" }, (s) => {
    document.getElementById("scans").textContent =
      s?.totalScans || 0;
    document.getElementById("threats").textContent =
      s?.threatsBlocked || 0;
  });
}

document
  .getElementById("scanBtn")
  .addEventListener("click", async () => {
    const text =
      document.getElementById("payload").value.trim();
    const context =
      document.getElementById("context").value.trim();
    if (!text) return;

    const btn = document.getElementById("scanBtn");
    const out = document.getElementById("out");
    btn.disabled = true;
    btn.textContent = "Scanning...";

    try {
      const res = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          qr_decoded_text: text,
          context_text: context || null,
          scan_source: "extension_popup"
        })
      });
      const data = await res.json();
      out.classList.remove("hidden", "crit", "safe");
      const bad =
        data.risk_level === "CRITICAL" ||
        data.risk_level === "HIGH";
      out.classList.add(bad ? "crit" : "safe");
      out.innerHTML =
        `<b>${data.risk_level}</b> — ` +
        `${data.threat_score}/100<br/>${data.verdict}`;
      refreshStats();
    } catch (e) {
      out.classList.remove("hidden");
      out.classList.add("crit");
      out.textContent =
        "Backend not reachable on localhost:8000";
    } finally {
      btn.disabled = false;
      btn.textContent = "Scan with AI";
    }
  });

refreshStats();
