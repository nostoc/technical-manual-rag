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

  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  table.headers.forEach((h) => {
    const th = document.createElement("th");
    th.textContent = h;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  tbl.appendChild(thead);

  const tbody = document.createElement("tbody");
  table.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell) => {
      const td = document.createElement("td");
      td.textContent = cell;
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

type TabKey = "answer" | "tables" | "images" | "sources";

export function createAnswerBlock(msg: Message): HTMLElement {
  const block = document.createElement("div");
  block.className = "answer-block";

  const hasImages = (msg.images?.length ?? 0) > 0;
  const hasTables = (msg.tables?.length ?? 0) > 0;
  const hasSources = (msg.sources?.length ?? 0) > 0;

  const tabs: { key: TabKey; label: string }[] = [
    { key: "answer", label: "Answer" },
    ...(hasTables ? [{ key: "tables" as TabKey, label: `Tables (${msg.tables!.length})` }] : []),
    ...(hasImages ? [{ key: "images" as TabKey, label: `Images (${msg.images!.length})` }] : []),
    ...(hasSources ? [{ key: "sources" as TabKey, label: `Sources (${msg.sources!.length})` }] : []),
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
  answerText.textContent = msg.answer ?? "";
  answerPanel.appendChild(answerText);
  panels.set("answer", answerPanel);

  // Tables panel
  if (hasTables) {
    const tp = document.createElement("div");
    tp.className = "tab-panel";
    tp.setAttribute("role", "tabpanel");
    msg.tables!.forEach((t) => tp.appendChild(createDataTable(t)));
    panels.set("tables", tp);
  }

  // Images panel
  if (hasImages) {
    const ip = document.createElement("div");
    ip.className = "tab-panel";
    ip.setAttribute("role", "tabpanel");
    const grid = document.createElement("div");
    grid.className = "image-grid";
    msg.images!.forEach((src, i) => {
      const a = document.createElement("a");
      a.href = `${API_BASE}${src}`;
      a.target = "_blank";
      a.rel = "noreferrer";
      const img = document.createElement("img");
      img.src = `${API_BASE}${src}`;
      img.alt = `Figure ${i + 1}`;
      img.className = "result-image";
      a.appendChild(img);
      grid.appendChild(a);
    });
    ip.appendChild(grid);
    panels.set("images", ip);
  }

  // Sources panel
  if (hasSources) {
    const sp = document.createElement("div");
    sp.className = "tab-panel";
    sp.setAttribute("role", "tabpanel");
    msg.sources!.forEach((s) => sp.appendChild(createSourceCard(s)));
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