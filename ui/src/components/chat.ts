import type { Message } from "../types";
import { createAnswerBlock } from "./answerBlock";

export function createChat(): { el: HTMLElement; appendMessage: (msg: Message) => void; setLoading: (v: boolean) => void } {
  const el = document.createElement("div");
  el.className = "chat";
  el.setAttribute("role", "log");
  el.setAttribute("aria-live", "polite");
  el.setAttribute("aria-label", "Conversation");

  // Empty state
  const empty = document.createElement("div");
  empty.className = "chat__empty";
  empty.innerHTML = `
    <i class="ti ti-manual-gearbox chat__empty-icon" aria-hidden="true"></i>
    <p>Upload a manual and ask a question to get started.</p>
  `;
  el.appendChild(empty);

  // Loading indicator
  const loadingEl = document.createElement("div");
  loadingEl.className = "chat__loading";
  loadingEl.hidden = true;
  loadingEl.setAttribute("aria-label", "Waiting for answer");
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.className = "loading-dot";
    dot.style.animationDelay = `${i * 0.2}s`;
    loadingEl.appendChild(dot);
  }

  const scrollAnchor = document.createElement("div");
  scrollAnchor.setAttribute("aria-hidden", "true");

  const scrollToBottom = () => {
    scrollAnchor.scrollIntoView({ behavior: "smooth" });
  };

  const appendMessage = (msg: Message) => {
    // Remove empty state on first message
    if (empty.parentNode) el.removeChild(empty);

    const wrapper = document.createElement("div");
    wrapper.className = `message message--${msg.role}`;

    if (msg.role === "user") {
      const bubble = document.createElement("div");
      bubble.className = "message__bubble message__bubble--user";
      bubble.textContent = msg.text ?? "";
      wrapper.appendChild(bubble);
    } else if (msg.role === "assistant") {
      const bubble = document.createElement("div");
      bubble.className = "message__bubble message__bubble--assistant";
      bubble.appendChild(createAnswerBlock(msg));
      wrapper.appendChild(bubble);
    } else if (msg.role === "error") {
      const bubble = document.createElement("div");
      bubble.className = "message__bubble message__bubble--error";
      bubble.innerHTML = `<i class="ti ti-alert-triangle" aria-hidden="true" style="margin-right:6px"></i>${msg.text ?? "Unknown error"}`;
      wrapper.appendChild(bubble);
    }

    // Insert before loading indicator
    if (loadingEl.parentNode) {
      el.insertBefore(wrapper, loadingEl);
    } else {
      el.insertBefore(wrapper, scrollAnchor);
    }

    scrollToBottom();
  };

  const setLoading = (active: boolean) => {
    loadingEl.hidden = !active;
    if (active) {
      if (!loadingEl.parentNode) el.insertBefore(loadingEl, scrollAnchor);
      scrollToBottom();
    } else {
      loadingEl.parentNode?.removeChild(loadingEl);
    }
  };

  el.appendChild(scrollAnchor);

  return { el, appendMessage, setLoading };
}