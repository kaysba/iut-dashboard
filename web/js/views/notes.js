/* Vue : Notes (relevé complet, par UE ou par matière). */
import { errorBox, skel, toast } from "../core/api.js";
import { fDate, iso } from "../core/dates.js";
import { $, ICON, esc, main } from "../core/dom.js";
import { rankPill } from "../components/rank.js";
import { bindNotesLogin, markSeen, newEvals, notesData, notesLoginForm } from "../features/notes/data.js";
import { fmt, fmtInt, gradeCls } from "../features/notes/format.js";
import { avecAjouts, coefParDefaut, moduleFige, noteMinimale, recalculer, restantes, verifier } from "../features/notes/simulate.js";

const notesUi = { sem: null, view: "ue", init: false };
// Simulation (semestre en cours seulement) : rien n'est envoyé ni enregistré, tout disparaît en quittant le mode.
// sim : id d'évaluation -> note simulée ; edit : évaluations déjà notées rouvertes (« Et si j'avais eu… ») ;
// ajouts : code du module -> notes ajoutées [{ id négatif, coef }] ; ask : UE dont on affiche « Quelle note pour… ? » ;
// check : vérification de la formule sur les vraies notes (et recalcul sans simulation, dans check.base).
const simUi = { on: false, sim: new Map(), edit: new Set(), ajouts: new Map(), next: 0, ask: new Set(), cible: 10, check: null };
const resetSim = () => { simUi.sim = new Map(); simUi.edit = new Set(); simUi.ajouts = new Map(); simUi.ask = new Set(); };
const simRel = (r) => avecAjouts(r, simUi.ajouts);
const simulable = (m) => simUi.on && m && !moduleFige(m);

// Notes ajoutées d'un module (« et si j'avais eu 14 en prog système ») et bouton pour en ajouter une.
const addBtn = (code) => `<button class="linkish sim-add" type="button" data-add="${esc(code)}">+ Note</button>`;
const ajoutRows = (code, titre) => (simUi.ajouts.get(code) || []).map((a) => `<div class="ev sim-new"><div class="t">Note ajoutée
    <label class="d">coef <input class="sim-coef" type="number" min="0" step="0.05" inputmode="decimal" data-coef="${a.id}" data-mod="${esc(code)}" value="${a.coef}" aria-label="Coefficient de la note ajoutée en ${esc(titre)}"></label>
    <button class="linkish sim-del" type="button" data-del="${a.id}" data-mod="${esc(code)}">Retirer</button></div>
  ${simInput({ id: a.id, note: null, titre: `note ajoutée en ${titre}` })}</div>`).join("");

// Valeur affichée : officielle, ou « 12,40 → 13,15 » quand la simulation la change.
function simValue(officiel, base, val) {
  const changed = val != null && (base == null || Math.abs(val - base) >= 0.005);
  if (!simUi.on || !changed) return `<span class="${gradeCls(officiel)}">${fmt(officiel)}</span>`;
  return `<span class="sim-from">${fmt(officiel ?? base)}</span><span class="sim-arrow" aria-hidden="true">→</span><span class="sim-val ${gradeCls(val)}" title="Valeur simulée">${fmt(val)}</span>`;
}
const slot = (key, officiel) => (simUi.on ? `<span data-s="${esc(key)}">${simValue(officiel, null, null)}</span>` : `<span class="${gradeCls(officiel)}">${fmt(officiel)}</span>`);

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
  const tiles = [`<div class="panel n-tile"><span class="lbl">Moyenne générale</span><div class="val"><span>${slot("gen", s.moyenne)}<small> /20</small></span>${rankPill(s.rang, s.total)}</div>
      ${r.options.promo ? `<div class="sub">${promoText(s)}</div>` : ""}</div>`];
  if (s.ects_total != null) tiles.push(`<div class="panel n-tile"><span class="lbl">ECTS acquis</span><div class="val">${fmtInt(s.ects_acquis ?? 0)}<small> / ${fmtInt(s.ects_total)}</small></div></div>`);
  if (s.bonus) tiles.push(`<div class="panel n-tile"><span class="lbl">Bonus</span><div class="val">${s.bonus > 0 ? "+" : ""}${fmt(s.bonus)}</div></div>`);
  if (s.absences) tiles.push(`<div class="panel n-tile"><span class="lbl">Absences</span><div class="val" style="font-size:20px">${esc(absText(s.absences))}</div></div>`);
  return `<div class="n-sum">${tiles.join("")}</div>`;
}

function notesByUe(r, fresh) {
  const newMods = new Set(r.modules.filter((m) => m.evaluations.some((e) => fresh.has(e.id))).map((m) => m.code));
  const mods = Object.fromEntries(r.modules.map((m) => [m.code, m]));
  const ask = (u) => simUi.on && restantes(u, simRel(r)).length > 0;   // seulement s'il reste des notes à trouver
  return r.ues.map((u) => `<section class="panel n-sec ue" style="--uc:${esc(u.couleur)}">
    <div class="n-sec-head"><div class="ttl"><span class="code">${esc(u.code)}</span><h2>${esc(u.titre)}</h2></div>
      <span class="avg">${slot(`ue:${u.code}`, u.moyenne)}</span>${rankPill(u.rang, u.total)}
      ${ask(u) ? `<button class="btn sim-ask" type="button" data-ask="${esc(u.code)}" aria-expanded="${simUi.ask.has(u.code)}">Quelle note pour ${simUi.cible} ?</button>` : ""}
      <div class="meta">${u.bonus ? `<span class="n-tag plus">Bonus +${fmt(u.bonus)}</span>` : ""}${u.malus ? `<span class="n-tag minus">Malus −${fmt(Math.abs(u.malus))}</span>` : ""}
        ${u.ects_total != null ? `<span>${fmtInt(u.ects_total)} ECTS</span>` : ""}${r.options.promo ? promoText(u) : ""}</div></div>
    ${u.modules.map((m) => `<div class="n-row"><span class="code">${esc(m.code)}</span>
      <span class="name">${esc(m.titre)}${newMods.has(m.code) ? '<span class="new-tag">Nouveau</span>' : ""}${simulable(mods[m.code]) && m.coef ? addBtn(m.code) : ""}</span>
      <span class="coef">coef ${fmtInt(m.coef)}</span><span class="grade">${slot(`uem:${u.code}|${m.code}`, m.moyenne)}</span></div>
      ${simulable(mods[m.code]) && m.coef ? ajoutRows(m.code, m.titre) : ""}`).join("")
      || '<div class="n-empty">Aucune ressource ni SAÉ.</div>'}
    ${ask(u) && simUi.ask.has(u.code) ? `<p class="sim-min" data-min="${esc(u.code)}" role="status"></p>` : ""}</section>`).join("");
}

function notesByModule(r, fresh) {
  const ueColor = Object.fromEntries(r.ues.map((u) => [u.code, u.couleur]));
  return r.modules.map((m) => `<section class="panel n-sec">
    <div class="n-sec-head"><div class="ttl"><span class="code">${esc(m.code)} · ${m.type === "sae" ? "SAÉ" : "Ressource"}</span><h2>${esc(m.titre)}</h2></div>
      <span class="avg">${slot(`mod:${m.code}`, m.moyenne)}</span>${rankPill(m.rang, m.total)}
      ${r.options.promo && promoText(m) ? `<div class="meta">${promoText(m)}</div>` : ""}
      ${simUi.on && moduleFige(m) ? `<p class="sim-note">${esc(figeRaison(m))} : la moyenne officielle de ce module est gardée, sans simulation.</p>` : ""}</div>
    ${m.evaluations.map((e) => {
      const poids = Object.entries(e.poids).filter(([, v]) => v).map(([k, v]) => `<span style="color:color-mix(in srgb, ${esc(ueColor[k] || "#888")} 70%, var(--ink))"><b>${esc(k)}</b> ×${fmtInt(v)}</span>`).join("");
      const stats = r.options.promo && (e.min != null || e.moy != null || e.max != null) ? promoText(e) : "";
      const sim = simUi.on && !moduleFige(m);
      return `<div class="ev"><div class="t">${esc(e.titre)}${fresh.has(e.id) ? '<span class="new-tag">Nouveau</span>' : ""}
          <span class="d">${esc(evDate(e.date))}${e.type === "bonus" ? " · bonus (points ajoutés)" : e.coef != null ? ` · coef ${fmt(e.coef)}` : ""}</span>
          ${sim && e.note != null && !simUi.edit.has(e.id) ? `<button class="linkish sim-what" type="button" data-what="${e.id}">Et si j'avais eu…</button>` : ""}</div>
        ${sim && (e.note == null || simUi.edit.has(e.id)) && !e.etat ? simInput(e)
          : e.etat ? `<span class="g none">${esc(e.etat)}</span>`
          : e.note == null ? '<span class="g none">pas encore de note</span>' : `<span class="g ${gradeCls(e.note)}">${fmt(e.note)}</span>`}
        ${poids || stats ? `<div class="sub">${poids}${stats}</div>` : ""}</div>`;
    }).join("") || (simulable(m) && simUi.ajouts.get(m.code)?.length ? "" : '<div class="n-empty">Aucune évaluation pour le moment.</div>')}
    ${simulable(m) ? `${ajoutRows(m.code, m.titre)}<div class="sim-add-row">${addBtn(m.code)}</div>` : ""}</section>`).join("");
}

function figeRaison(m) {
  const e = m.evaluations.find((x) => x.etat);
  if (e) return `Note « ${e.etat} »`;
  const t = m.evaluations.find((x) => x.type && !["normale", "bonus"].includes(x.type)).type;
  return { rattrapage: "Rattrapage", session2: "Session 2" }[t] || "Évaluation d'un type inconnu";
}

function simInput(e) {
  const v = simUi.sim.get(e.id);
  return `<span class="g sim-cell">${e.note != null ? `<span class="sim-from">${fmt(e.note)}</span><span class="sim-arrow" aria-hidden="true">→</span>` : ""}
    <input class="sim-in ${v == null ? "" : gradeCls(v)}" type="number" min="0" max="20" step="0.25" inputmode="decimal" data-ev="${e.id}"
      value="${v == null ? "" : v}" placeholder="${e.note != null ? fmt(e.note) : "?"}" aria-label="Note simulée : ${esc(e.titre)}"></span>`;
}

function simBar(r) {
  const { ecarts, generale } = simUi.check;
  const warn = ecarts.map((x) => `<li><b>${esc(x.code)}</b> : relevé ${fmt(x.officiel)}, calcul ${fmt(x.calcul)} (écart ${fmt(x.calcul == null ? null : Math.abs(x.calcul - x.officiel))})</li>`).join("")
    + (generale ? `<li><b>Moyenne générale</b> : relevé ${fmt(generale.officiel)}, calcul ${fmt(generale.calcul)} (écart ${fmt(generale.calcul == null ? null : Math.abs(generale.calcul - generale.officiel))})</li>` : "");
  return `<div class="panel sim-bar">
    <div class="sim-top"><p><b>Simulation</b> : ajoute une note à une matière (« + Note ») ou change une de tes notes (« Et si j'avais eu… », vue Par matière) ; les moyennes se recalculent aussitôt. Rien n'est enregistré ni envoyé.</p>
      <div class="sim-tools"><span class="seg" role="group" aria-label="Note visée">${[8, 10].map((c) => `<button type="button" data-cible="${c}" aria-pressed="${simUi.cible === c}">Cible ${c}</button>`).join("")}</span>
      <button class="btn" type="button" id="sim-reset">Réinitialiser</button></div></div>
    ${warn ? `<div class="sim-warn" role="alert"><b>Le calcul simulé peut différer du relevé officiel pour cette UE</b><ul>${warn}</ul></div>` : ""}
  </div>`;
}

// Met à jour les moyennes affichées sans redessiner les champs (le focus reste dans le champ en cours).
function refreshSim(root, r) {
  const rs = simRel(r), base = simUi.check.base, now = recalculer(rs, simUi.sim);
  const vals = { gen: [r.semestre.moyenne, base.generale, now.generale] };
  r.modules.forEach((m) => { vals[`mod:${m.code}`] = [m.moyenne, base.modules[m.code], now.modules[m.code]]; });
  r.ues.forEach((u) => {
    vals[`ue:${u.code}`] = [u.moyenne, base.ues[u.code], now.ues[u.code]];
    u.modules.forEach((m) => { const k = `${u.code}|${m.code}`; vals[`uem:${k}`] = [m.moyenne, base.ueModules[k], now.ueModules[k]]; });
  });
  root.querySelectorAll("[data-s]").forEach((el) => { const v = vals[el.dataset.s]; if (v) el.innerHTML = simValue(...v); });
  root.querySelectorAll("[data-min]").forEach((el) => {
    const u = r.ues.find((x) => x.code === el.dataset.min);
    const res = noteMinimale(u, rs, simUi.sim, simUi.cible);
    const reste = res.n > 1 ? `les ${res.n} notes restantes` : "la note restante";
    const vides = u.modules.filter((um) => um.coef && !(rs.modules.find((m) => m.code === um.code) || { evaluations: [] }).evaluations.length).length;
    el.innerHTML = `<b>Pour ${simUi.cible} :</b> ${{
      note: `${fmt(res.note)} de moyenne sur ${reste}`,
      acquise: "Déjà acquise, même avec 0",
      impossible: "Impossible, même avec 20",
      aucune: "toutes les notes de cette UE sont remplies (vide un champ ou ajoute une note)",
    }[res.statut]}.${vides ? ` <span class="muted">${vides} module${vides > 1 ? "s n'ont" : " n'a"} encore aucune évaluation publiée : ${vides > 1 ? "ils ne comptent" : "il ne compte"} pas.</span>` : ""}`;
  });
}

function bindSim(root, r, draw) {
  root.querySelectorAll(".sim-in").forEach((inp) => {
    const id = +inp.dataset.ev;
    const read = () => { const v = parseFloat(inp.value.replace(",", ".")); return inp.value.trim() === "" ? null : v; };
    inp.addEventListener("input", () => {
      const v = read();
      const bad = v != null && !(v >= 0 && v <= 20);
      inp.setAttribute("aria-invalid", String(bad));
      if (v == null || bad) simUi.sim.delete(id); else simUi.sim.set(id, v);
      root.querySelectorAll(`.sim-in[data-ev="${id}"]`).forEach((o) => {
        if (o !== inp) o.value = inp.value;
        o.className = `sim-in ${v == null || bad ? "" : gradeCls(v)}`;
      });
      refreshSim(root, r);
    });
    inp.addEventListener("change", () => {   // au pas de 0,25
      const v = read();
      if (v == null || !(v >= 0 && v <= 20)) return;
      const q = Math.round(v * 4) / 4;
      if (q !== v) { root.querySelectorAll(`.sim-in[data-ev="${id}"]`).forEach((o) => { o.value = q; }); simUi.sim.set(id, q); refreshSim(root, r); }
    });
  });
  root.querySelectorAll("[data-what]").forEach((b) => b.addEventListener("click", () => {
    simUi.edit.add(+b.dataset.what);
    draw();
    root.querySelector(`.sim-in[data-ev="${b.dataset.what}"]`)?.focus();
  }));
  const ajout = (el) => (simUi.ajouts.get(el.dataset.mod) || []).find((a) => a.id === +(el.dataset.coef || el.dataset.del));
  root.querySelectorAll("[data-add]").forEach((b) => b.addEventListener("click", () => {
    const code = b.dataset.add, id = --simUi.next;
    const list = simUi.ajouts.get(code) || [];
    list.push({ id, coef: coefParDefaut(r.modules.find((m) => m.code === code)) });
    simUi.ajouts.set(code, list);
    draw();
    root.querySelector(`.sim-in[data-ev="${id}"]`)?.focus();
  }));
  root.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => {
    const a = ajout(b);
    simUi.ajouts.set(b.dataset.mod, (simUi.ajouts.get(b.dataset.mod) || []).filter((x) => x !== a));
    if (a) simUi.sim.delete(a.id);
    draw();
  }));
  root.querySelectorAll(".sim-coef").forEach((inp) => inp.addEventListener("input", () => {
    const v = parseFloat(inp.value.replace(",", "."));
    const ok = v > 0 && v <= 100;
    inp.setAttribute("aria-invalid", String(!ok));
    const a = ajout(inp);
    if (!a || !ok) return;
    a.coef = v;
    root.querySelectorAll(`.sim-coef[data-coef="${a.id}"]`).forEach((o) => { if (o !== inp) o.value = inp.value; });
    refreshSim(root, r);
  }));
  root.querySelectorAll("[data-ask]").forEach((b) => b.addEventListener("click", () => {
    const c = b.dataset.ask;
    if (simUi.ask.has(c)) simUi.ask.delete(c); else simUi.ask.add(c);
    draw();
  }));
  root.querySelectorAll("[data-cible]").forEach((b) => b.addEventListener("click", () => { simUi.cible = +b.dataset.cible; draw(); }));
  root.querySelector("#sim-reset")?.addEventListener("click", () => { resetSim(); draw(); });
  refreshSim(root, r);
}

export async function viewNotes() {
  if (!notesUi.init) {   // lien direct possible : #/notes?v=mod&sem=120
    notesUi.init = true;
    const q = new URLSearchParams(location.hash.split("?")[1] || "");
    if (q.get("v") === "mod") notesUi.view = "mod";
    if (q.get("sem")) notesUi.sem = +q.get("sem");
  }
  simUi.on = false;
  resetSim();
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
    body.innerHTML = (simUi.on ? simBar(r) : "") + notesSummary(r) + (notesUi.view === "ue" ? notesByUe(r, fresh) : notesByModule(r, fresh));
    if (simUi.on) bindSim(body, r, draw);
  };
  if (current) {
    $("#n-pdf").insertAdjacentHTML("beforebegin", '<button class="btn" type="button" id="n-sim" aria-pressed="false">Simuler</button>');
    $("#n-sim").addEventListener("click", (ev) => {
      simUi.on = !simUi.on;
      resetSim();
      // La formule est vérifiée sur les vraies notes avant d'afficher la moindre valeur simulée.
      if (simUi.on) simUi.check = verifier(r);
      ev.currentTarget.setAttribute("aria-pressed", String(simUi.on));
      ev.currentTarget.textContent = simUi.on ? "Quitter la simulation" : "Simuler";
      draw();
    });
  }
  document.querySelectorAll("#n-tools .seg button").forEach((b) => b.addEventListener("click", () => { notesUi.view = b.dataset.v; draw(); }));
  draw();
  if (current) markSeen(r);
}
