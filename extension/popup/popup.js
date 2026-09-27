// extension/popup/popup.js
const API = "http://localhost:8000/api/scan";
const HEALTH_API = "http://localhost:8000/api/health";

// DOM elements
const scanBtn = document.getElementById("scanBtn");
const payloadInput = document.getElementById("payload");
const contextInput = document.getElementById("context");
const resultDiv = document.getElementById("result");
const resultIcon = document.getElementById("resultIcon");
const resultLevel = document.getElementById("resultLevel");
const resultScore = document.getElementById("resultScore");
const resultVerdict = document.getElementById("resultVerdict");
const scansCount = document.getElementById("scans");
const threatsCount = document.getElementById("threats");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// Check backend health
async function checkBackendHealth() {
  try {
    const response = await fetch(HEALTH_API, { 
      method: "GET",
      signal: AbortSignal.timeout(5000)
    });
    
    if (response.ok) {
      const data = await response.json();
      if (data.status === "healthy") {
        statusDot.classList.add("online");
        statusDot.classList.remove("offline");
        statusText.textContent = "Backend: Online";
        return true;
      }
    }
    throw new Error("Backend not healthy");
  } catch (error) {
    console.error("Health check failed:", error);
    statusDot.classList.add("offline");
    statusDot.classList.remove("online");
    statusText.textContent = "Backend: Offline";
    return false;
  }
}

// Refresh stats from storage
function refreshStats() {
  chrome.runtime.sendMessage({ type: "QG_STATS" }, (stats) => {
    if (stats) {
      scansCount.textContent = stats.totalScans || 0;
      threatsCount.textContent = stats.threatsBlocked || 0;
    }
  });
}

// Scan button click handler
scanBtn.addEventListener("click", async () => {
  const payload = payloadInput.value.trim();
  const context = contextInput.value.trim();
  
  if (!payload) {
    alert("Please paste a URL or UPI string to scan");
    return;
  }
  
  // Show loading state
  scanBtn.disabled = true;
  scanBtn.querySelector(".btn-text").textContent = "Scanning...";
  resultDiv.classList.remove("hidden", "critical", "high", "medium", "safe");
  resultLevel.textContent = "ANALYZING...";
  resultScore.textContent = "--/100";
  resultVerdict.textContent = "Please wait...";
  resultDiv.classList.remove("hidden");
  
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
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status}`);
    }
    
    const data = await response.json();
    displayResult(data);
    refreshStats();
    
  } catch (error) {
    console.error("Scan failed:", error);
    resultDiv.classList.add("critical");
    resultIcon.textContent = "❌";
    resultLevel.textContent = "ERROR";
    resultScore.textContent = "N/A";
    resultVerdict.textContent = 
      "Cannot reach backend at localhost:8000.\n\n" +
      "Make sure M2's server is running:\n" +
      "cd backend && python main.py";
  } finally {
    scanBtn.disabled = false;
    scanBtn.querySelector(".btn-text").textContent = "Scan with AI";
  }
});

// Display scan result
function displayResult(data) {
  const riskLevel = (data.risk_level || "UNKNOWN").toLowerCase();
  
  // Clear previous classes
  resultDiv.className = "result";
  
  // Set color theme
  resultDiv.classList.add(riskLevel);
  
  // Set icon
  const icons = {
    critical: "🚨",
    high: "⚠️",
    medium: "⚡",
    safe: "✅",
    unknown: "❓"
  };
  resultIcon.textContent = icons[riskLevel] || "❓";
  
  // Set level text
  resultLevel.textContent = data.risk_level || "UNKNOWN";
  
  // Set score
  resultScore.textContent = `${data.threat_score || 0}/100`;
  
  // Set verdict
  resultVerdict.textContent = data.verdict || "No verdict available";
  
  // Show result
  resultDiv.classList.remove("hidden");
}

// Initialize on popup open
document.addEventListener("DOMContentLoaded", () => {
  console.log("QuishGuard popup loaded");
  
  // Check backend health immediately
  checkBackendHealth();
  
  // Refresh stats
  refreshStats();
  
  // Focus on input
  payloadInput.focus();
  
  // Check health every 10 seconds
  setInterval(checkBackendHealth, 10000);
});

// Allow Ctrl+Enter to submit from textarea
payloadInput.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") {
    scanBtn.click();
  }
});

// Enter key in context input triggers scan
contextInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    scanBtn.click();
  }
});
