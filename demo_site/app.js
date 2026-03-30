async function loadManifest() {
  const response = await fetch("./generated/manifest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Manifest request failed with ${response.status}`);
  }
  return response.json();
}

function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function renderCaseCard(item) {
  const article = document.createElement("article");
  article.className = "case-card";

  const highlights = Array.isArray(item.highlights) && item.highlights.length
    ? item.highlights
    : ["Prepared reference lifecycle snapshot."];

  article.innerHTML = `
    <div class="case-head">
      <div>
        <h3>${titleize(item.title || item.case_id)}</h3>
        <p>Perspective: <strong>${titleize(item.analysis_perspective)}</strong></p>
      </div>
      <span class="badge">${titleize(item.recommendation)}</span>
    </div>
    <div class="stats">
      <span><strong>Risk:</strong> ${titleize(item.overall_risk)}</span>
      <span><strong>Findings:</strong> ${item.findings_count}</span>
      <span><strong>Obligations:</strong> ${item.obligations_count}</span>
      <span><strong>Alerts:</strong> ${item.alerts_count}</span>
      <span><strong>Documents:</strong> ${item.documents_count}</span>
    </div>
    <ul>
      ${highlights.map((highlight) => `<li>${highlight}</li>`).join("")}
    </ul>
    <a class="button button-primary" href="${item.dashboard_href}">Open dashboard</a>
  `;

  return article;
}

async function main() {
  const grid = document.getElementById("case-grid");
  const generatedAt = document.getElementById("generated-at");

  try {
    const manifest = await loadManifest();
    generatedAt.textContent = manifest.generated_at
      ? `Generated ${new Date(manifest.generated_at).toLocaleString()}`
      : "";
    grid.innerHTML = "";
    const cases = Array.isArray(manifest.cases) ? manifest.cases : [];
    if (!cases.length) {
      grid.innerHTML = `<article class="loading-card"><p>No demo cases were found in this build.</p></article>`;
      return;
    }
    for (const item of cases) {
      grid.appendChild(renderCaseCard(item));
    }
  } catch (error) {
    grid.innerHTML = `
      <article class="loading-card">
        <p>Could not load the demo manifest.</p>
        <p>${String(error.message || error)}</p>
      </article>
    `;
  }
}

main();
