async function loadManifest() {
  const response = await fetch("./generated/manifest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Manifest request failed with ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function badgeClass(value) {
  const key = String(value || "").toLowerCase();
  return `badge badge-${key.replace(/[^a-z0-9]+/g, "_")}`;
}

function summarizeManifest(manifest) {
  const cases = Array.isArray(manifest.cases) ? manifest.cases : [];
  return cases.reduce(
    (acc, item) => {
      acc.caseCount += 1;
      acc.findings += Number(item.findings_count || 0);
      acc.obligations += Number(item.obligations_count || 0);
      acc.alerts += Number(item.alerts_count || 0);
      acc.documents += Number(item.documents_count || 0);
      return acc;
    },
    { caseCount: 0, findings: 0, obligations: 0, alerts: 0, documents: 0 },
  );
}

function renderSignalStrip(manifest) {
  const summary = summarizeManifest(manifest);
  const generatedAt = manifest.generated_at
    ? new Date(manifest.generated_at).toLocaleString()
    : "Timestamp unavailable";

  const cards = [
    {
      eyebrow: "Corpus build",
      value: generatedAt,
      body: "Latest generated public artifact bundle published from the reference corpus.",
    },
    {
      eyebrow: "Demo coverage",
      value: `${summary.caseCount} case surfaces`,
      body: `${summary.documents} source documents represented across the public demo set.`,
    },
    {
      eyebrow: "Risk density",
      value: `${summary.findings} surfaced findings`,
      body: `${summary.obligations} obligations and ${summary.alerts} active alerts across generated artifacts.`,
    },
    {
      eyebrow: "Artifact mode",
      value: "External dashboards",
      body: "Client-safe readouts with internal strategy context deliberately suppressed.",
    },
  ];

  return cards.map((card) => `
    <article class="signal-card">
      <p class="eyebrow">${escapeHtml(card.eyebrow)}</p>
      <strong>${escapeHtml(card.value)}</strong>
      <p>${escapeHtml(card.body)}</p>
    </article>
  `).join("");
}

function renderCaseCard(item, index) {
  const article = document.createElement("article");
  article.className = "case-card";
  article.style.setProperty("--card-delay", `${index * 70}ms`);

  const highlights = Array.isArray(item.highlights) && item.highlights.length
    ? item.highlights
    : ["Prepared reference lifecycle snapshot."];

  const metrics = [
    ["Risk", titleize(item.overall_risk)],
    ["Findings", item.findings_count],
    ["Obligations", item.obligations_count],
    ["Alerts", item.alerts_count],
  ];

  article.innerHTML = `
    <div class="case-head">
      <div>
        <p class="case-kicker">${escapeHtml(titleize(item.analysis_perspective))} perspective</p>
        <h3>${escapeHtml(titleize(item.title || item.case_id))}</h3>
        <p class="case-slug">${escapeHtml(item.project_id || item.case_id || "")}</p>
      </div>
      <span class="${badgeClass(item.recommendation)}">${escapeHtml(titleize(item.recommendation))}</span>
    </div>
    <div class="case-stat-grid">
      ${metrics.map(([label, value]) => `
        <div class="case-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("")}
    </div>
    <ul class="highlight-list">
      ${highlights.map((highlight) => `<li>${escapeHtml(highlight)}</li>`).join("")}
    </ul>
    <div class="case-footer">
      <span class="case-footnote">${escapeHtml(Number(item.documents_count || 0))} documents indexed in this surface</span>
      <a class="button button-primary" href="${escapeHtml(item.dashboard_href)}">Open surface</a>
    </div>
  `;

  return article;
}

async function main() {
  const grid = document.getElementById("case-grid");
  const generatedAt = document.getElementById("generated-at");
  const heroGeneratedAt = document.getElementById("hero-generated-at");
  const heroCaseCount = document.getElementById("hero-case-count");
  const signalStrip = document.getElementById("signal-strip");

  try {
    const manifest = await loadManifest();
    const summary = summarizeManifest(manifest);
    const generatedLabel = manifest.generated_at
      ? `Generated ${new Date(manifest.generated_at).toLocaleString()}`
      : "Generated timestamp unavailable";

    generatedAt.textContent = generatedLabel;
    heroGeneratedAt.textContent = generatedLabel;
    heroCaseCount.textContent = `${summary.caseCount} case surface${summary.caseCount === 1 ? "" : "s"}`;
    signalStrip.innerHTML = renderSignalStrip(manifest);

    grid.innerHTML = "";
    const cases = Array.isArray(manifest.cases) ? manifest.cases : [];
    if (!cases.length) {
      grid.innerHTML = `<article class="loading-card"><p>No demo cases were found in this build.</p></article>`;
      return;
    }

    cases.forEach((item, index) => {
      grid.appendChild(renderCaseCard(item, index));
    });
  } catch (error) {
    const message = String(error.message || error);
    if (signalStrip) {
      signalStrip.innerHTML = `
        <article class="loading-card signal-card">
          <p>Could not load the live build telemetry.</p>
          <p>${escapeHtml(message)}</p>
        </article>
      `;
    }
    grid.innerHTML = `
      <article class="loading-card">
        <p>Could not load the demo manifest.</p>
        <p>${escapeHtml(message)}</p>
      </article>
    `;
  }
}

main();
