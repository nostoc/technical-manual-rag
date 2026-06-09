export interface InputCallbacks {
  onSubmit: (query: string) => void;
}

export function createInput(callbacks: InputCallbacks): { el: HTMLElement; setDisabled: (v: boolean) => void } {
  const el = document.createElement("div");
  el.className = "input-bar";

  const inner = document.createElement("div");
  inner.className = "input-bar__inner";

  const textarea = document.createElement("textarea");
  textarea.className = "input-bar__textarea";
  textarea.placeholder = "e.g. What is the torque spec for the main shaft bearing?";
  textarea.rows = 1;
  textarea.setAttribute("aria-label", "Query");
  textarea.setAttribute("autocomplete", "off");
  textarea.setAttribute("spellcheck", "false");

  const sendBtn = document.createElement("button");
  sendBtn.className = "input-bar__send";
  sendBtn.setAttribute("aria-label", "Send query");
  sendBtn.innerHTML = `<i class="ti ti-arrow-up" aria-hidden="true"></i>`;

  // Auto-resize textarea
  const resize = () => {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
  };
  textarea.addEventListener("input", resize);

  const getQuery = () => textarea.value.trim();

  const updateSendState = () => {
    const hasContent = getQuery().length > 0;
    sendBtn.classList.toggle("input-bar__send--active", hasContent);
    sendBtn.disabled = !hasContent;
  };

  textarea.addEventListener("input", updateSendState);

  const submit = () => {
    const q = getQuery();
    if (!q) return;
    callbacks.onSubmit(q);
    textarea.value = "";
    textarea.style.height = "auto";
    updateSendState();
    textarea.focus();
  };

  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) submit();
    }
  });

  sendBtn.addEventListener("click", submit);
  sendBtn.disabled = true;

  inner.appendChild(textarea);
  inner.appendChild(sendBtn);

  const hint = document.createElement("p");
  hint.className = "input-bar__hint";
  hint.textContent = "Enter to send · Shift+Enter for new line";

  el.appendChild(inner);
  el.appendChild(hint);

  const setDisabled = (disabled: boolean) => {
    textarea.disabled = disabled;
    sendBtn.disabled = disabled || getQuery().length === 0;
    sendBtn.classList.toggle("input-bar__send--active", !disabled && getQuery().length > 0);
  };

  return { el, setDisabled };
}