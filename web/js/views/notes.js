/* Vue : Notes (relevé complet, par UE ou par matière). */
import { errorBox, skel, toast } from "../core/api.js";
import { fDate, iso } from "../core/dates.js";
import { $, ICON, esc, main } from "../core/dom.js";
import { rankPill } from "../components/rank.js";
import { bindNotesLogin, markSeen, newEvals, notesData, notesLoginForm } from "../features/notes/data.js";
import { fmt, fmtInt, gradeCls } from "../features/notes/format.js";

const notesUi = { sem: null, view: "ue", init: false };

function absText(a) {
  if (!a) return "";
  const u = /heure/i.test(a.unite) ? "h" : String(a.unite).toLowerCase();
  if (!a.total) return "Aucune absence";
  const inj = a.injustifiees ? `, dont ${fmtInt(a.injustifiees)} non justifiée${a.injustifiees > 1 ? "s" : ""}` : "";
  return `${fmtInt(a.total)} ${u}${inj}`;
}
const promoText = (o) => (o.min == null && o.moy == null && o.max == null ? ""
  : `<span>Promo : min ${fmt(o.min)}</span><span>moy ${fmt(o.moy)}</span><span>max ${fmt(o.max)}</span>`);
const evDate = (iso) => (iso ? fDate.format(new Date(`${iso}T12:00:00`)) : "");

function notesSummary(r) {
  const s = r.semestre;
  const tiles = [`<div class="panel n-tile"><span class="lbl">Moyenne générale</span><div class="val"><span class="${gradeCls(s.moyenne)}">${fmt(s.moyenne)}<small> /20</small></span>${rankPill(s.rang, s.total)}</div>
      ${r.options.promo ? `<div class="sub">${promoText(s)}</div>` : ""}</div>`];
  if (s.ects_total != null) tiles.push(`<div class="panel n-tile"><span class="lbl">ECTS acquis</span><div class="val">${fmtInt(s.ects_acquis ?? 0)}<small> / ${fmtInt(s.ects_total)}</small></div></div>`);
  if (s.bonus) tiles.push(`<div class="panel n-tile"><span class="lbl">Bonus</span><div class="val">${s.bonus > 0 ? "+" : ""}${fmt(s.bonus)}</div></div>`);
  if (s.absences) tiles.push(`<div class="panel n-tile"><span class="lbl">Absences</span><div class="val" style="font-size:20px">${esc(absText(s.absences))}</div></div>`);
  return `<div class="n-sum">${tiles.join("")}</div>`;
}

function notesByUe(r, fresh) {
  const newMods = new Set(r.modules.filter((m) => m.evaluations.some((e) => fresh.has(e.id))).map((m) => m.code));
  return r.ues.map((u) => `<section class="panel n-sec ue" style="--uc:${esc(u.couleur)}">
    <div class="n-sec-head"><div class="ttl"><span class="code">${esc(u.code)}</span><h2>${esc(u.titre)}</h2></div>
      <span class="avg ${gradeCls(u.moyenne)}">${fmt(u.moyenne)}</span>${rankPill(u.rang, u.total)}
      <div class="meta">${u.bonus ? `<span class="n-tag plus">Bonus +${fmt(u.bonus)}</span>` : ""}${u.malus ? `<span class="n-tag minus">Malus −${fmt(Math.abs(u.malus))}</span>` : ""}
        ${u.ects_total != null ? `<span>${fmtInt(u.ects_total)} ECTS</span>` : ""}${r.options.promo ? promoText(u) : ""}</div></div>
    ${u.modules.map((m) => `<div class="n-row"><span class="code">${esc(m.code)}</span>
      <span class="name">${esc(m.titre)}${newMods.has(m.code) ? '<span class="new-tag">Nouveau</span>' : ""}</span>
      <span class="coef">coef ${fmtInt(m.coef)}</span><span class="grade ${gradeCls(m.moyenne)}">${fmt(m.moyenne)}</span></div>`).join("")
      || '<div class="n-empty">Aucune ressource ni SAÉ.</div>'}</section>`).join("");
}

function notesByModule(r, fresh) {
  const ueColor = Object.fromEntries(r.ues.map((u) => [u.code, u.couleur]));
  return r.modules.map((m) => `<section class="panel n-sec">
    <div class="n-sec-head"><div class="ttl"><span class="code">${esc(m.code)} · ${m.type === "sae" ? "SAÉ" : "Ressource"}</span><h2>${esc(m.titre)}</h2></div>
      <span class="avg ${gradeCls(m.moyenne)}">${fmt(m.moyenne)}</span>${rankPill(m.rang, m.total)}
      ${r.options.promo && promoText(m) ? `<div class="meta">${promoText(m)}</div>` : ""}</div>
    ${m.evaluations.map((e) => {
      const poids = Object.entries(e.poids).filter(([, v]) => v).map(([k, v]) => `<span style="color:color-mix(in srgb, ${esc(ueColor[k] || "#888")} 70%, var(--ink))"><b>${esc(k)}</b> ×${fmtInt(v)}</span>`).join("");
      const stats = r.options.promo && (e.min != null || e.moy != null || e.max != null) ? promoText(e) : "";
      return `<div class="ev"><div class="t">${esc(e.titre)}${fresh.has(e.id) ? '<span class="new-tag">Nouveau</span>' : ""}
          <span class="d">${esc(evDate(e.date))}${e.coef != null ? ` · coef ${fmt(e.coef)}` : ""}</span></div>
        ${e.note == null ? '<span class="g none">pas encore de note</span>' : `<span class="g ${gradeCls(e.note)}">${fmt(e.note)}</span>`}
        ${poids || stats ? `<div class="sub">${poids}${stats}</div>` : ""}</div>`;
    }).join("") || '<div class="n-empty">Aucune évaluation pour le moment.</div>'}</section>`).join("");
}

export async function viewNotes() {
  if (!notesUi.init) {   // lien direct possible : #/notes?v=mod&sem=120
    notesUi.init = true;
    const q = new URLSearchParams(location.hash.split("?")[1] || "");
    if (q.get("v") === "mod") notesUi.view = "mod";
    if (q.get("sem")) notesUi.sem = +q.get("sem");
  }
  main.innerHTML = `<header class="head"><div><h1>Notes</h1><p id="n-sub">Relevé de la passerelle de l'IUT</p></div><div class="toolbar" id="n-tools"></div></header><div id="n-body">${skel(6)}</div>`;
  const body = $("#n-body");
  let d;
  try {
    d = await notesData();
    if (notesUi.sem && !d.semestres.find((s) => s.id === notesUi.sem && !s.actuel)) notesUi.sem = null;
    if (notesUi.sem) d = await notesData(notesUi.sem);
  } catch (e) {
    if (e.code === "notes_login_required") {
      body.innerHTML = `<div class="panel notes-card" style="max-width:420px"><div class="nc-top"><h2>Notes</h2></div>${notesLoginForm()}</div>`;
      bindNotesLogin(body, viewNotes);
    } else body.innerHTML = errorBox(e, "Notes");
    return;
  }
  const cur = notesUi.sem || (d.semestres.find((s) => s.actuel) || {}).id;
  const r = d.releve;
  $("#n-tools").innerHTML = `<select class="select" id="n-sem" aria-label="Semestre">${d.semestres.slice().reverse().map((s) =>
    `<option value="${s.id}"${s.id === cur ? " selected" : ""}>${esc(s.nom)}${s.actuel ? " (en cours)" : ""}</option>`).join("")}</select>
    <div class="seg" role="group" aria-label="Affichage"><button type="button" data-v="ue" aria-pressed="${notesUi.view === "ue"}">Par UE</button><button type="button" data-v="mod" aria-pressed="${notesUi.view === "mod"}">Par matière</button></div>
    <button class="btn" type="button" id="n-pdf" title="Relevé officiel de la passerelle">${ICON.dl}Relevé PDF officiel</button>`;
  $("#n-pdf").addEventListener("click", async (ev) => {
    const b = ev.currentTarget;
    b.disabled = true;
    try {
      const r = await fetch(`/api/notes/pdf?semestre=${cur}`);
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `HTTP ${r.status}`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await r.blob());
      a.download = `releve-notes-semestre-${r.headers.get("Content-Disposition")?.match(/notes-(\d+)/)?.[1] || cur}.pdf`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    } catch (e) { toast(e.message); } finally { b.disabled = false; }
  });
  $("#n-sub").textContent = `${(d.semestres.find((x) => x.id === cur) || {}).nom || ""} · relevé de notes`;
  $("#n-sem").addEventListener("change", (ev) => {
    const sel = d.semestres.find((s) => s.id === +ev.target.value);
    notesUi.sem = sel && !sel.actuel ? sel.id : null;
    viewNotes();
  });
  if (!r.publie) { body.innerHTML = `<div class="empty">${esc(r.message)}</div>`; return; }
  const current = (d.semestres.find((x) => x.id === cur) || {}).actuel;   // seul le semestre en cours a des « nouvelles » notes
  const fresh = current ? newEvals(r) : new Set();
  const draw = () => {
    document.querySelectorAll("#n-tools .seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === notesUi.view)));
    body.innerHTML = notesSummary(r) + (notesUi.view === "ue" ? notesByUe(r, fresh) : notesByModule(r, fresh));
  };
  document.querySelectorAll("#n-tools .seg button").forEach((b) => b.addEventListener("click", () => { notesUi.view = b.dataset.v; draw(); }));
  draw();
  if (current) markSeen(r);
}
