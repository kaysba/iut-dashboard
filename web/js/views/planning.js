/* Vue : Planning (jour ou semaine). */
import { errorBox, planning, skel } from "../core/api.js";
import { addDays, cap, fDayMonth, fWeekday, hm, longDay, monday, sameDay, startOfDay } from "../core/dates.js";
import { $, ICON, esc, main } from "../core/dom.js";
import { subjStyle, subjectOf } from "../core/subjects.js";
import { evMeta, slots, strip } from "../components/strip.js";

const plan = { mode: "week", anchor: startOfDay(new Date()) };

export async function viewPlanning() {
  const { mode } = plan;
  const start = mode === "week" ? monday(plan.anchor) : plan.anchor;
  const end = mode === "week" ? addDays(start, 6) : start;
  const title = mode === "week"
    ? `Semaine du ${fDayMonth.format(start)}`
    : longDay(start);
  main.innerHTML = `
    <header class="head">
      <div><h1>Planning</h1><p>${esc(title)}</p></div>
      <div class="toolbar">
        <div class="seg" role="group" aria-label="Affichage">
          <button type="button" data-mode="day" aria-pressed="${mode === "day"}">Jour</button>
          <button type="button" data-mode="week" aria-pressed="${mode === "week"}">Semaine</button>
        </div>
        <button class="btn icon" type="button" data-step="-1" aria-label="Précédent">${ICON.left}</button>
        <button class="btn" type="button" data-step="0">Aujourd'hui</button>
        <button class="btn icon" type="button" data-step="1" aria-label="Suivant">${ICON.right}</button>
      </div>
    </header>
    <div id="plan" class="panel">${skel(6)}</div>`;

  main.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => { plan.mode = b.dataset.mode; viewPlanning(); }));
  main.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    const n = +b.dataset.step;
    plan.anchor = n === 0 ? startOfDay(new Date()) : addDays(plan.anchor, n * (plan.mode === "week" ? 7 : 1));
    viewPlanning();
  }));

  let evs;
  try { evs = await planning(start, end); } catch (e) { $("#plan").outerHTML = errorBox(e, "Emploi du temps"); return; }
  const box = $("#plan");
  if (mode === "day") {
    box.className = "day";
    box.innerHTML = evs.length ? `<div class="day-top"><h2>${evs.length} créneau${evs.length > 1 ? "x" : ""}</h2><span>de ${hm(evs[0].s)} à ${hm(evs[evs.length - 1].e)}</span></div>
      ${strip(evs, start)}<div style="margin-top:18px">${slots(evs)}</div>` : '<div class="day-empty">Aucun cours ce jour-là.</div>';
    return;
  }
  const days = [];
  for (let i = 0; i < 7; i++) {
    const d = addDays(start, i);
    const list = evs.filter((e) => sameDay(e.s, d));
    if (i < 5 || list.length) days.push({ d, list });
  }
  box.innerHTML = weekGrid(days) + `<div class="agenda week-agenda">${days.map(({ d, list }) => `
    <div class="agenda-day${sameDay(d, new Date()) ? " today" : ""}"><h3>${cap(fWeekday.format(d))}<span>${fDayMonth.format(d)}</span></h3>
    <div>${list.length ? slots(list) : '<div class="slot"><span class="me">Pas de cours</span></div>'}</div></div>`).join("")}</div>`;
}

function weekGrid(days) {
  const all = days.flatMap((x) => x.list);
  let from = 8, to = 18;
  all.forEach((e) => { from = Math.min(from, e.s.getHours()); to = Math.max(to, e.e.getHours() + (e.e.getMinutes() ? 1 : 0)); });
  const HH = 52;
  const now = new Date();
  const top = (d) => ((d.getHours() - from) * 60 + d.getMinutes()) / 60 * HH;
  const height = (to - from) * HH;
  const hours = Array.from({ length: to - from }, (_, i) => `<span style="top:${i * HH}px">${from + i}h</span>`).join("");
  const head = days.map(({ d }) => `<div class="wh${sameDay(d, now) ? " today" : ""}"><b>${cap(fWeekday.format(d))}</b><span>${fDayMonth.format(d)}</span></div>`).join("");
  const cols = days.map(({ d, list }) => {
    const evs = list.map((e) => {
      const h = Math.max(top(e.e) - top(e.s) - 3, 22);
      return `<div class="wev subj${e.e < now ? " past" : ""}" style="${subjStyle(subjectOf(e.title))};top:${top(e.s) + 1}px;height:${h}px" title="${esc(`${e.title}\n${hm(e.s)} – ${hm(e.e)}\n${evMeta(e)}`)}">
        <span class="ti">${esc(e.title)}</span><span class="me">${hm(e.s)} – ${hm(e.e)}</span>${h > 62 ? `<span class="me">${esc(e.room)}</span>` : ""}${h > 76 && e.teacher ? `<span class="me">${esc(e.teacher)}</span>` : ""}</div>`;
    }).join("");
    const line = sameDay(d, now) && now.getHours() >= from && now.getHours() < to ? `<div class="now-line" style="top:${top(now)}px"></div>` : "";
    return `<div class="dcol${sameDay(d, now) ? " today" : ""}" style="height:${height}px">${evs}${line}</div>`;
  }).join("");
  return `<div class="week week-grid" style="--days:${days.length};--hh:${HH}px">
    <div class="wh"></div>${head}
    <div class="hcol" style="height:${height}px">${hours}</div>${cols}</div>`;
}
