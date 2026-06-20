// components/answerBlock.ts
import type { Message, SourceNode, TableData } from "../types";
import { API_BASE } from "../api";

// ── Signal bars (retrieval score visualiser) ─────────────────────────────────

function createSignalBars(score: number | null): HTMLElement {
  const wrap = document.createElement("span");
  wrap.className = "signal-bars";

  const pct = score != null ? Math.round(score * 100) : null;
  const filled = pct != null ? Math.round((pct / 100) * 5) : 0;

  for (let i = 0; i < 5; i++) {
    const bar = document.createElement("span");
    bar.className = "signal-bar" + (i < filled ? " signal-bar--active" : "");
    bar.style.height = `${4 + i * 2}px`;
    wrap.appendChild(bar);
  }

  if (pct != null) {
    const label = document.createElement("span");
    label.className = "signal-pct";
    label.textContent = `${pct}%`;
    wrap.appendChild(label);
  }

  return wrap;
}

// ── Source card ──────────────────────────────────────────────────────────────

function createSourceCard(source: SourceNode): HTMLElement {
  const card = document.createElement("div");
  card.className = `source-card ${source.type === "table_summary" ? "source-card--table" : ""}`;

  const header = document.createElement("div");
  header.className = "source-card__header";
  header.setAttribute("role", "button");
  header.setAttribute("tabindex", "0");
  header.setAttribute("aria-expanded", "false");

  header.appendChild(createSignalBars(source.score));

  const fname = document.createElement("span");
  fname.className = "source-card__filename";
  fname.textContent = source.file_name;
  header.appendChild(fname);

  if (source.page !== "") {
    const pg = document.createElement("span");
    pg.className = "badge badge--neutral";
    pg.textContent = `p.${source.page}`;
    header.appendChild(pg);
  }

  if (source.type === "table_summary") {
    const tb = document.createElement("span");
    tb.className = "badge badge--amber";
    tb.textContent = "table";
    header.appendChild(tb);
  }

  const chevron = document.createElement("i");
  chevron.className = "ti ti-chevron-down source-card__chevron";
  chevron.setAttribute("aria-hidden", "true");
  header.appendChild(chevron);

  const body = document.createElement("div");
  body.className = "source-card__body";
  body.hidden = true;
  body.textContent = source.snippet;

  const toggle = () => {
    const expanded = !body.hidden;
    body.hidden = expanded;
    chevron.style.transform = expanded ? "" : "rotate(180deg)";
    header.setAttribute("aria-expanded", String(!expanded));
  };

  header.addEventListener("click", toggle);
  header.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
  });

  card.appendChild(header);
  card.appendChild(body);
  return card;
}

// ── Data table ───────────────────────────────────────────────────────────────

function createDataTable(table: TableData): HTMLElement {
  const wrap = document.createElement("div");
  wrap.className = "data-table-wrap";

  const meta = document.createElement("div");
  meta.className = "data-table__meta";
  meta.textContent = `${table.file_name} · p.${table.page} · table ${table.table_index + 1}`;
  wrap.appendChild(meta);

  const scroll = document.createElement("div");
  scroll.className = "data-table__scroll";

  const tbl = document.createElement("table");
  tbl.className = "data-table";

  // Backend returns col_names (array of strings) and rows (array of dicts)
  const colNames: string[] = table.col_names ?? [];

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  colNames.forEach((h) => {
    const th = document.createElement("th");
    th.textContent = h;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  tbl.appendChild(thead);

  const tbody = document.createElement("tbody");
  // Each row is a dict keyed by column name; preserve column order via colNames
  (table.rows as Record<string, string>[]).forEach((rowDict) => {
    const tr = document.createElement("tr");
    colNames.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = rowDict[col] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);

  scroll.appendChild(tbl);
  wrap.appendChild(scroll);
  return wrap;
}

// ── Answer block (tabs) ──────────────────────────────────────────────────────

type TabKey = "answer" | "tables" | "sources";

export function createAnswerBlock(msg: Message): HTMLElement {
  const block = document.createElement("div");
  block.className = "answer-block";

  const hasImages = (msg.images?.length ?? 0) > 0;
  const hasTables = (msg.tables?.length ?? 0) > 0;
  const filteredSources = (msg.sources ?? []).filter((s) => s.score != null && s.score >= 0.2);
  const hasSources = filteredSources.length > 0;

  const tabs: { key: TabKey; label: string }[] = [
    { key: "answer", label: "Answer" },
    ...(hasTables ? [{ key: "tables" as TabKey, label: `Tables (${msg.tables!.length})` }] : []),
    ...(hasSources ? [{ key: "sources" as TabKey, label: `Sources (${filteredSources.length})` }] : []),
  ];

  // Tab bar
  const tabBar = document.createElement("div");
  tabBar.className = "tab-bar";
  tabBar.setAttribute("role", "tablist");

  // Panels
  const panels = new Map<TabKey, HTMLElement>();

  // Answer panel
  const answerPanel = document.createElement("div");
  answerPanel.className = "tab-panel";
  answerPanel.setAttribute("role", "tabpanel");
  const answerText = document.createElement("p");
  answerText.className = "answer-text";

  const formatAnswerText = (text: string) => {
    const t = text ?? "";
    const esc = t
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
    return esc.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  };

  answerText.innerHTML = formatAnswerText(msg.answer ?? "");
  answerPanel.appendChild(answerText);

  // Append images to the answer panel directly below the text
  if (hasImages) {
    const section = document.createElement("div");
    section.className = "answer-images-section";

    const title = document.createElement("div");
    title.className = "answer-images-title";
    title.innerHTML = `<i class="ti ti-photo" aria-hidden="true"></i> <span>Related Figures (${msg.images!.length})</span>`;
    section.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "image-grid";

    msg.images!.forEach((src, i) => {
      const url = `${API_BASE}${src}`;
      
      const wrapper = document.createElement("div");
      wrapper.className = "image-card-wrapper";

      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.setAttribute("aria-label", `View Figure ${i + 1} in full size`);

      const img = document.createElement("img");
      img.src = url;
      img.alt = `Figure ${i + 1}`;
      img.className = "result-image";
      
      const caption = document.createElement("div");
      caption.className = "image-caption";
      caption.textContent = `Figure ${i + 1}`;

      a.appendChild(img);
      wrapper.appendChild(a);
      wrapper.appendChild(caption);
      grid.appendChild(wrapper);
    });

    section.appendChild(grid);
    answerPanel.appendChild(section);
  }

  panels.set("answer", answerPanel);

  // Tables panel
  if (hasTables) {
    const tp = document.createElement("div");
    tp.className = "tab-panel";
    tp.setAttribute("role", "tabpanel");
    msg.tables!.forEach((t) => tp.appendChild(createDataTable(t)));
    panels.set("tables", tp);
  }

  // Sources panel
  if (hasSources) {
    const sp = document.createElement("div");
    sp.className = "tab-panel";
    sp.setAttribute("role", "tabpanel");
    filteredSources.forEach((s) => sp.appendChild(createSourceCard(s)));
    panels.set("sources", sp);
  }

  let activeTab: TabKey = "answer";
  const tabButtons = new Map<TabKey, HTMLButtonElement>();

  const switchTab = (key: TabKey) => {
    tabButtons.get(activeTab)?.classList.remove("tab-btn--active");
    panels.get(activeTab)!.hidden = true;
    activeTab = key;
    tabButtons.get(activeTab)?.classList.add("tab-btn--active");
    panels.get(activeTab)!.hidden = false;
  };

  tabs.forEach(({ key, label }) => {
    const btn = document.createElement("button");
    btn.className = "tab-btn" + (key === "answer" ? " tab-btn--active" : "");
    btn.textContent = label;
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", String(key === "answer"));
    btn.addEventListener("click", () => switchTab(key));
    tabButtons.set(key, btn);
    tabBar.appendChild(btn);
  });

  block.appendChild(tabBar);

  panels.forEach((panel, key) => {
    panel.hidden = key !== "answer";
    block.appendChild(panel);
  });

  return block;
}