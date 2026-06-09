import { uploadPDF, checkHealth } from "../api";

export interface SidebarCallbacks {
  onUploaded: (filename: string) => void;
}

export function createSidebar(callbacks: SidebarCallbacks): HTMLElement {
  const aside = document.createElement("aside");
  aside.className = "sidebar";

  // ── Branding ───────────────────────────────────────────────────────────────
  const brand = document.createElement("div");
  brand.className = "sidebar__brand";
  brand.innerHTML = `
    <div class="brand-row">
      <span class="brand-name">ManualIQ</span>
      <span class="badge badge--amber">RAG</span>
    </div>
    <p class="brand-sub">Technical manual assistant</p>
  `;
  aside.appendChild(brand);

  // ── Upload section ─────────────────────────────────────────────────────────
  const section = document.createElement("div");
  section.className = "sidebar__section";

  const sectionLabel = document.createElement("p");
  sectionLabel.className = "sidebar__label";
  sectionLabel.textContent = "Documents";
  section.appendChild(sectionLabel);

  // Drop zone
  const zone = document.createElement("div");
  zone.className = "upload-zone";
  zone.setAttribute("role", "button");
  zone.setAttribute("tabindex", "0");
  zone.setAttribute("aria-label", "Upload PDF — click or drop file here");

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = ".pdf";
  fileInput.style.display = "none";
  fileInput.setAttribute("aria-hidden", "true");

  const zoneIcon = document.createElement("i");
  zoneIcon.className = "ti ti-file-upload upload-zone__icon";
  zoneIcon.setAttribute("aria-hidden", "true");

  const zoneText = document.createElement("span");
  zoneText.className = "upload-zone__text";
  zoneText.textContent = "Drop a PDF or click to browse";

  zone.appendChild(fileInput);
  zone.appendChild(zoneIcon);
  zone.appendChild(zoneText);

  // File list
  const fileList = document.createElement("div");
  fileList.className = "file-list";

  const setUploading = (active: boolean) => {
    zone.classList.toggle("upload-zone--loading", active);
    zoneText.textContent = active ? "Indexing…" : "Drop a PDF or click to browse";
    zoneIcon.className = active
      ? "ti ti-loader-2 upload-zone__icon upload-zone__icon--spin"
      : "ti ti-file-upload upload-zone__icon";
  };

  const handleFile = async (file: File) => {
    if (!file || file.type !== "application/pdf") {
      alert("Only PDF files are supported.");
      return;
    }
    setUploading(true);
    try {
      const data = await uploadPDF(file);
      appendFileItem(data.file);
      callbacks.onUploaded(data.file);
    } catch (err) {
      console.error(err);
      alert("Upload failed. Check that the API is running.");
    } finally {
      setUploading(false);
    }
  };

  const appendFileItem = (filename: string) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <i class="ti ti-file-text file-item__icon" aria-hidden="true"></i>
      <span class="file-item__name" title="${filename}">${filename}</span>
      <i class="ti ti-check file-item__check" aria-hidden="true"></i>
    `;
    fileList.appendChild(item);
  };

  zone.addEventListener("click", () => fileInput.click());
  zone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
  });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("upload-zone--drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("upload-zone--drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("upload-zone--drag");
    const file = e.dataTransfer?.files[0];
    if (file) handleFile(file);
  });
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) handleFile(file);
    fileInput.value = "";
  });

  section.appendChild(zone);
  section.appendChild(fileList);
  aside.appendChild(section);

  // ── Status ─────────────────────────────────────────────────────────────────
  const statusBar = document.createElement("div");
  statusBar.className = "sidebar__status";
  statusBar.innerHTML = `
    <span class="status-dot status-dot--checking" id="status-dot"></span>
    <span class="status-text" id="status-text">Checking API…</span>
  `;
  aside.appendChild(statusBar);

  // Health check
  checkHealth()
    .then(() => {
      const dot = aside.querySelector<HTMLSpanElement>("#status-dot")!;
      const txt = aside.querySelector<HTMLSpanElement>("#status-text")!;
      dot.className = "status-dot status-dot--ok";
      txt.textContent = "API online";
    })
    .catch(() => {
      const dot = aside.querySelector<HTMLSpanElement>("#status-dot")!;
      const txt = aside.querySelector<HTMLSpanElement>("#status-text")!;
      dot.className = "status-dot status-dot--error";
      txt.textContent = "API unreachable";
    });

  return aside;
}