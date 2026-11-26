/* Vue : Devoirs. */
import { assignments, errorBox, skel } from "../core/api.js";
import { $, main } from "../core/dom.js";
import { dueRow } from "../components/due.js";

export async function viewAssignments() {
  main.innerHTML = `<header class="head"><div><h1>Devoirs</h1><p>Dépôts Moodle, du plus urgent au plus lointain</p></div></header><div id="dues">${skel(6)}</div>`;
  let list;
  try { list = await assignments(); } catch (e) { $("#dues").innerHTML = errorBox(e, "Moodle"); return; }
  const now = Date.now() / 1000;
  const open = list.filter((a) => a.status !== "rendu");
  const groups = [
    ["En retard", open.filter((a) => a.due && a.due < now)],
    ["Cette semaine", open.filter((a) => a.due && a.due >= now && a.due < now + 7 * 86400)],
    ["Plus tard", open.filter((a) => a.due >= now + 7 * 86400)],
    ["Sans date limite", open.filter((a) => !a.due)],
    ["Déjà rendus", list.filter((a) => a.status === "rendu").sort((a, b) => b.due - a.due)],
  ].filter(([, l]) => l.length);
  $("#dues").innerHTML = groups.length ? groups.map(([name, l]) => `
    <section style="margin-bottom:34px"><div class="h2"><h2>${name}</h2><span class="mail-time">${l.length}</span></div>
    <div class="due-list">${l.map(dueRow).join("")}</div></section>`).join("")
    : '<div class="empty">Aucun devoir Moodle trouvé dans tes cours.</div>';
}
