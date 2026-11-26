/* Dashboard IUT : point d'entrée. Démarrage, rafraîchissement chaque minute, écoute des événements.
   Modules ES natifs, aucune dépendance. */
import { assignments, logout, mailsData, refreshMe, setForceNext, setStatus, store } from "./core/api.js";
import { $, main } from "./core/dom.js";
import { on } from "./core/events.js";
import { state } from "./core/state.js";
import { initTheme, syncTheme } from "./core/theme.js";
import { installMailClicks } from "./components/mail.js";
import { installDepotClicks } from "./features/depot/panel.js";
import { newEvals, notesData } from "./features/notes/data.js";
import { showLogin } from "./views/login.js";
import { showAuth } from "./views/setup.js";
import { route } from "./router.js";

function badges() {
  assignments().then((list) => {
    const now = Date.now() / 1000;
    const n = list.filter((a) => a.status !== "rendu" && a.due && a.due < now + 7 * 86400).length;
    $("#nav-devoirs").textContent = n || "";
  }).catch(() => {});
  if (state.me.sources.notes) {
    notesData().then((d) => {
      const n = d.releve.publie ? newEvals(d.releve).size : 0;
      if (location.hash !== "#/notes") $("#nav-notes").textContent = n || "";
    }).catch(() => {});
  }
  mailsData().then((m) => {
    const el = $("#nav-mails");
    el.textContent = m.unread || "";
    el.classList.add("calm");
  }).catch(() => {});
}

function start() {
  document.body.classList.remove("locked");
  Object.keys(store).forEach((k) => delete store[k]);
  setStatus("moodle", "idle");
  if (!state.me.sources.mail) setStatus("mail", "off");
  if (!state.me.sources.notes) setStatus("notes", "off");
  if (!state.me.sources.ade) setStatus("ade", "off");
  syncTheme();
  route();
  badges();
}

// Les modules signalent un changement ; ici on redessine la page et les pastilles.
on("data-changed", () => { route(); badges(); });
on("auth-required", (message) => showAuth(message));
on("login-required", (message) => showLogin(message));
on("logged-in", start);

installDepotClicks();
installMailClicks();

$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh");
  b.classList.add("spin");
  setForceNext(true);
  try { await route(); badges(); } finally {
    setForceNext(false);
    setTimeout(() => b.classList.remove("spin"), 600);
  }
});

window.addEventListener("hashchange", () => { route(); main.focus({ preventScroll: true }); window.scrollTo({ top: 0 }); });

// Rafraîchit l'affichage chaque minute (ligne « maintenant », comptes à rebours).
setInterval(() => {
  if (document.hidden) return;
  const key = location.hash.replace(/^#\/?/, "");
  if (key === "" || key === "planning" || key === "devoirs") route();
  badges();
}, 60000);

initTheme();
$("#logout").addEventListener("click", logout);

(async function init() {
  await refreshMe();
  syncTheme();
  if (state.me.demo && !state.me.setup && state.me.loggedIn) $("#logout").hidden = true;
  if (!state.me.loggedIn) return showAuth();
  start();
})();
