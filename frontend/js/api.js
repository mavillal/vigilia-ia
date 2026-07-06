/**
 * api.js — VIGIL-IA Panel de Detecciones
 * Cliente para el backend local (FastAPI + SQLite, ver ../backend).
 *
 * Resolución de API_BASE (en orden de prioridad):
 *   1. window.VIGILIA_API_BASE, si fue definido explícitamente antes de
 *      cargar este script.
 *   2. Si la página se sirve sin puerto explícito en la URL (típico detrás
 *      del proxy nginx de integration/, puerto 80/443), se asume que el
 *      backend está expuesto en el MISMO origen (ver integration/nginx.conf)
 *      y se usa window.location.origin directamente.
 *   3. Si no, se asume el flujo de desarrollo local (frontend servido en
 *      :8080 vía `python -m http.server`, backend en :8000 aparte).
 */

const API_BASE =
  window.VIGILIA_API_BASE ||
  (window.location.port === "" ? window.location.origin : "http://localhost:8000");

const TOKEN_KEY = "vigilia_token";
const ROL_KEY = "vigilia_rol";

const Api = {
  getToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  },

  getRol() {
    return sessionStorage.getItem(ROL_KEY);
  },

  isAuthenticated() {
    return Boolean(this.getToken());
  },

  logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(ROL_KEY);
    window.location.href = "index.html";
  },

  async login(username, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || "No se pudo iniciar sesión");
    }

    const data = await res.json();
    sessionStorage.setItem(TOKEN_KEY, data.access_token);
    sessionStorage.setItem(ROL_KEY, data.rol);
    return data;
  },

  async _authFetch(path, params = {}) {
    const token = this.getToken();
    if (!token) {
      window.location.href = "index.html";
      return null;
    }

    const url = new URL(`${API_BASE}${path}`);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });

    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.status === 401) {
      this.logout();
      return null;
    }
    if (!res.ok) {
      throw new Error(`Error ${res.status} al consultar ${path}`);
    }
    return res.json();
  },

  async health() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Backend no disponible");
    return res.json();
  },

  getDetecciones({ limit = 50, clase } = {}) {
    return this._authFetch("/detecciones", { limit, clase });
  },

  getAlertas({ limit = 20 } = {}) {
    return this._authFetch("/alertas", { limit });
  },

  getResumen() {
    return this._authFetch("/resumen");
  },
};
