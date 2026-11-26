/* Frise de la journée (bande horaire) et liste des créneaux. */
import { esc } from "../core/dom.js";
import { hm, sameDay } from "../core/dates.js";
import { subjectOf, subjStyle } from "../core/subjects.js";

export function evMeta(ev) {
  return [ev.room, ev.teacher].filter(Boolean).join(", ");
}

export function strip(events, day) {
  const now = new Date();
  let from = 8, to = 19;
  events.forEach((e) => {
    from = Math.min(from, e.s.getHours());
    to = Math.max(to, e.e.getHours() + (e.e.getMinutes() ? 1 : 0));
  });
  const span = (to - from) * 60;
  const pos = (d) => ((d.getHours() - from) * 60 + d.getMinutes()) / span * 100;
  const grid = Array.from({ length: to - from }, () => "<i></i>").join("");
  const nowH = now.getHours() + now.getMinutes() / 60;
  const showNow = sameDay(day, now) && nowH >= from && nowH < to;
  const hours = Array.from({ length: to - from + 1 }, (_, i) => (i % 2 === 0 || to - from <= 8) && !(showNow && Math.abs(from + i - nowH) < 0.75)
    ? `<span style="left:${(i / (to - from)) * 100}%">${from + i}h</span>` : "").join("");
  const evs = events.map((e) => {
    const past = e.e < now, live = e.s <= now && now < e.e;
    return `<div class="strip-ev subj${past ? " past" : ""}${live ? " now" : ""}"
      style="${subjStyle(subjectOf(e.title))};left:calc(${pos(e.s)}% + 2px);width:calc(${pos(e.e) - pos(e.s)}% - 4px)"
      title="${esc(`${e.title}\n${hm(e.s)} – ${hm(e.e)}\n${evMeta(e)}`)}">
      <span class="ti">${esc(e.title)}</span><span class="me">${hm(e.s)}, ${esc(e.room || "salle ?")}</span>${e.teacher ? `<span class="me">${esc(e.teacher)}</span>` : ""}</div>`;
  }).join("");
  const line = showNow ? `<div class="now-line" style="left:${pos(now)}%"><span>${hm(now)}</span></div>` : "";
  return `<div class="strip"><div class="strip-grid">${grid}</div>${evs}${line}</div><div class="hours">${hours}</div>`;
}

export function slots(events) {
  const now = new Date();
  return events.map((e) => `<div class="slot${e.e < now ? " past" : ""}">
    <time>${hm(e.s)} – ${hm(e.e)}</time>
    <div><div class="ti">${esc(e.title)}</div><div class="me">${esc(evMeta(e) || "Salle non indiquée")}</div></div>
    <span class="tags"><span class="tag subj" style="${subjStyle(subjectOf(e.title))}">${e.type === "Autre" ? "Cours" : e.type}</span></span></div>`).join("");
}
