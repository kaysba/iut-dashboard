/* Ligne de devoir (accueil, page Devoirs) et registre des devoirs affichés, lu par le panneau de dépôt. */
import { esc, ICON } from "../core/dom.js";
import { fDate, fShortMonth, countdown } from "../core/dates.js";
import { subjectOf, subjTag } from "../core/subjects.js";

export const depotStore = {};            // id du devoir -> devoir (pour le panneau)
export const knownFiles = new Map();     // nom de fichier (minuscules) -> devoir où il a déjà été rendu (cette session)
let depotOff = false;                    // le Moodle de l'IUT refuse le dépôt externe : on masque pour la session
try { depotOff = sessionStorage.getItem("depotOff") === "1"; } catch { /* sans stockage */ }

export function disableDepot() {
  depotOff = true;
  try { sessionStorage.setItem("depotOff", "1"); } catch { /* sans stockage */ }
}

const canDeposit = (a) => !depotOff && a.depot && a.depot.fichiers && a.depot.ouvert;

export function rememberFiles(a) {
  const d = a.depot;
  if (d && d.statut === "remis") d.fichiers_actuels.forEach((f) => knownFiles.set(f.nom.toLowerCase(), { id: a.id, name: a.name }));
}

export function dueRow(a) {
  const now = Date.now() / 1000;
  const done = a.status === "rendu";
  const late = !done && a.due && a.due < now;
  const soon = !done && a.due && a.due >= now && a.due < now + 3 * 86400;
  const d = a.due ? new Date(a.due * 1000) : null;
  const stateTag = done ? '<span class="tag s-done">Rendu</span>'
    : late ? '<span class="tag s-late">En retard</span>'
    : a.status === "brouillon" ? '<span class="tag s-draft">Brouillon</span>'
    : soon ? '<span class="tag s-soon">Bientôt</span>' : "";
  const when = !d ? "pas de date limite" : done ? `date limite : ${fDate.format(d)}` : countdown(a.due);
  depotStore[a.id] = a;
  rememberFiles(a);
  const hot = late || soon ? " hot" : "";
  const action = done
    ? `<a class="btn ghost" href="${esc(a.url)}" target="_blank" rel="noopener">Voir le dépôt</a>`
    : canDeposit(a) ? `<button class="btn${hot}" type="button" data-depot="${a.id}">${ICON.assign}Déposer</button>`
    : `<a class="btn${hot}" href="${esc(a.submitUrl)}" target="_blank" rel="noopener">${ICON.assign}Déposer</a>`;
  const closed = !done && a.depot && a.depot.fichiers && !a.depot.ouvert ? `<span class="due-closed">${esc(a.depot.raison_fermeture)}</span>` : "";
  return `<div class="due${done ? " done" : late ? " late" : soon ? " soon" : ""}">
    <div class="due-date">${d ? `<b>${d.getDate()}</b><span>${esc(fShortMonth.format(d))}</span>` : "<b>–</b>"}</div>
    <div><a class="due-name" href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.name)}</a>
      <div class="due-meta">${subjTag(subjectOf(a.course, a.courseShort), a.courseShort || a.course)}<span>${esc(when)}</span>${stateTag}${closed}</div></div>
    <div class="due-act">${action}</div></div>`;
}
