/**
 * ControlPlane.ai Extension - Advanced Popup Logic (Phase 5 Polish)
 * Features: Auto-detection, live Wikipedia verification, history cache, expandable claims, copy report.
 */

const API_BASE_URL = "http://localhost:8000";
const HISTORY_KEY = "controlplane_verification_history";
const MAX_HISTORY = 10;

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const queryInput = document.getElementById("query-input");
  const responseInput = document.getElementById("response-input");
  const getSelectionBtn = document.getElementById("get-selection-btn");
  const verifyBtn = document.getElementById("verify-btn");
  
  const loadingContainer = document.getElementById("loading-container");
  const errorContainer = document.getElementById("error-container");
  const errorMessage = document.getElementById("error-message");
  const errorRetryBtn = document.getElementById("error-retry-btn");
  const resultsContainer = document.getElementById("results-container");

  const detectedBanner = document.getElementById("detected-banner");
  const detectedText = document.getElementById("detected-text");
  const dismissDetectionBtn = document.getElementById("dismiss-detection-btn");

  const tabVerify = document.getElementById("tab-verify");
  const tabHistory = document.getElementById("tab-history");
  const verifyView = document.getElementById("verify-view");
  const historyView = document.getElementById("history-view");
  const historyList = document.getElementById("history-list");
  const clearHistoryBtn = document.getElementById("clear-history-btn");
  const copyReportBtn = document.getElementById("copy-report-btn");

  let lastEvaluationResult = null;

  // Initial Detection
  grabSelectedText();

  // Tab Switching
  tabVerify.addEventListener("click", () => switchTab("verify"));
  tabHistory.addEventListener("click", () => {
    switchTab("history");
    renderHistoryList();
  });

  function switchTab(tab) {
    if (tab === "verify") {
      tabVerify.classList.add("active");
      tabHistory.classList.remove("active");
      verifyView.classList.remove("hidden");
      historyView.classList.add("hidden");
    } else {
      tabHistory.classList.add("active");
      tabVerify.classList.remove("active");
      historyView.classList.remove("hidden");
      verifyView.classList.add("hidden");
    }
  }

  // Dismiss auto-detection banner
  if (dismissDetectionBtn) {
    dismissDetectionBtn.addEventListener("click", () => {
      detectedBanner.classList.add("hidden");
    });
  }

  // Grab selection button click
  getSelectionBtn.addEventListener("click", () => {
    grabSelectedText();
  });

  // Verify button click
  verifyBtn.addEventListener("click", () => {
    performVerification();
  });

  // Retry button click
  errorRetryBtn.addEventListener("click", () => {
    performVerification();
  });

  // Clear history click
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", () => {
      clearHistory();
    });
  }

  // Copy report click
  if (copyReportBtn) {
    copyReportBtn.addEventListener("click", () => {
      copyVerificationReport();
    });
  }

  /**
   * Request auto-detection or selected text from the active tab.
   */
  async function grabSelectedText() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab || !tab.id) return;

      chrome.tabs.sendMessage(tab.id, { action: "AUTO_DETECT" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          executeScriptFallback(tab.id);
        } else {
          if (response.selectedText) {
            responseInput.value = response.selectedText;
          }
          if (response.query) {
            queryInput.value = response.query;
          }
          if (response.detected && response.source && response.source !== "Selection") {
            detectedText.textContent = `Auto-detected from ${response.source}`;
            detectedBanner.classList.remove("hidden");
          } else {
            detectedBanner.classList.add("hidden");
          }
        }
      });
    } catch (err) {
      console.warn("Could not perform auto-detection:", err);
    }
  }

  /**
   * Fallback to executeScript if content script wasn't active.
   */
  async function executeScriptFallback(tabId) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: () => window.getSelection() ? window.getSelection().toString().trim() : ""
      });
      if (results && results[0] && results[0].result) {
        responseInput.value = results[0].result;
      }
    } catch (err) {
      console.warn("Scripting fallback failed:", err);
    }
  }

  /**
   * Send evaluation request to the ControlPlane FastAPI backend.
   */
  async function performVerification() {
    const query = queryInput.value.trim();
    const responseText = responseInput.value.trim();

    if (!responseText) {
      showError("Please select an AI response to verify or paste text into the field.");
      return;
    }

    showLoading();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 20000);

      const res = await fetch(`${API_BASE_URL}/api/v1/evaluation/evaluate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          query: query || "Fact-check statement",
          response: responseText
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}: ${res.statusText}`);
      }

      const data = await res.json();
      lastEvaluationResult = { query: query || "Statement", response: responseText, data, timestamp: new Date().toISOString() };
      
      saveToHistory(lastEvaluationResult);
      renderResults(data);

    } catch (err) {
      console.error("Verification error:", err);
      if (err.name === "AbortError") {
        showError("Verification timed out. Wikipedia search took too long.");
      } else if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
        showError("Cannot connect to ControlPlane backend at http://localhost:8000. Please ensure the server is running.");
      } else {
        showError(err.message || "An unexpected error occurred during verification.");
      }
    }
  }

  /**
   * Render evaluation response from the backend.
   */
  function renderResults(data) {
    hideLoading();
    hideError();

    const decision = data.decision || {};
    const performance = data.performance || {};
    const factualVerification = performance.factual_verification || {};
    const verifiedClaims = factualVerification.verified_claims || [];

    // 1. Decision Banner
    const actionEl = document.getElementById("decision-action");
    const riskEl = document.getElementById("decision-risk");
    const reasonEl = document.getElementById("decision-reason");
    const factualityEl = document.getElementById("factuality-percentage");

    const action = decision.action || "ALLOW";
    const risk = decision.risk_level || "LOW";

    actionEl.textContent = action;
    actionEl.className = `badge badge-action ${getActionBadgeClass(action)}`;

    riskEl.textContent = `${risk} RISK`;
    riskEl.className = `badge badge-risk ${getRiskBadgeClass(risk)}`;

    reasonEl.innerHTML = parseMarkdownLinks(decision.reason || "Response evaluated.");

    const factScore = performance.factuality !== undefined && performance.factuality !== null
      ? Math.round(performance.factuality * 100)
      : null;
    factualityEl.textContent = factScore !== null ? `${factScore}%` : "N/A";

    // 2. Metrics Counter
    document.getElementById("metric-claims-count").textContent = factualVerification.total_claims || verifiedClaims.length || 0;
    document.getElementById("metric-supported-count").textContent = factualVerification.supported_claims || 0;
    document.getElementById("metric-contradicted-count").textContent = factualVerification.contradicted_claims || 0;
    document.getElementById("metric-unverified-count").textContent = factualVerification.insufficient_evidence_claims || 0;

    // 3. Claims List
    const claimsContainer = document.getElementById("claims-list");
    claimsContainer.innerHTML = "";

    if (verifiedClaims.length === 0) {
      claimsContainer.innerHTML = `<div class="hint-text" style="text-align: center; padding: 12px;">No discrete factual claims identified.</div>`;
    } else {
      verifiedClaims.forEach((claimObj, idx) => {
        const card = createClaimCard(claimObj, idx);
        claimsContainer.appendChild(card);
      });
    }

    resultsContainer.classList.remove("hidden");
  }

  /**
   * Create an interactive, expandable claim card element with confidence bar.
   */
  function createClaimCard(claimObj, index) {
    const card = document.createElement("div");
    const status = claimObj.status || "INSUFFICIENT_EVIDENCE";
    card.className = `claim-card status-${status}`;

    const statusLabel = status.replace("_", " ");
    const confPercent = claimObj.confidence ? Math.round(claimObj.confidence * 100) : 0;

    let barColor = "var(--color-info)";
    if (status === "SUPPORTED") barColor = "var(--color-success)";
    if (status === "CONTRADICTED") barColor = "var(--color-danger)";
    if (status === "INSUFFICIENT_EVIDENCE") barColor = "var(--color-warning)";

    card.innerHTML = `
      <div class="claim-top" title="Click to toggle details">
        <span class="claim-text">${escapeHtml(claimObj.claim)}</span>
        <div class="claim-badges">
          <span class="claim-badge badge-${status}">${statusLabel}</span>
          <span class="toggle-icon">▼</span>
        </div>
      </div>
      ${claimObj.evidence ? `<div class="evidence-box">"${escapeHtml(claimObj.evidence)}"</div>` : ""}
      <div class="claim-footer">
        <div class="source-tag">
          ${claimObj.wikipedia_title ? `<span>Source: <strong>${escapeHtml(claimObj.wikipedia_title)}</strong></span>` : "<span>No Wikipedia match</span>"}
        </div>
        <div class="confidence-bar-wrap" title="Confidence: ${confPercent}%">
          <div class="confidence-bar">
            <div class="confidence-fill" style="width: ${confPercent}%; background-color: ${barColor};"></div>
          </div>
          <span>${confPercent}%</span>
        </div>
        ${claimObj.wikipedia_url ? `
          <button class="view-source-btn" data-url="${escapeHtml(claimObj.wikipedia_url)}">
            <span>View Source ↗</span>
          </button>
        ` : ""}
      </div>
    `;

    // Toggle expand / collapse on claim-top click
    const topEl = card.querySelector(".claim-top");
    topEl.addEventListener("click", () => {
      card.classList.toggle("collapsed");
    });

    // Attach click event to View Source button
    const viewBtn = card.querySelector(".view-source-btn");
    if (viewBtn) {
      viewBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const url = viewBtn.getAttribute("data-url");
        if (url) {
          chrome.tabs.create({ url });
        }
      });
    }

    return card;
  }

  /**
   * Save a completed verification to storage history.
   */
  function saveToHistory(item) {
    try {
      chrome.storage.local.get([HISTORY_KEY], (res) => {
        let history = res[HISTORY_KEY] || [];
        // Add to top and cap
        history.unshift(item);
        if (history.length > MAX_HISTORY) {
          history = history.slice(0, MAX_HISTORY);
        }
        chrome.storage.local.set({ [HISTORY_KEY]: history });
      });
    } catch (e) {
      console.warn("Storage history save failed:", e);
    }
  }

  /**
   * Render history list items.
   */
  function renderHistoryList() {
    try {
      chrome.storage.local.get([HISTORY_KEY], (res) => {
        const history = res[HISTORY_KEY] || [];
        historyList.innerHTML = "";

        if (history.length === 0) {
          historyList.innerHTML = `<div class="hint-text" style="text-align: center; padding: 24px;">No recent verifications yet.</div>`;
          return;
        }

        history.forEach((item, idx) => {
          const el = document.createElement("div");
          el.className = "history-item";

          const decision = item.data?.decision || {};
          const action = decision.action || "ALLOW";
          const date = item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

          el.innerHTML = `
            <div class="history-item-top">
              <span class="history-query">${escapeHtml(item.query)}</span>
              <span class="badge ${getActionBadgeClass(action)}">${action}</span>
            </div>
            <p class="history-response">${escapeHtml(item.response)}</p>
            <div class="history-item-top" style="margin-top: 2px;">
              <span class="history-time">${date}</span>
              <span class="text-btn" style="font-size: 10px;">Load →</span>
            </div>
          `;

          el.addEventListener("click", () => {
            queryInput.value = item.query || "";
            responseInput.value = item.response || "";
            renderResults(item.data);
            switchTab("verify");
          });

          historyList.appendChild(el);
        });
      });
    } catch (e) {
      console.warn("Could not load history:", e);
    }
  }

  /**
   * Clear stored history.
   */
  function clearHistory() {
    try {
      chrome.storage.local.remove([HISTORY_KEY], () => {
        renderHistoryList();
      });
    } catch (e) {
      console.warn("Could not clear history:", e);
    }
  }

  /**
   * Copy formatted markdown report to clipboard.
   */
  function copyVerificationReport() {
    if (!lastEvaluationResult) return;

    const { query, response, data } = lastEvaluationResult;
    const decision = data.decision || {};
    const performance = data.performance || {};
    const claims = performance.factual_verification?.verified_claims || [];

    let report = `## ControlPlane.ai Verification Report\n\n`;
    report += `**Query:** ${query}\n`;
    report += `**Decision:** ${decision.action} (${decision.risk_level} RISK)\n`;
    report += `**Factuality Score:** ${performance.factuality !== null ? Math.round(performance.factuality * 100) + "%" : "N/A"}\n`;
    report += `**Reason:** ${decision.reason}\n\n`;
    report += `### Verified Claims:\n`;

    claims.forEach((c, idx) => {
      report += `${idx + 1}. **[${c.status}]** ${c.claim}\n`;
      if (c.wikipedia_title && c.wikipedia_url) {
        report += `   - Source: [${c.wikipedia_title}](${c.wikipedia_url})\n`;
      }
      if (c.evidence) {
        report += `   - Evidence: "${c.evidence}"\n`;
      }
    });

    navigator.clipboard.writeText(report).then(() => {
      const origText = copyReportBtn.innerHTML;
      copyReportBtn.innerHTML = `<span>✓ Copied!</span>`;
      setTimeout(() => {
        copyReportBtn.innerHTML = origText;
      }, 2000);
    });
  }

  function showLoading() {
    loadingContainer.classList.remove("hidden");
    errorContainer.classList.add("hidden");
    resultsContainer.classList.add("hidden");
    verifyBtn.disabled = true;
    verifyBtn.style.opacity = "0.7";
  }

  function hideLoading() {
    loadingContainer.classList.add("hidden");
    verifyBtn.disabled = false;
    verifyBtn.style.opacity = "1";
  }

  function showError(msg) {
    hideLoading();
    resultsContainer.classList.add("hidden");
    errorMessage.textContent = msg;
    errorContainer.classList.remove("hidden");
  }

  function hideError() {
    errorContainer.classList.add("hidden");
  }

  function getActionBadgeClass(action) {
    if (action === "ALLOW") return "badge-action";
    if (action === "BLOCK" || action === "REDACT") return "danger";
    return "warning";
  }

  function getRiskBadgeClass(risk) {
    if (risk === "LOW") return "";
    if (risk === "CRITICAL" || risk === "HIGH") return "danger";
    return "warning";
  }

  function parseMarkdownLinks(text) {
    if (!text) return "";
    return text.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, (match, title, url) => {
      return `<a href="#" data-url="${escapeHtml(url)}" class="wiki-link">${escapeHtml(title)}</a>`;
    });
  }

  // Delegated listener for markdown wiki links in decision reason
  document.addEventListener("click", (e) => {
    if (e.target && e.target.classList.contains("wiki-link")) {
      e.preventDefault();
      const url = e.target.getAttribute("data-url");
      if (url) {
        chrome.tabs.create({ url });
      }
    }
  });

  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
});
