const state = { examples: [], currentMessage: "" };
const qs = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
}).format(Number(value || 0));

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await response.json();
  state.examples = data.examples || [];
  renderExamples();
  renderRecentQuotes(data.recent_quotes || []);
  renderRecentLeads(data.recent_leads || []);
  if (state.examples[0]) qs("#requestText").value = state.examples[0].text;
}

function renderExamples() {
  const select = qs("#exampleSelect");
  for (const item of state.examples) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    select.appendChild(option);
  }
}

function renderRecentQuotes(quotes) {
  const body = qs("#recentQuotes");
  if (!quotes.length) {
    body.innerHTML = "<tr><td colspan='6'>Aucun devis généré pour l'instant.</td></tr>";
    return;
  }
  body.innerHTML = quotes.map((q) => `
    <tr>
      <td><strong>${escapeHtml(q.id)}</strong><br>${escapeHtml(q.date)}</td>
      <td>${escapeHtml(q.metier)}</td>
      <td>${escapeHtml(q.chantier)}</td>
      <td>${escapeHtml(q.ville)}</td>
      <td><strong>${money(q.total_ttc)}</strong>${q.questions ? `<br>${q.questions} question(s)` : ""}</td>
      <td><a href="${q.html}" target="_blank">HTML</a> · <a href="${q.markdown}" target="_blank">MD</a> · <a href="${q.json}" target="_blank">JSON</a></td>
    </tr>
  `).join("");
}

function renderRecentLeads(leads) {
  const body = qs("#recentLeads");
  if (!leads.length) {
    body.innerHTML = "<tr><td colspan='5'>Aucun lead local à afficher. Lance l'agent acquisition pour remplir cette vue.</td></tr>";
    return;
  }
  body.innerHTML = leads.map((lead) => `
    <tr>
      <td><strong>${escapeHtml(lead.score)}</strong></td>
      <td>${escapeHtml(lead.commune)}</td>
      <td>${escapeHtml(lead.metier)}</td>
      <td>${escapeHtml(lead.prochaine_action)}</td>
      <td>${escapeHtml(lead.source)}</td>
    </tr>
  `).join("");
}

async function generateQuote() {
  const text = qs("#requestText").value.trim();
  if (!text) {
    setStatus("Demande vide");
    return;
  }
  setStatus("Génération...");
  qs("#generateBtn").disabled = true;
  try {
    const response = await fetch("/api/devis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Erreur génération");
    renderQuote(data);
    const fresh = await (await fetch("/api/bootstrap")).json();
    renderRecentQuotes(fresh.recent_quotes || []);
    setStatus("Devis généré");
  } catch (error) {
    setStatus(error.message);
  } finally {
    qs("#generateBtn").disabled = false;
  }
}

function renderQuote(doc) {
  const demande = doc.demande || {};
  const totaux = doc.totaux || {};
  const lignes = doc.lignes || [];
  state.currentMessage = doc.message_client || "";

  qs("#quoteMeta").textContent = `${doc.id_devis} · ${doc.date_creation}`;
  qs("#quoteState").textContent = demande.questions?.length ? "À compléter" : "Prêt";
  qs("#tradeValue").textContent = demande.metier_libelle || "-";
  qs("#cityValue").textContent = demande.ville || "à préciser";
  qs("#surfaceValue").textContent = demande.surface_m2 ? `${demande.surface_m2} m²` : "à préciser";
  qs("#totalValue").textContent = money(totaux.total_ttc);

  const questions = demande.questions || [];
  qs("#questionsBox").classList.toggle("active", questions.length > 0);
  qs("#questionsList").innerHTML = questions.map((q) => `<li>${escapeHtml(q)}</li>`).join("");

  qs("#linesBody").innerHTML = lignes.map((line) => `
    <tr>
      <td><strong>${escapeHtml(line.libelle)}</strong><br>${escapeHtml(line.description || "")}</td>
      <td>${escapeHtml(line.quantite)} ${escapeHtml(line.unite)}</td>
      <td>${money(line.prix_unitaire_ht)}</td>
      <td><strong>${money(line.total_ht)}</strong></td>
    </tr>
  `).join("");
  qs("#clientMessage").textContent = state.currentMessage || "Message indisponible.";
  qs("#exportsBox").innerHTML = Object.entries(doc.exports || {}).map(([label, href]) => {
    const text = label === "pdf" ? "Imprimer PDF" : label.toUpperCase();
    return `<a href="${href}" target="_blank">${text}</a>`;
  }).join("");
}

function setStatus(text) {
  qs("#statusText").textContent = text;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

document.addEventListener("click", (event) => {
  const nav = event.target.closest(".nav-item");
  if (!nav) return;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  nav.classList.add("active");
  qs(`#view-${nav.dataset.view}`).classList.add("active");
});

qs("#exampleSelect").addEventListener("change", (event) => {
  const item = state.examples.find((example) => example.id === event.target.value);
  if (item) qs("#requestText").value = item.text;
});
qs("#generateBtn").addEventListener("click", generateQuote);
qs("#clearBtn").addEventListener("click", () => {
  qs("#requestText").value = "";
  setStatus("Prêt");
});
qs("#copyMessageBtn").addEventListener("click", async () => {
  if (!state.currentMessage) return;
  await navigator.clipboard.writeText(state.currentMessage);
  setStatus("Message copié");
});

bootstrap().catch((error) => setStatus(error.message));

