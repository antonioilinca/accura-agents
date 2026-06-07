const state = { examples: [], currentMessage: "", onboarding: null, plans: {} };
const qs = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
}).format(Number(value || 0));

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await response.json();
  state.examples = data.examples || [];
  state.onboarding = data.onboarding || null;
  state.plans = data.plans || {};
  renderExamples();
  renderRecentQuotes(data.recent_quotes || []);
  renderRecentLeads(data.recent_leads || []);
  renderOnboarding();
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

function renderOnboarding() {
  if (!state.onboarding) return;
  const profile = state.onboarding;
  const form = qs("#onboardingForm");
  form.plan.value = profile.plan || "fondation";
  form.main_trade.value = profile.business?.main_trade || "plomberie";
  form.company_name.value = profile.company?.name || "";
  form.siret.value = profile.company?.siret || "";
  form.phone.value = profile.company?.phone || "";
  form.email.value = profile.company?.email || "";
  form.address.value = profile.company?.address || "";
  form.insurance.value = profile.company?.insurance || "";
  form.vat_rate.value = profile.quote_settings?.vat_rate ?? 0.1;
  form.margin_rate.value = profile.quote_settings?.margin_rate ?? 0.2;
  form.hourly_rate_ht.value = profile.quote_settings?.hourly_rate_ht ?? 55;
  form.deposit_rate.value = profile.quote_settings?.deposit_rate ?? 0.3;
  form.minimum_job_ttc.value = profile.business?.minimum_job_ttc ?? 350;
  form.validity_days.value = profile.quote_settings?.validity_days ?? 30;
  form.service_area.value = (profile.business?.service_area || []).join(", ");
  form.ideal_jobs.value = (profile.business?.ideal_jobs || []).join(", ");
  form.excluded_jobs.value = (profile.business?.excluded_jobs || []).join(", ");
  form.quote_items.value = (profile.quote_items || []).map((item) => [
    item.code,
    item.label,
    item.unit,
    item.unit_price_ht,
    (item.keywords || []).join("|"),
    item.quantity_from || "",
  ].join(";")).join("\n");
  updatePlanCapabilities();
}

function collectOnboardingProfile() {
  const form = qs("#onboardingForm");
  return {
    plan: form.plan.value,
    company: {
      name: form.company_name.value,
      siret: form.siret.value,
      phone: form.phone.value,
      email: form.email.value,
      address: form.address.value,
      insurance: form.insurance.value,
    },
    business: {
      main_trade: form.main_trade.value,
      secondary_trades: [],
      service_area: splitList(form.service_area.value),
      ideal_jobs: splitList(form.ideal_jobs.value),
      excluded_jobs: splitList(form.excluded_jobs.value),
      minimum_job_ttc: Number(form.minimum_job_ttc.value || 0),
    },
    quote_settings: {
      vat_rate: Number(form.vat_rate.value || 0),
      margin_rate: Number(form.margin_rate.value || 0),
      hourly_rate_ht: Number(form.hourly_rate_ht.value || 0),
      deposit_rate: Number(form.deposit_rate.value || 0),
      validity_days: Number(form.validity_days.value || 30),
    },
    quote_items: parseQuoteItems(form.quote_items.value),
  };
}

function parseQuoteItems(text) {
  return text.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
    const [code, label, unit, unitPrice, keywords, quantityFrom] = line.split(";").map((part) => part?.trim() || "");
    return {
      code,
      label,
      unit: unit || "forfait",
      unit_price_ht: Number(unitPrice || 0),
      keywords: (keywords || "").split("|").map((item) => item.trim()).filter(Boolean),
      ...(quantityFrom ? { quantity_from: quantityFrom } : {}),
    };
  }).filter((item) => item.code && item.label && item.unit_price_ht > 0);
}

function splitList(text) {
  return text.split(",").map((item) => item.trim()).filter(Boolean);
}

function updatePlanCapabilities() {
  const plan = qs("#planSelect").value;
  const details = state.plans[plan];
  if (!details) return;
  qs("#planCapabilities").innerHTML = `
    <strong>${escapeHtml(details.label)} · ${escapeHtml(details.price)}</strong><br>
    Agents activés : ${details.agents.map((agent) => `<code>${escapeHtml(agent)}</code>`).join(" ")}
  `;
}

async function saveOnboarding(applyConfig = false) {
  const endpoint = applyConfig ? "/api/onboarding/apply" : "/api/onboarding";
  qs("#onboardingMessage").textContent = applyConfig ? "Application..." : "Sauvegarde...";
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile: collectOnboardingProfile() }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Erreur onboarding");
  state.onboarding = data.profile;
  renderOnboarding();
  qs("#onboardingStatus").textContent = applyConfig ? "Appliqué" : "Sauvegardé";
  qs("#onboardingMessage").textContent = applyConfig
    ? `Config devis prête : ${data.paths?.devis_config || ""}`
    : "Profil sauvegardé";
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
qs("#planSelect").addEventListener("change", updatePlanCapabilities);
qs("#saveOnboardingBtn").addEventListener("click", () => {
  saveOnboarding(false).catch((error) => qs("#onboardingMessage").textContent = error.message);
});
qs("#applyOnboardingBtn").addEventListener("click", () => {
  saveOnboarding(true).catch((error) => qs("#onboardingMessage").textContent = error.message);
});

bootstrap().catch((error) => setStatus(error.message));
