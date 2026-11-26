/* Vue : Aujourd'hui (accueil). */
import { assignments, errorBox, mailsData, planning, skel } from "../core/api.js";
import { addDays, hm, longDay, relDay, sameDay, startOfDay } from "../core/dates.js";
import { $, esc, main } from "../core/dom.js";
import { state } from "../core/state.js";
import { renderDS } from "../components/ds.js";
import { dueRow } from "../components/due.js";
import { mailRow } from "../components/mail.js";
import { slots, strip } from "../components/strip.js";
import { renderNotesCard } from "../features/notes/card.js";

export async function viewHome() {
  const today = startOfDay(new Date());
  const me = state.me;
  main.innerHTML = `<div class="home-grid">
    <header class="head">
      <div><h1>Bonjour${me.prenom ? ` ${esc(me.prenom)}` : ""}</h1><p id="next">${longDay(today)}</p></div>
      ${me.demo ? '<span class="demo-banner">Mode démo : données fictives</span>' : ""}
    </header>
    <section class="day" id="day"><div class="day-top"><h2>Ta journée</h2><span></span></div>${skel(2)}</section>
    <aside class="panel notes-col" aria-label="Notes"><div class="notes-card" id="home-notes">${skel(5)}</div></aside>
    <div class="cols">
      <div class="stack">
        <section><div class="h2"><h2>À rendre</h2><a href="#/devoirs">Tous les devoirs</a></div><div id="home-due">${skel(4)}</div></section>
        <section id="home-ds"><div class="h2"><h2>DS à venir</h2><a href="#/planning">Planning</a></div>${skel(3)}</section>
      </div>
      <section><div class="h2"><h2>Mails récents</h2><a href="#/mails">Boîte de réception</a></div><div id="home-mail">${skel(4)}</div></section>
    </div></div>`;
  renderNotesCard();

  planning(today, addDays(today, 7)).then((evs) => {
    const now = new Date();
    const todays = evs.filter((e) => sameDay(e.s, today));
    const next = evs.find((e) => e.e > now);
    const live = evs.find((e) => e.s <= now && now < e.e);
    let line = longDay(today);
    if (live) line += `. En ce moment : <strong>${esc(live.title)}</strong>, ${esc(live.room || "salle ?")}, jusqu'à ${hm(live.e)}`;
    else if (next) {
      const mins = Math.round((next.s - now) / 60000);
      const when = sameDay(next.s, now) ? (mins < 90 ? `dans ${mins} min` : `à ${hm(next.s)}`) : `${relDay(next.s)} à ${hm(next.s)}`;
      line += `. Prochain cours ${when} : <strong>${esc(next.title)}</strong>, ${esc(next.room || "salle ?")}`;
    }
    $("#next").innerHTML = line;
    const day = $("#day");
    const end = todays.length ? todays[todays.length - 1].e : null;
    day.innerHTML = `<div class="day-top"><h2>Ta journée</h2><span>${todays.length
      ? `${todays.length} créneau${todays.length > 1 ? "x" : ""}, fin à ${hm(end)}` : ""}</span></div>
      ${todays.length ? strip(todays, today) + `<div class="day-list">${slots(todays)}</div>`
        : `<div class="day-empty">Pas de cours aujourd'hui.${next ? ` Prochain : ${esc(next.title)}, ${relDay(next.s)} à ${hm(next.s)}.` : ""}</div>`}`;
  }).catch((e) => { $("#day").innerHTML = errorBox(e, "Emploi du temps"); });

  planning(today, addDays(today, 60)).then(renderDS)
    .catch((e) => { $("#home-ds").innerHTML = errorBox(e, "Emploi du temps"); });

  assignments().then((list) => {
    const now = Date.now() / 1000;
    const todo = list.filter((a) => a.status !== "rendu" && a.due && a.due > now - 7 * 86400)
      .sort((a, b) => a.due - b.due).slice(0, 3);
    $("#home-due").innerHTML = todo.length ? `<div class="due-list">${todo.map(dueRow).join("")}</div>`
      : '<div class="empty">Rien à rendre pour le moment.</div>';
  }).catch((e) => { $("#home-due").innerHTML = errorBox(e, "Moodle"); });

  mailsData().then((m) => {
    state.webmail = m.webmail;
    $("#home-mail").innerHTML = m.messages.length ? `<div class="mail-list">${m.messages.slice(0, 6).map(mailRow).join("")}</div>`
      : '<div class="empty">Boîte de réception vide.</div>';
  }).catch((e) => {
    const box = $("#home-mail");
    box.innerHTML = e.code === "mail_not_connected"
      ? `<div class="empty">Outlook n'est pas encore connecté. <a class="linkish" href="#/mails">Connecter ma boîte</a></div>`
      : errorBox(e, "Outlook");
  });
}
