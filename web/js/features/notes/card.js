/* Carte « Notes » de la page d'accueil. */
import { $, esc } from "../../core/dom.js";
import { errorBox } from "../../core/api.js";
import { emit } from "../../core/events.js";
import { rankPill } from "../../components/rank.js";
import { fmt, gradeCls } from "./format.js";
import { notesData, notesLoginForm, bindNotesLogin } from "./data.js";

const semNom = (d) => (d.semestres.find((s) => s.actuel) || {}).nom || "";

function notesCard(d) {
  const r = d.releve;
  const top = `<div class="nc-top"><h2>Notes</h2><span>${esc(semNom(d))}</span></div>`;
  if (!r.publie) return `${top}<p class="nc-msg">${esc(r.message)}</p>`;
  const s = r.semestre;
  const promo = r.options.promo;
  const ues = r.ues.map((u) => {
    const pct = u.moyenne == null ? 0 : Math.max(0, Math.min(100, u.moyenne * 5));
    const marker = promo && u.moy != null ? `<span class="mp" style="left:${Math.min(100, u.moy * 5)}%" title="Moyenne de la promo : ${fmt(u.moy)}"></span>` : "";
    return `<div class="ue-row" style="--uc:${esc(u.couleur)}">
      <div class="ue-top"><span class="ue-code">${esc(u.code)}</span><span class="ue-name" title="${esc(u.titre)}">${esc(u.titre)}</span>
        <b class="ue-avg ${gradeCls(u.moyenne)}">${fmt(u.moyenne)}</b>${rankPill(u.rang, u.total)}</div>
      <div class="bar" role="img" aria-label="${esc(u.code)} : ${fmt(u.moyenne)} sur 20"><i style="width:${pct}%"></i><span class="m10"></span>${marker}</div></div>`;
  }).join("");
  return `${top}
    <div class="nc-avg"><div><span class="lbl">Moyenne générale</span><b class="big ${gradeCls(s.moyenne)}">${fmt(s.moyenne)}<small>/20</small></b></div>${rankPill(s.rang, s.total)}</div>
    ${s.bonus ? `<p class="nc-bonus">Bonus : ${s.bonus > 0 ? "+" : ""}${fmt(s.bonus)}</p>` : ""}
    <div class="ue-list">${ues || '<p class="nc-msg">Aucune UE pour le moment.</p>'}</div>
    <div class="nc-foot"><a href="#/notes">Relevé complet</a><span class="nc-legend">${promo ? "Repères : 10 et moyenne de la promo" : "Repère à 10"}</span></div>`;
}

export async function renderNotesCard() {
  const box = $("#home-notes");
  if (!box) return;
  try {
    box.innerHTML = notesCard(await notesData());
  } catch (e) {
    if (e.code === "notes_login_required") {
      box.innerHTML = `<div class="nc-top"><h2>Notes</h2></div>${notesLoginForm()}`;
      bindNotesLogin(box, () => emit("data-changed", "notes"));
    } else box.innerHTML = errorBox(e, "Notes");
  }
}
