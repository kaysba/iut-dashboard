/* Ligne de mail, mail en grand (modale) et formulaire de connexion Outlook. */
import { $, esc, ICON } from "../core/dom.js";
import { ago, fDate, hm } from "../core/dates.js";
import { store, toast } from "../core/api.js";
import { state } from "../core/state.js";
import { openModal, closeModal } from "../core/modal.js";

const mailStore = [];
export function mailRow(m) {
  const i = mailStore.push(m) - 1;
  return `<button type="button" class="mail${m.unread ? " unread" : ""}" data-mail="${i}">
    <i class="ud"></i><span class="mail-from">${esc(m.from)}</span><span class="mail-time">${esc(ago(m.date))}</span>
    <span class="mail-subj">${esc(m.subject)}${m.attachment ? ICON.clip : ""}</span>
    <span class="mail-snip">${esc(m.snippet)}</span></button>`;
}

function openMail(m) {
  closeModal();
  const url = esc(state.webmail || "https://outlook.office.com/mail/inbox");
  const d = m.date ? new Date(m.date * 1000) : null;
  const { box, close } = openModal({
    id: "mail-modal",
    labelledBy: "mail-title",
    html: `<header class="modal-head">
      <div><h2 id="mail-title">${esc(m.subject)}</h2>
        <p><b>${esc(m.from)}</b>${m.fromAddr && m.fromAddr !== m.from ? ` &lt;${esc(m.fromAddr)}&gt;` : ""}${d ? ` · ${esc(fDate.format(d))}, ${hm(d)}` : ""}${m.attachment ? " · pièce jointe" : ""}</p></div>
      <a class="btn icon" href="${url}" target="_blank" rel="noopener" title="Ouvrir sur Outlook" aria-label="Ouvrir sur Outlook">${ICON.ext}</a>
      <button class="btn icon" type="button" id="mail-close" aria-label="Fermer">${ICON.close}</button>
    </header>
    <div class="modal-body">${esc(m.body || m.snippet || "(message vide)")}</div>`,
  });
  $("#mail-close", box).addEventListener("click", close);
  $("#mail-close", box).focus();
}

// Clic sur n'importe quelle ligne de mail de la page : ouvre le mail.
export function installMailClicks() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest?.("[data-mail]");
    if (b) openMail(mailStore[+b.dataset.mail]);
  });
}

export function mailConnect({ bare = false } = {}) {
  return `<div class="${bare ? "connect bare" : "panel connect"}">
    ${bare ? "" : "<h2>Connecter ta boîte Outlook</h2>"}
    <p>Microsoft demande une connexion unique. Elle se renouvelle ensuite toute seule.</p>
    <ol>
      <li>Clique sur <b>Ouvrir la connexion Microsoft</b> et connecte-toi dans le nouvel onglet.</li>
      <li>À la fin, cet onglet affiche <b>« La connexion a échoué »</b> (adresse <code>localhost</code>). C'est normal : la connexion a réussi.</li>
      <li>Dans cet onglet, clique dans la barre d'adresse, fais <b>Ctrl+A</b> puis <b>Ctrl+C</b>. Reviens ici et colle avec <b>Ctrl+V</b> dans le champ ci-dessous.</li>
    </ol>
    <form id="mail-form">
      <button class="btn primary" type="button" id="mail-login">Ouvrir la connexion Microsoft</button>
      <input name="url" placeholder="Colle ici l'adresse copiée (https://localhost/?code=…)" aria-label="Adresse copiée" autocomplete="off">
      <button class="btn" type="submit">Valider</button>
    </form></div>`;
}

export function bindMailConnect(root, after, before) {
  const login = $("#mail-login", root);
  if (!login) return;
  const form = $("#mail-form", root);
  const input = form.url;
  login.addEventListener("click", async () => {
    if (before && (await before()) === false) return;
    const r = await fetch("/api/mail/auth-url").then((x) => x.json());
    if (r.error) return toast(r.error);
    window.open(r.url, "_blank", "noopener");
    input.focus();
  });
  let busy = false;
  const submit = async () => {
    const url = input.value.trim();
    if (!url || busy) return;
    busy = true;
    try {
      const r = await fetch("/api/mail/finish", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      const data = await r.json();
      if (data.error) return toast(data.error);
      toast("Outlook connecté");
      delete store["/api/mails"];
      after();
    } finally { busy = false; }
  };
  form.addEventListener("submit", (ev) => { ev.preventDefault(); submit(); });
  input.addEventListener("paste", () => setTimeout(() => { if (/[?&]code=/.test(input.value)) submit(); }, 0));
}
