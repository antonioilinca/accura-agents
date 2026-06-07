const state = {
  examples: [],
  recentQuotes: [],
  crmStatuses: {},
  currentMessage: "",
  reviewMessage: "",
  followupMessages: [],
  onboarding: null,
  plans: {},
};
const qs = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
}).format(Number(value || 0));

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await response.json();
  state.examples = data.examples || [];
  state.recentQuotes = data.recent_quotes || [];
  state.onboarding = data.onboarding || null;
  state.plans = data.plans || {};
  renderExamples();
  renderRecentQuotes(state.recentQuotes);
  renderInvoiceQuoteOptions();
  renderRecentInvoices(data.recent_invoices || []);
  renderFollowupQuoteOptions();
  renderRecentFollowups(data.recent_followups || []);
  renderRecentLeads(data.recent_leads || []);
  renderCRM(data.crm || {});
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

function renderInvoiceQuoteOptions() {
  const select = qs("#invoiceQuoteSelect");
  if (!select) return;
  const current = select.value;
  select.innerHTML = "<option value=''>Choisir un devis</option>";
  for (const quote of state.recentQuotes) {
    const option = document.createElement("option");
    option.value = quote.id;
    option.textContent = `${quote.id} · ${quote.ville} · ${money(quote.total_ttc)}`;
    select.appendChild(option);
  }
  if (current && state.recentQuotes.some((quote) => quote.id === current)) {
    select.value = current;
  }
}

function renderFollowupQuoteOptions() {
  const select = qs("#followupQuoteSelect");
  if (!select) return;
  const current = select.value;
  select.innerHTML = "<option value=''>Choisir un devis</option>";
  for (const quote of state.recentQuotes) {
    const option = document.createElement("option");
    option.value = quote.id;
    option.textContent = `${quote.id} · ${quote.ville} · ${money(quote.total_ttc)}`;
    select.appendChild(option);
  }
  if (current && state.recentQuotes.some((quote) => quote.id === current)) {
    select.value = current;
  }
}

function renderRecentInvoices(invoices) {
  const body = qs("#recentInvoices");
  if (!body) return;
  if (!invoices.length) {
    body.innerHTML = "<tr><td colspan='6'>Aucune facture générée pour l'instant.</td></tr>";
    return;
  }
  body.innerHTML = invoices.map((invoice) => `
    <tr>
      <td><strong>${escapeHtml(invoice.id)}</strong><br>${escapeHtml(invoice.date)}</td>
      <td>${escapeHtml(invoice.quote_id)}</td>
      <td>${escapeHtml(invoice.type)}</td>
      <td>${escapeHtml(invoice.client)}</td>
      <td><strong>${money(invoice.total_ttc)}</strong></td>
      <td><a href="${invoice.html}" target="_blank">HTML</a> · <a href="${invoice.markdown}" target="_blank">MD</a> · <a href="${invoice.json}" target="_blank">JSON</a></td>
    </tr>
  `).join("");
}

function renderRecentFollowups(plans) {
  const body = qs("#recentFollowups");
  if (!body) return;
  if (!plans.length) {
    body.innerHTML = "<tr><td colspan='6'>Aucun plan de relance généré pour l'instant.</td></tr>";
    return;
  }
  body.innerHTML = plans.map((plan) => `
    <tr>
      <td><strong>${escapeHtml(plan.quote_id)}</strong></td>
      <td>${escapeHtml(plan.client)}</td>
      <td>${escapeHtml(plan.chantier)}</td>
      <td>${escapeHtml(plan.messages_count)}</td>
      <td>${escapeHtml(plan.next_date)}</td>
      <td><a href="${plan.json}" target="_blank">JSON</a></td>
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

function renderCRM(crm) {
  const rows = qs("#crmRows");
  if (!rows) return;
  const items = crm.items || [];
  state.crmStatuses = crm.statuses || {};
  renderCRMStats(crm.stats || {});
  if (!items.length) {
    rows.innerHTML = "<tr><td colspan='6'>Aucun devis dans le pipeline. Génère un devis pour remplir le CRM.</td></tr>";
    return;
  }
  rows.innerHTML = items.map((item) => `
    <tr data-quote-id="${escapeHtml(item.id)}">
      <td><strong>${escapeHtml(item.id)}</strong><br>${escapeHtml(item.date || "")}</td>
      <td>${escapeHtml(item.client)}<br><small>${escapeHtml(item.chantier)}</small></td>
      <td><strong>${money(item.total_ttc)}</strong></td>
      <td>${crmStatusSelect(item.status)}</td>
      <td><input class="crm-next-action" type="text" value="${escapeAttribute(item.next_action || "")}"></td>
      <td><button class="secondary small save-crm" type="button">Sauver</button><br><a href="${item.html}" target="_blank">Devis</a></td>
    </tr>
  `).join("");
}

function renderCRMStats(stats) {
  const box = qs("#crmStats");
  if (!box) return;
  const keys = Object.keys(state.crmStatuses);
  box.innerHTML = keys.map((key) => `
    <div><span>${escapeHtml(state.crmStatuses[key])}</span><strong>${Number(stats[key] || 0)}</strong></div>
  `).join("");
}

function crmStatusSelect(current) {
  return `<select class="crm-status">${Object.entries(state.crmStatuses).map(([value, label]) => (
    `<option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`
  )).join("")}</select>`;
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
    state.recentQuotes = fresh.recent_quotes || [];
    renderRecentQuotes(state.recentQuotes);
    renderInvoiceQuoteOptions();
    renderFollowupQuoteOptions();
    renderCRM(fresh.crm || {});
    setStatus("Devis généré");
  } catch (error) {
    setStatus(error.message);
  } finally {
    qs("#generateBtn").disabled = false;
  }
}

async function saveCRMRow(row) {
  const quoteId = row.dataset.quoteId;
  const status = row.querySelector(".crm-status").value;
  const nextAction = row.querySelector(".crm-next-action").value;
  qs("#crmState").textContent = "Sauvegarde...";
  const response = await fetch("/api/crm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quote_id: quoteId, status, next_action: nextAction }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Erreur CRM");
  renderCRM(data);
  qs("#crmState").textContent = "Sauvegardé";
}

async function generateInvoice(type) {
  const quoteId = qs("#invoiceQuoteSelect").value;
  if (!quoteId) {
    setInvoiceStatus("Choisis un devis source");
    return;
  }
  setInvoiceStatus(type === "acompte" ? "Génération acompte..." : "Génération solde...");
  qs("#generateDepositBtn").disabled = true;
  qs("#generateBalanceBtn").disabled = true;
  try {
    const response = await fetch("/api/factures", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quote_id: quoteId, type }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Erreur facture");
    renderInvoice(data);
    const fresh = await (await fetch("/api/bootstrap")).json();
    renderRecentInvoices(fresh.recent_invoices || []);
    setInvoiceStatus("Facture générée");
  } catch (error) {
    setInvoiceStatus(error.message);
  } finally {
    qs("#generateDepositBtn").disabled = false;
    qs("#generateBalanceBtn").disabled = false;
  }
}

async function generateFollowups() {
  const quoteId = qs("#followupQuoteSelect").value;
  if (!quoteId) {
    setFollowupStatus("Choisis un devis source");
    return;
  }
  setFollowupStatus("Génération...");
  qs("#generateFollowupsBtn").disabled = true;
  try {
    const response = await fetch("/api/relances", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quote_id: quoteId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Erreur relances");
    renderFollowups(data);
    const fresh = await (await fetch("/api/bootstrap")).json();
    renderRecentFollowups(fresh.recent_followups || []);
    setFollowupStatus("Relances générées");
  } catch (error) {
    setFollowupStatus(error.message);
  } finally {
    qs("#generateFollowupsBtn").disabled = false;
  }
}

async function generateReviewRequest() {
  qs("#reviewStatus").textContent = "Génération...";
  qs("#generateReviewBtn").disabled = true;
  try {
    const response = await fetch("/api/avis-google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client: qs("#reviewClient").value,
        chantier: qs("#reviewProject").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Erreur avis Google");
    state.reviewMessage = data.message || "";
    qs("#reviewMessage").textContent = state.reviewMessage || "Message indisponible.";
    qs("#reviewState").textContent = "À copier";
    qs("#reviewStatus").textContent = "Message généré";
    qs("#reviewExportsBox").innerHTML = Object.entries(data.exports || {}).map(([label, href]) => (
      `<a href="${href}" target="_blank">${label.toUpperCase()}</a>`
    )).join("");
  } catch (error) {
    qs("#reviewStatus").textContent = error.message;
  } finally {
    qs("#generateReviewBtn").disabled = false;
  }
}

function renderFollowups(plan) {
  state.followupMessages = plan.messages || [];
  qs("#followupState").textContent = state.followupMessages.length ? "À copier" : "Prêt";
  qs("#followupMessages").innerHTML = state.followupMessages.map((item, index) => `
    <article class="followup-card">
      <div class="followup-head">
        <div>
          <strong>J+${escapeHtml(item.jour)} · ${escapeHtml(item.date_prevue)}</strong>
          <span>${escapeHtml(item.objet)}</span>
        </div>
        <button class="secondary small copy-followup" type="button" data-index="${index}">Copier</button>
      </div>
      <p>${escapeHtml(item.message)}</p>
    </article>
  `).join("");
}

function renderInvoice(invoice) {
  const totaux = invoice.totaux || {};
  qs("#invoiceIdValue").textContent = invoice.id_facture || "-";
  qs("#invoiceQuoteValue").textContent = invoice.id_devis || "-";
  qs("#invoiceTypeValue").textContent = invoice.type_facture || "-";
  qs("#invoiceTotalValue").textContent = money(totaux.total_ttc);
  qs("#invoiceState").textContent = invoice.statut || "Prêt";
  qs("#invoiceExportsBox").innerHTML = Object.entries(invoice.exports || {}).map(([label, href]) => {
    const text = label === "pdf" ? "Imprimer PDF" : label.toUpperCase();
    return `<a href="${href}" target="_blank">${text}</a>`;
  }).join("");
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
  form.google_review_url.value = profile.company?.google_review_url || "";
  qs("#logoPath").textContent = profile.assets?.logo_path
    ? `Logo actif : ${profile.assets.logo_path}`
    : "Aucun logo importé";
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
      google_review_url: form.google_review_url.value,
    },
    assets: {
      logo_path: state.onboarding?.assets?.logo_path || "",
      logo_original_name: state.onboarding?.assets?.logo_original_name || "",
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

async function uploadLogo() {
  const input = qs("#logoFile");
  const file = input.files?.[0];
  if (!file) {
    qs("#onboardingMessage").textContent = "Choisis un logo PNG, JPG ou WebP";
    return;
  }

  qs("#onboardingMessage").textContent = "Import logo...";
  const formData = new FormData();
  formData.append("logo", file);
  const response = await fetch("/api/onboarding/logo", {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Erreur import logo");
  state.onboarding = data.profile;
  renderOnboarding();
  qs("#onboardingStatus").textContent = "Logo sauvegardé";
  qs("#onboardingMessage").textContent = `Logo prêt : ${data.logo?.logo_path || ""}`;
  input.value = "";
}

function setStatus(text) {
  qs("#statusText").textContent = text;
}

function setInvoiceStatus(text) {
  qs("#invoiceStatus").textContent = text;
}

function setFollowupStatus(text) {
  qs("#followupStatus").textContent = text;
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

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
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
qs("#generateDepositBtn").addEventListener("click", () => generateInvoice("acompte"));
qs("#generateBalanceBtn").addEventListener("click", () => generateInvoice("solde"));
qs("#generateFollowupsBtn").addEventListener("click", generateFollowups);
qs("#generateReviewBtn").addEventListener("click", generateReviewRequest);
qs("#clearBtn").addEventListener("click", () => {
  qs("#requestText").value = "";
  setStatus("Prêt");
});
qs("#copyMessageBtn").addEventListener("click", async () => {
  if (!state.currentMessage) return;
  await navigator.clipboard.writeText(state.currentMessage);
  setStatus("Message copié");
});
qs("#copyReviewBtn").addEventListener("click", async () => {
  if (!state.reviewMessage) return;
  await navigator.clipboard.writeText(state.reviewMessage);
  qs("#reviewStatus").textContent = "Message copié";
});
qs("#crmRows").addEventListener("click", (event) => {
  const button = event.target.closest(".save-crm");
  if (!button) return;
  const row = button.closest("tr");
  saveCRMRow(row).catch((error) => qs("#crmState").textContent = error.message);
});
qs("#followupMessages").addEventListener("click", async (event) => {
  const button = event.target.closest(".copy-followup");
  if (!button) return;
  const message = state.followupMessages[Number(button.dataset.index)]?.message;
  if (!message) return;
  await navigator.clipboard.writeText(message);
  setFollowupStatus("Message copié");
});
qs("#planSelect").addEventListener("change", updatePlanCapabilities);
qs("#saveOnboardingBtn").addEventListener("click", () => {
  saveOnboarding(false).catch((error) => qs("#onboardingMessage").textContent = error.message);
});
qs("#applyOnboardingBtn").addEventListener("click", () => {
  saveOnboarding(true).catch((error) => qs("#onboardingMessage").textContent = error.message);
});
qs("#uploadLogoBtn").addEventListener("click", () => {
  uploadLogo().catch((error) => qs("#onboardingMessage").textContent = error.message);
});

bootstrap().catch((error) => setStatus(error.message));
