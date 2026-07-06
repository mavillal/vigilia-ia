/**
 * dashboard.js — VIGIL-IA Panel de Detecciones
 * Orquesta KPIs, tabla de eventos, alertas y control de acceso por rol.
 */

const CLASS_LABELS = {
  mineral_normal: "Mineral normal",
  roca_oversize: "Roca oversize",
  metal_grande: "Metal grande",
};

const RISK_BADGE = {
  sin_riesgo: { label: "Sin riesgo", css: "badge-sin" },
  riesgo: { label: "Riesgo", css: "badge-medio" },
  "daño": { label: "Daño", css: "badge-alto" },
};

const POLL_INTERVAL_MS = 5000;
let activeFilter = null;
let pollHandle = null;

function formatTimestamp(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-CL", { hour12: false });
  } catch {
    return iso;
  }
}

function riskBadgeHtml(nivelRiesgo) {
  const cfg = RISK_BADGE[nivelRiesgo] || { label: nivelRiesgo, css: "badge-sin" };
  return `<span class="badge ${cfg.css}">${cfg.label}</span>`;
}

function renderKpis(resumen) {
  const kpiRow = document.getElementById("kpi-row");
  if (!resumen) {
    kpiRow.innerHTML = `<div class="empty-state">Indicadores agregados requieren rol supervisor o superior.</div>`;
    return;
  }

  const ultima = resumen.ultima_alerta
    ? `${CLASS_LABELS[resumen.ultima_alerta.clase] || resumen.ultima_alerta.clase} · ${formatTimestamp(resumen.ultima_alerta.timestamp)}`
    : "Sin alertas registradas";

  kpiRow.innerHTML = `
    <div class="kpi-card">
      <div class="kpi-value mono">${resumen.detecciones_hoy}</div>
      <div class="kpi-label">Detecciones hoy</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value mono">${resumen.inchancables_detectados}</div>
      <div class="kpi-label">Inchancables detectados hoy</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-value" style="font-size: var(--text-lg);">${ultima}</div>
      <div class="kpi-label">Última alerta crítica</div>
    </div>
  `;
}

function renderEventsTable(eventos) {
  const tbody = document.getElementById("events-tbody");
  const emptyState = document.getElementById("events-empty");

  if (!eventos || eventos.length === 0) {
    tbody.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }
  emptyState.style.display = "none";

  tbody.innerHTML = eventos
    .map(
      (e) => `
      <tr>
        <td class="mono">${formatTimestamp(e.timestamp)}</td>
        <td>${CLASS_LABELS[e.clase] || e.clase}</td>
        <td class="mono">${(e.confianza * 100).toFixed(0)}%</td>
        <td>${riskBadgeHtml(e.nivel_riesgo)}</td>
        <td class="mono">${e.frame_id}</td>
      </tr>
    `
    )
    .join("");
}

function renderAlerts(alertas) {
  const banner = document.getElementById("critical-banner");
  const list = document.getElementById("alerts-list");

  if (!alertas || alertas.length === 0) {
    banner.style.display = "none";
    list.innerHTML = `<div class="empty-state">Sin alertas activas.</div>`;
    return;
  }

  const critica = alertas.find((a) => a.clase === "metal_grande") || alertas[0];
  banner.style.display = "block";
  banner.innerHTML = `
    <div class="label">Alerta crítica</div>
    <div class="clase">${CLASS_LABELS[critica.clase] || critica.clase}</div>
    <div class="ts mono" style="margin-top:4px; opacity:0.85;">${formatTimestamp(critica.timestamp)}</div>
  `;

  list.innerHTML = alertas
    .map(
      (a) => `
      <div class="alert-item ${a.clase === "metal_grande" ? "alto" : ""}">
        <div>${CLASS_LABELS[a.clase] || a.clase} · ${(a.confianza * 100).toFixed(0)}%</div>
        <div class="ts">${formatTimestamp(a.timestamp)} · frame ${a.frame_id}</div>
      </div>
    `
    )
    .join("");
}

function setSystemStatus(online) {
  const dot = document.getElementById("status-dot");
  const label = document.getElementById("status-label");
  dot.classList.toggle("offline", !online);
  label.textContent = online ? "Sistema operativo" : "Backend no disponible";
}

async function refresh() {
  try {
    await Api.health();
    setSystemStatus(true);
  } catch {
    setSystemStatus(false);
  }

  try {
    const resumen = await Api.getResumen();
    renderKpis(resumen);
  } catch (err) {
    if (err.message && err.message.includes("403")) {
      renderKpis(null);
    }
  }

  try {
    const eventos = await Api.getDetecciones({ limit: 50, clase: activeFilter });
    renderEventsTable(eventos);
  } catch (err) {
    console.error(err);
  }

  try {
    const alertas = await Api.getAlertas({ limit: 20 });
    renderAlerts(alertas);
  } catch (err) {
    console.error(err);
  }
}

function setupFilters() {
  const chips = document.querySelectorAll(".filter-chip");
  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeFilter = chip.dataset.clase || null;
      refresh();
    });
  });
}

function setupRoleGating() {
  const rol = Api.getRol();
  document.getElementById("user-rol").textContent = rol;

  const configItem = document.getElementById("nav-config");
  if (rol !== "gerencia") {
    configItem.dataset.locked = "true";
    configItem.title = "Requiere rol gerencia";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "index.html";
    return;
  }

  setupRoleGating();
  setupFilters();

  document.getElementById("logout-btn").addEventListener("click", () => Api.logout());

  refresh();
  pollHandle = setInterval(refresh, POLL_INTERVAL_MS);

  window.addEventListener("beforeunload", () => clearInterval(pollHandle));
});
