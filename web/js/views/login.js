/* Écran de connexion (et pièces communes avec l'assistant : marque, champs du compte). */
import { postJSON, refreshMe } from "../core/api.js";
import { $, esc, main } from "../core/dom.js";
import { emit } from "../core/events.js";
import { state } from "../core/state.js";

export const brandHTML = '<div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i></span><span>IUT Nice<small>BUT Informatique</small></span></div>';

export function accountFields(me) {
  return `<label>Identifiant UniCA<input name="login" value="${esc(me.login || "")}" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="ex. ab123456" required></label>
    <label>Mot de passe<input name="password" type="password" autocomplete="current-password"></label>
    <label class="remember"><input name="remember" type="checkbox"> Se souvenir de moi</label>`;
}

// Connexion Moodle + Notes. onOk est appelé une fois connecté (après relecture de /api/me).
export function bindAccount(form, label, onOk) {
  const btn = $("button[type=submit]", form), msg = $(".msg", form);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    btn.disabled = true;
    btn.textContent = "Connexion à Moodle…";
    msg.textContent = "";
    try {
      await postJSON("/api/login", { login: form.login.value, password: form.password.value, remember: form.remember.checked });
      form.password.value = "";
      await refreshMe();
      onOk();
    } catch (e) {
      msg.textContent = e.message;
      btn.disabled = false;
      btn.textContent = label;
      form.password.focus();
    }
  });
}

export const PW_NOTE = "Ton mot de passe n'est jamais enregistré. « Se souvenir de moi » garde seulement une session Moodle et Outlook sur cet ordinateur, jusqu'à ce que tu cliques sur Se déconnecter.";

export function showLogin(message) {
  document.body.classList.add("locked");
  main.innerHTML = `<form class="panel login" id="login" autocomplete="off">
    ${brandHTML}
    <h1>Connexion</h1>
    <p>Avec ton compte de l'université.</p>
    <div class="msg" role="alert">${esc(message || "")}</div>
    ${accountFields(state.me)}
    <button class="btn primary" type="submit">Se connecter</button>
    <p class="note">${PW_NOTE} Après un redémarrage, les notes te redemanderont ton mot de passe.</p>
  </form>`;
  const f = $("#login");
  (f.login.value ? f.password : f.login).focus();
  bindAccount(f, "Se connecter", () => emit("logged-in"));
}
