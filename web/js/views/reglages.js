/* Vue : Réglages. Chaque changement est enregistré tout de suite (POST /api/settings) ;
   le serveur valide et vide le cache concerné. */
import { dropStore, logout, postJSON, refreshMe, saveSettings, toast } from "../core/api.js";
import { $, esc, main } from "../core/dom.js";
import { emit } from "../core/events.js";
import { confirmModal } from "../core/modal.js";
import { state } from "../core/state.js";
import { setTheme, themeMode } from "../core/theme.js";
import { bindMailConnect, mailConnect } from "../components/mail.js";
import { adeForm, bindAdeForm, coursCount } from "../features/ade/form.js";

const SET_ORIGIN = { config: "vient de config.py", defaut: "valeur par défaut" };
const originNote = (s, key) => (s.origine && SET_ORIGIN[s.origine[key]] && s.origine[key] === "config"
  ? `<span class="from">${SET_ORIGIN.config}</span>` : "");
const CACHE_LABELS = { CACHE_PLANNING: "Emploi du temps", CACHE_MOODLE: "Moodle (cours, devoirs)", CACHE_MAILS: "Mails", CACHE_NOTES: "Notes" };

function validRegex(src) { try { new RegExp(src); return ""; } catch (e) { return e.message; } }

export async function viewSettings() {
  const me = state.me;
  const s = me.settings || {};
  const matieres = me.matieres || [];
  main.innerHTML = `<header class="head"><div><h1>Réglages</h1>
      <p>Enregistrés sur cet ordinateur, dès que tu changes quelque chose.</p></div></header>
    <div class="settings">
    <section class="panel set-sec" aria-labelledby="set-account"><h2 id="set-account">Compte</h2>
      <div class="set-row"><span class="set-label">Identifiant UniCA</span><span class="set-val"><b>${esc(me.login || "–")}</b></span></div>
      <div class="set-row"><span class="set-label">Prénom</span><span class="set-val"><b>${esc(me.prenom || "–")}</b><span class="from">lu dans Moodle</span></span></div>
      <div class="set-row"><span></span><span class="set-val"><button class="btn" type="button" id="set-logout">Se déconnecter</button></span></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-ade"><h2 id="set-ade">Emploi du temps</h2>
      <div class="set-row"><span class="set-label">Lien ADE</span>
        <span class="set-val">${s.ade ? `<code class="token" title="Lien masqué : il contient un jeton personnel">${esc(s.ade)}</code>${originNote(s, "ADE_ICAL_URL")}` : '<span class="muted">Aucun lien : l\'emploi du temps n\'est pas affiché.</span>'}
        <button class="btn" type="button" id="ade-change" aria-expanded="false">${s.ade ? "Changer" : "Ajouter"}</button></span></div>
      <div id="ade-box" hidden></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-mail"><h2 id="set-mail">Mails</h2>
      <div class="set-row"><label class="set-label" for="set-mail-input">Adresse</label>
        <span class="set-val"><input class="inp" id="set-mail-input" type="email" spellcheck="false" autocomplete="email"
          value="${esc(s.mail || "")}" placeholder="${esc(s.mailSuggestion || "prenom.nom@etu.unice.fr")}">${originNote(s, "MAIL_ADRESSE")}</span></div>
      <div class="set-row"><span class="set-label">Outlook</span>
        <span class="set-val"><span class="state"><i class="dot ${s.outlook ? "ok" : ""}"></i>${s.outlook ? "Connecté" : "Non connecté"}</span>
        <button class="btn" type="button" id="mail-toggle">${s.outlook ? "Déconnecter" : "Connecter"}</button></span></div>
      <div id="mail-box" hidden></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-colors"><h2 id="set-colors">Couleurs des matières</h2>
      <p class="set-help">La couleur sert dans le planning, les devoirs et les ressources.${originNote(s, "MATIERES")}</p>
      <ul class="subj-list">${matieres.map((m, i) => `<li><input type="color" value="${esc(m.couleur.toLowerCase())}" data-i="${i}" aria-label="Couleur de ${esc(m.nom || m.motif)}"><span>${esc(m.nom || m.motif)}</span></li>`).join("") || '<li class="muted">Aucune matière définie.</li>'}</ul>
      <div class="set-actions"><button class="btn" type="button" id="colors-reset">Couleurs par défaut</button></div>
      <details class="adv"><summary>Avancé : reconnaître les matières</summary>
        <p class="set-help">Chaque motif est une expression régulière, sans accents ni majuscules, comparée au nom du cours. La première qui correspond gagne.</p>
        <div class="motifs">${matieres.map((m, i) => `<div class="motif-row"><input class="inp" data-nom="${i}" value="${esc(m.nom)}" aria-label="Nom affiché">
          <input class="inp mono" data-motif="${i}" value="${esc(m.motif)}" spellcheck="false" aria-label="Motif de ${esc(m.nom)}"><span class="check bad" data-err="${i}"></span></div>`).join("")}</div>
      </details>
    </section>

    <section class="panel set-sec" aria-labelledby="set-display"><h2 id="set-display">Affichage</h2>
      <div class="set-row"><span class="set-label">Thème</span><span class="set-val">
        <span class="seg" role="group" aria-label="Thème">${["system", "light", "dark"].map((t) => `<button type="button" data-theme="${t}" aria-pressed="${themeMode() === t}">${{ system: "Système", light: "Clair", dark: "Sombre" }[t]}</button>`).join("")}</span></span></div>
      <div class="set-row top"><label class="set-label" for="set-hidden">Cours à masquer</label>
        <span class="set-val col"><textarea class="inp" id="set-hidden" rows="3" spellcheck="false" placeholder="Espace étudiants&#10;Bibliothèque">${esc((s.coursMasques || []).join("\n"))}</textarea>
        <span class="set-help">Un mot par ligne : les cours Moodle dont le nom contient ce mot sont masqués.</span></span></div>
    </section>

    <details class="panel set-sec adv-sec"><summary><h2>Avancé</h2></summary>
      <p class="set-help">Durée pendant laquelle le dashboard garde les données avant de les redemander (en minutes).</p>
      ${Object.entries(CACHE_LABELS).map(([k, label]) => `<div class="set-row"><label class="set-label" for="c-${k}">${label}</label>
        <span class="set-val"><input class="inp num" id="c-${k}" type="number" min="0" max="1440" step="1" data-cache="${k}" value="${Math.round(((s.cache || {})[k] || 0) / 60)}"> min</span></div>`).join("")}
      <div class="set-row"><label class="set-label" for="set-port">Port</label>
        <span class="set-val"><input class="inp num" id="set-port" type="number" min="1024" max="65535" value="${esc(s.port || "")}">
        <span class="set-help">Pris en compte au prochain lancement.${s.portActuel && s.port !== s.portActuel ? ` En ce moment : ${s.portActuel}.` : ""}</span></span></div>
    </details>

    <section class="panel set-sec danger-sec" aria-labelledby="set-wipe"><h2 id="set-wipe">Effacer</h2>
      <p class="set-help">Supprime de cet ordinateur la session, les jetons Moodle et Outlook et tous les réglages (lien ADE, couleurs…). Le dashboard revient à l'assistant de premier lancement.</p>
      <div class="set-actions"><button class="btn danger" type="button" id="wipe">Tout effacer de cet ordinateur</button></div>
    </section>
    </div>`;

  const fail = (e) => toast(e.message);
  $("#set-logout")?.addEventListener("click", logout);

  // Emploi du temps
  $("#ade-change").addEventListener("click", (ev) => {
    const box = $("#ade-box");
    box.hidden = !box.hidden;
    ev.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
    if (box.hidden) return;
    box.innerHTML = adeForm();
    bindAdeForm(box, (r) => { toast(`Enregistré : ${coursCount(r.count).toLowerCase()}`); setTimeout(viewSettings, 1200); });
    $("#ade-url", box).focus();
  });

  // Mails
  const mailInput = $("#set-mail-input");
  mailInput.addEventListener("change", () => {
    saveSettings({ MAIL_ADRESSE: mailInput.value.trim() || null }).then(viewSettings).catch(fail);
  });
  $("#mail-toggle").addEventListener("click", async (ev) => {
    if (s.outlook) {
      await postJSON("/api/mail/disconnect").catch(fail);
      dropStore("/api/mails");
      await refreshMe();
      toast("Outlook déconnecté");
      return viewSettings();
    }
    const box = $("#mail-box");
    box.hidden = !box.hidden;
    ev.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
    box.innerHTML = box.hidden ? "" : mailConnect({ bare: true });
    bindMailConnect(box, async () => { await refreshMe(); emit("data-changed", "mails"); }, async () => {
      if (!mailInput.value.trim() && !s.mailSuggestion) { toast("Indique d'abord ton adresse mail."); mailInput.focus(); return false; }
      return true;
    });
  });

  // Couleurs
  const currentList = () => (state.me.matieres || []).map((m) => ({ ...m }));
  main.querySelectorAll("input[type=color]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const list = currentList();
      list[+inp.dataset.i].couleur = inp.value.toUpperCase();
      saveSettings({ MATIERES: list }).catch(fail);
    });
  });
  $("#colors-reset").addEventListener("click", () => saveSettings({ MATIERES: null }, "Couleurs par défaut remises").then(viewSettings).catch(fail));
  main.querySelectorAll("[data-motif], [data-nom]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const i = +(inp.dataset.motif ?? inp.dataset.nom);
      const err = $(`[data-err="${i}"]`);
      const list = currentList();
      if (inp.dataset.motif !== undefined) {
        const bad = inp.value.trim() ? validRegex(inp.value) : "motif vide";
        err.textContent = bad ? `Motif invalide : ${bad}` : "";
        if (bad) return;
        list[i].motif = inp.value.trim();
      } else list[i].nom = inp.value.trim();
      saveSettings({ MATIERES: list }).catch((e) => { err.textContent = e.message; });
    });
  });

  // Affichage
  main.querySelectorAll("[data-theme]").forEach((b) => b.addEventListener("click", () => {
    setTheme(b.dataset.theme);
    main.querySelectorAll("[data-theme]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  }));
  const hidden = $("#set-hidden");
  hidden.addEventListener("change", () => {
    const words = hidden.value.split("\n").map((w) => w.trim()).filter(Boolean);
    saveSettings({ COURS_MASQUES: words }).catch(fail);
  });

  // Avancé
  main.querySelectorAll("[data-cache]").forEach((inp) => inp.addEventListener("change", () => {
    const v = Math.round(Number(inp.value));
    if (!Number.isFinite(v) || v < 0 || v > 1440) return toast("Durée entre 0 et 1440 minutes.");
    saveSettings({ [inp.dataset.cache]: v * 60 }).catch(fail);
  }));
  const port = $("#set-port");
  port.addEventListener("change", () => {
    const v = Number(port.value);
    if (!Number.isInteger(v) || v < 1024 || v > 65535) return toast("Le port doit être un nombre entre 1024 et 65535.");
    saveSettings({ PORT: v }, "Enregistré : pris en compte au prochain lancement").then(viewSettings).catch(fail);
  });

  // Tout effacer
  $("#wipe").addEventListener("click", async () => {
    const ok = await confirmModal({
      title: "Tout effacer de cet ordinateur ?",
      text: "Session, jetons Moodle et Outlook, lien ADE, couleurs et autres réglages seront supprimés. Il faudra refaire l'assistant.",
      ok: "Tout effacer",
    });
    if (!ok) return;
    try {
      await postJSON("/api/reset", { confirm: true });
      try { localStorage.clear(); sessionStorage.clear(); } catch { /* sans stockage */ }
      location.hash = "";
      location.reload();
    } catch (e) { fail(e); }
  });
}
