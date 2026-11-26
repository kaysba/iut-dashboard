/* Vue : Mails. */
import { errorBox, mailsData, skel, store, toast } from "../core/api.js";
import { $, ICON, esc, main } from "../core/dom.js";
import { emit } from "../core/events.js";
import { state } from "../core/state.js";
import { bindMailConnect, mailConnect, mailRow } from "../components/mail.js";

export async function viewMails() {
  main.innerHTML = `<header class="head"><div><h1>Mails</h1><p>${esc(state.me.mail)}</p></div><div class="toolbar" id="mail-tools"></div></header><div id="mails">${skel(8)}</div>`;
  try {
    const m = await mailsData();
    state.webmail = m.webmail;
    $("#mail-tools").innerHTML = `<a class="btn" href="${esc(m.webmail)}" target="_blank" rel="noopener">${ICON.ext}Ouvrir Outlook</a>
      <button class="btn ghost" type="button" id="mail-out">Déconnecter</button>`;
    $("#mail-out").addEventListener("click", async () => {
      await fetch("/api/mail/disconnect", { method: "POST" });
      delete store["/api/mails"];
      toast("Outlook déconnecté");
      viewMails();
    });
    $("#mails").innerHTML = `<p style="margin:-10px 0 16px;color:var(--muted)">${m.unread} non lu${m.unread > 1 ? "s" : ""} dans la boîte de réception</p>
      <div class="panel mail-list mails-page">${m.messages.map(mailRow).join("") || '<div class="empty">Boîte de réception vide.</div>'}</div>`;
  } catch (e) {
    const box = $("#mails");
    if (e.code === "mail_not_connected") {
      box.innerHTML = mailConnect();
      bindMailConnect(box, () => emit("data-changed", "mails"));
    } else box.innerHTML = errorBox(e, "Outlook");
  }
}
