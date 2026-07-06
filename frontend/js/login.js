/**
 * login.js — VIGIL-IA Panel de Detecciones
 */

document.addEventListener("DOMContentLoaded", () => {
  if (Api.isAuthenticated()) {
    window.location.href = "dashboard.html";
    return;
  }

  const form = document.getElementById("login-form");
  const errorEl = document.getElementById("login-error");
  const submitBtn = document.getElementById("login-submit");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.textContent = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Ingresando...";

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      await Api.login(username, password);
      window.location.href = "dashboard.html";
    } catch (err) {
      errorEl.textContent = err.message;
      submitBtn.disabled = false;
      submitBtn.textContent = "Ingresar";
    }
  });
});
