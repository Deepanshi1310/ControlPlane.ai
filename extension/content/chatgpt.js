/**
 * ControlPlane.ai - ChatGPT Content Adapter
 * Automatically detects and extracts the latest User Query and AI Response from ChatGPT.
 */

const ChatGPTAdapter = {
  name: "ChatGPT",

  isMatch: (url) => {
    return url.includes("chatgpt.com") || url.includes("chat.openai.com");
  },

  extract: () => {
    try {
      // 1. Check if user highlighted a specific piece of text first (manual selection priority)
      const selection = window.getSelection() ? window.getSelection().toString().trim() : "";
      
      // 2. Select all assistant turns on page
      const assistantMessages = document.querySelectorAll(
        '[data-message-author-role="assistant"], div.agent-turn, div[data-testid^="conversation-turn-"] .markdown'
      );

      // 3. Select all user turns on page
      const userMessages = document.querySelectorAll(
        '[data-message-author-role="user"], div.user-turn, div[data-message-id] [data-message-author-role="user"]'
      );

      let extractedQuery = "";
      let extractedResponse = "";

      if (assistantMessages.length > 0) {
        const lastAssistant = assistantMessages[assistantMessages.length - 1];
        // Clean markdown prose text
        extractedResponse = lastAssistant.innerText ? lastAssistant.innerText.trim() : "";
      }

      if (userMessages.length > 0) {
        const lastUser = userMessages[userMessages.length - 1];
        extractedQuery = lastUser.innerText ? lastUser.innerText.trim() : "";
      }

      // If user has highlighted specific text, use it as the target response
      if (selection.length > 0) {
        return {
          detected: true,
          source: "ChatGPT (Selection)",
          query: extractedQuery,
          response: selection
        };
      }

      // If full assistant turn was found
      if (extractedResponse.length > 0) {
        return {
          detected: true,
          source: "ChatGPT",
          query: extractedQuery,
          response: extractedResponse
        };
      }

      return {
        detected: false,
        source: "ChatGPT",
        query: "",
        response: ""
      };

    } catch (e) {
      console.warn("ChatGPT adapter extraction error:", e);
      return {
        detected: false,
        source: "ChatGPT",
        query: "",
        response: ""
      };
    }
  }
};

window.ChatGPTAdapter = ChatGPTAdapter;
