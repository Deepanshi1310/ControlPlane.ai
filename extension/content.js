/**
 * ControlPlane.ai - Main Content Script Coordinator
 * Routes extraction to modular adapters (ChatGPT, Generic fallback).
 */

const ADAPTERS = [
  window.ChatGPTAdapter,
  window.GenericAdapter
].filter(Boolean);

function performDetection() {
  const currentUrl = window.location.href || "";

  // Check website-specific adapters first
  for (const adapter of ADAPTERS) {
    if (adapter.name !== "generic" && adapter.isMatch(currentUrl)) {
      const result = adapter.extract();
      if (result && (result.response || result.query)) {
        return {
          ...result,
          url: currentUrl,
          pageTitle: document.title || ""
        };
      }
    }
  }

  // Fallback to generic adapter
  if (window.GenericAdapter) {
    const genericResult = window.GenericAdapter.extract();
    return {
      ...genericResult,
      url: currentUrl,
      pageTitle: document.title || ""
    };
  }

  const selection = window.getSelection() ? window.getSelection().toString().trim() : "";
  return {
    detected: selection.length > 0,
    source: "Selection",
    query: "",
    response: selection,
    url: currentUrl,
    pageTitle: document.title || ""
  };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "AUTO_DETECT" || request.action === "GET_SELECTED_TEXT") {
    const detection = performDetection();
    sendResponse({
      selectedText: detection.response || "",
      query: detection.query || "",
      source: detection.source || "Webpage",
      detected: detection.detected || false,
      pageTitle: detection.pageTitle || "",
      url: detection.url || ""
    });
  }
  return true;
});
