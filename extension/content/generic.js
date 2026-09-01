/**
 * ControlPlane.ai - Generic Content Adapter
 * Handles fallback text selection and generic DOM extraction on any webpage.
 */

const GenericAdapter = {
  name: "generic",

  isMatch: (url) => {
    return true; // Catch-all fallback
  },

  extract: () => {
    const selection = window.getSelection() ? window.getSelection().toString().trim() : "";
    return {
      detected: selection.length > 0,
      source: "Selection",
      query: "",
      response: selection
    };
  }
};

window.GenericAdapter = GenericAdapter;
