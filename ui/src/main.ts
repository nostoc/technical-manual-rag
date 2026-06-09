import { createSidebar } from "./components/sidebar";
import { createChat } from "./components/chat";
import { createInput } from "./components/input";
import { queryRAG } from "./api";

const root = document.querySelector<HTMLDivElement>("#app")!;
root.className = "app-shell";

// ── Build layout ─────────────────────────────────────────────────────────────

const { el: chatEl, appendMessage, setLoading } = createChat();

const { el: inputEl, setDisabled } = createInput({
  onSubmit: async (query) => {
    appendMessage({ role: "user", text: query });
    setDisabled(true);
    setLoading(true);

    try {
      const data = await queryRAG(query);
      setLoading(false);
      appendMessage({ role: "assistant", ...data });
    } catch (err) {
      setLoading(false);
      const msg = err instanceof Error ? err.message : "Unexpected error";
      appendMessage({ role: "error", text: msg });
    } finally {
      setDisabled(false);
    }
  },
});

const sidebar = createSidebar({
  onUploaded: (_filename) => {
    // Future: could show a toast or auto-trigger a suggested query
  },
});

// ── Main panel ───────────────────────────────────────────────────────────────

const main = document.createElement("main");
main.className = "main-panel";

const header = document.createElement("header");
header.className = "main-panel__header";
header.innerHTML = `
  <i class="ti ti-robot" aria-hidden="true"></i>
  <span>Ask questions about your uploaded manuals — sources and tables shown for every answer.</span>
`;

main.appendChild(header);
main.appendChild(chatEl);
main.appendChild(inputEl);

root.appendChild(sidebar);
root.appendChild(main);