/* DS à venir (page d'accueil). */
import { $, esc } from "../core/dom.js";
import { DAY, fShortMonth, hm, startOfDay } from "../core/dates.js";
import { resources } from "../core/api.js";
import { subjectOf, subjTag } from "../core/subjects.js";

// Un créneau est un DS si son titre contient « DS » (avec numéro éventuel) comme mot entier : pas ADS, DSI, Deds.
export const DS_RE = /(^|[\s\-–(])DS\d*(?=$|[\s\-–:)])/i;
export const isDS = (titre) => DS_RE.test(String(titre || ""));

// « DS - R3.06 Réseaux » -> « R3.06 Réseaux » ; le numéro est gardé : « DS2 - R3.05 Prog » -> « R3.05 Prog (DS2) ».
function dsTitle(titre) {
  const m = DS_RE.exec(titre);
  if (!m) return titre;
  const num = (m[0].match(/\d+/) || [""])[0];
  const clean = titre.replace(DS_RE, (_, pre) => pre).replace(/\s{2,}/g, " ").replace(/^[\s\-–:]+|[\s\-–:]+$/g, "");
  return clean ? (num ? `${clean} (DS${num})` : clean) : titre;
}

// DS en cours ou à venir, sans doublons (ADE renvoie parfois un créneau par groupe), du plus proche au plus lointain.
function upcomingDS(evs, now = new Date()) {
  const seen = new Set();
  return evs.filter((e) => isDS(e.title) && e.e > now)
    .sort((a, b) => a.s - b.s)
    .filter((e) => { const k = `${e.title.trim().toLowerCase()}|${e.start}`; if (seen.has(k)) return false; seen.add(k); return true; });
}

const courseCode = (titre) => ((titre.match(/\b[RS]\d\.\d{2}\b/i) || [])[0] || "").toUpperCase();
function courseFor(courses, titre) {
  const code = courseCode(titre);
  if (!code) return null;
  return courses.find((c) => (c.short || "").toUpperCase() === code)
    || courses.find((c) => (c.name.match(/\b[RS]\d\.\d{2}\b/i) || [""])[0].toUpperCase() === code) || null;
}

function dsRow(e, courses) {
  const now = new Date();
  const days = Math.round((startOfDay(e.s) - startOfDay(now)) / DAY);
  const live = e.s <= now && now < e.e;
  const urg = days <= 1 ? " late" : days <= 7 ? " soon" : "";
  const title = dsTitle(e.title);
  const when = live ? `En cours, jusqu'à ${hm(e.e)}` : days === 0 ? "aujourd'hui" : days === 1 ? "demain" : `dans ${days} jours`;
  const course = courseFor(courses, e.title);
  const annales = course ? `<a class="btn ghost ds-annales" href="#/ressources?cours=${encodeURIComponent(course.short || courseCode(e.title))}&cat=Examen">Annales</a>` : "";
  return `<div class="due ds${urg}">
    <div class="due-date"><b>${e.s.getDate()}</b><span>${esc(fShortMonth.format(e.s))}</span></div>
    <div><div class="due-name">${esc(title)}</div>
      <div class="due-meta">${subjTag(subjectOf(title), courseCode(title) || subjectOf(title).name)}<span>${hm(e.s)} – ${hm(e.e)}</span>${e.room ? `<span>${esc(e.room)}</span>` : ""}</div></div>
    <div class="due-act"><span class="ds-when">${esc(when)}</span>${annales}</div></div>`;
}

export function renderDS(evs) {
  const all = upcomingDS(evs);
  const title = `DS à venir${all.length > 3 ? ` · ${all.length}` : ""}`;
  const head = `<div class="h2"><h2>${title}</h2><a href="#/planning">Planning</a></div>`;
  const box = $("#home-ds");
  if (!box) return;
  if (!all.length) { box.innerHTML = head + '<div class="empty">Aucun DS prévu dans les deux prochains mois.</div>'; return; }
  const draw = (courses) => { const b = $("#home-ds"); if (b) b.innerHTML = head + `<div class="due-list">${all.slice(0, 3).map((e) => dsRow(e, courses)).join("")}</div>`; };
  draw([]);
  resources().then(draw).catch(() => {});   // le bouton « Annales » apparaît si un cours correspond ; sans Moodle, il n'y en a pas
}
