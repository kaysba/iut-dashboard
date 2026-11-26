/* Assistant de premier lancement ; showAuth choisit entre l'assistant et l'écran de connexion. */
import { refreshMe, saveSettings } from "../core/api.js";
import { $, esc, main } from "../core/dom.js";
import { emit } from "../core/events.js";
import { state } from "../core/state.js";
import { bindMailConnect, mailConnect } from "../components/mail.js";
import { adeForm, bindAdeForm } from "../features/ade/form.js";
import { PW_NOTE, accountFields, bindAccount, brandHTML, showLogin } from "./login.js";

export function showAuth(message) {
  if ((state.me || {}).setup) return showSetup();
  return showLogin(message);
}

const wizard = { step: 1 };
const WIZ_STEPS = ["Compte UniCA", "Emploi du temps", "Mails"];

function stepsBar(n) {
  return `<ol class="steps" aria-label="Étapes">${WIZ_STEPS.map((label, i) => {
    const st = i + 1 < n ? "done" : i + 1 === n ? "current" : "";
    return `<li class="${st}"${st === "current" ? ' aria-current="step"' : ""}><b>${i + 1 < n ? "✓" : i + 1}</b><span>${label}</span></li>`;
  }).join("")}</ol>`;
}

export function showSetup() {
  document.body.classList.add("locked");
  const n = wizard.step;
  const me = state.me;
  const wrap = (inner) => `<div class="panel wizard">${brandHTML}${stepsBar(n)}${inner}</div>`;
  if (n === 1) {
    main.innerHTML = wrap(`<form id="login" autocomplete="off" class="wiz-body">
      <h1>Bienvenue</h1>
      <p class="lead">Trois étapes pour régler ton tableau de bord. Seule la première est obligatoire.</p>
      <div class="msg" role="alert"></div>
      ${accountFields(me)}
      <p class="hint">Ton prénom et ton adresse mail sont lus dans ton profil Moodle : rien d'autre à remplir.</p>
      <div class="wiz-foot"><span></span><button class="btn primary" type="submit">Continuer</button></div>
      <p class="note">${PW_NOTE}</p>
    </form>`);
    const f = $("#login");
    (f.login.value ? f.password : f.login).focus();
    bindAccount(f, "Continuer", () => { wizard.step = 2; showSetup(); });
    return;
  }
  if (n === 2) {
    main.innerHTML = wrap(`<div class="wiz-body">
      <h1>Ton emploi du temps</h1>
      <p class="lead">${me.prenom ? `Bonjour ${esc(me.prenom)} ! ` : ""}Le dashboard lit ton emploi du temps dans ADE grâce à ton lien d'export personnel.</p>
      ${adeForm()}
      <div class="wiz-foot"><button class="btn ghost" type="button" id="wiz-skip">Passer cette étape</button>
        <button class="btn primary" type="button" id="wiz-next" hidden>Continuer</button></div>
    </div>`);
    bindAdeForm(main, () => { $("#wiz-next").hidden = false; $("#wiz-skip").hidden = true; $("#wiz-next").focus(); });
    $("#wiz-skip").addEventListener("click", () => { wizard.step = 3; showSetup(); });
    $("#wiz-next").addEventListener("click", () => { wizard.step = 3; showSetup(); });
    $("#ade-url").focus();
    return;
  }
  const s = me.settings || {};
  const connected = s.outlook;
  main.innerHTML = wrap(`<div class="wiz-body">
    <h1>Tes mails <span class="opt">facultatif</span></h1>
    <p class="lead">Pour voir tes derniers mails de l'université sur l'accueil.</p>
    <label class="field">Adresse mail<input id="wiz-mail" type="email" autocomplete="email" spellcheck="false"
      value="${esc(s.mail || s.mailSuggestion || "")}"></label>
    <p class="check bad" id="wiz-mail-err" role="alert"></p>
    ${connected ? '<p class="check ok">Outlook est connecté.</p>' : mailConnect({ bare: true })}
    <div class="wiz-foot"><button class="btn ghost" type="button" id="wiz-skip">Passer</button>
      <button class="btn primary" type="button" id="wiz-done">Terminer</button></div>
  </div>`);
  const mailInput = $("#wiz-mail");
  const saveMail = async () => {
    const v = mailInput.value.trim();
    if (!v || v === (state.me.settings || {}).mail) return true;
    try {
      await saveSettings({ MAIL_ADRESSE: v }, null);
      $("#wiz-mail-err").textContent = "";
      return true;
    } catch (e) {
      $("#wiz-mail-err").textContent = e.message;
      mailInput.focus();
      return false;
    }
  };
  bindMailConnect(main, async () => { await refreshMe(); showSetup(); }, saveMail);
  $("#wiz-skip").addEventListener("click", finishSetup);
  $("#wiz-done").addEventListener("click", async () => { if (await saveMail()) finishSetup(); });
}

async function finishSetup() {
  wizard.step = 1;
  await refreshMe();
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  emit("logged-in");
}
