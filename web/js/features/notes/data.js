/* Notes : lecture du relevé, notes nouvelles (localStorage) et mot de passe redemandé. */
import { $ } from "../../core/dom.js";
import { DAY } from "../../core/dates.js";
import { api, store, refreshMe } from "../../core/api.js";

export const notesData = (sem) => api(`/api/notes${sem ? `?semestre=${sem}` : ""}`, { source: "notes", maxAge: 600000 });

// Évaluations déjà vues (localStorage, facultatif). Au tout premier affichage, seules les notes
// récentes comptent comme nouvelles : on ne signale pas tout l'historique.
const SEEN_KEY = "notes.seen";
function loadSeen() {
  try { const v = JSON.parse(localStorage.getItem(SEEN_KEY)); return Array.isArray(v) ? new Set(v) : null; } catch { return null; }
}
function saveSeen(set) {
  try { localStorage.setItem(SEEN_KEY, JSON.stringify([...set])); } catch { /* stockage indisponible */ }
}
function gradedEvals(releve) {
  return releve.modules.flatMap((m) => m.evaluations.filter((e) => e.note != null));
}
export function newEvals(releve) {
  const graded = gradedEvals(releve);
  let seen = loadSeen();
  if (!seen) {
    seen = new Set(graded.filter((e) => !e.date || Date.now() - new Date(`${e.date}T12:00:00`) > 4 * DAY).map((e) => e.id));
    saveSeen(seen);
  }
  return new Set(graded.filter((e) => !seen.has(e.id)).map((e) => e.id));
}
export function markSeen(releve) {
  const seen = loadSeen() || new Set();
  gradedEvals(releve).forEach((e) => seen.add(e.id));
  saveSeen(seen);
  $("#nav-notes").textContent = "";
}

// Champ de mot de passe quand il n'y en a plus en mémoire (session « Se souvenir de moi »).
export function notesLoginForm() {
  return `<form class="pw-form" id="notes-pw" autocomplete="off">
    <input type="password" name="password" placeholder="Mot de passe pour afficher tes notes" aria-label="Mot de passe pour afficher tes notes" autocomplete="current-password" required>
    <p class="pw-err" role="alert"></p>
    <button class="btn primary" type="submit">Afficher mes notes</button></form>`;
}
export function bindNotesLogin(root, after) {
  const f = $("#notes-pw", root);
  if (!f) return;
  f.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = $("button", f), err = $(".pw-err", f);
    btn.disabled = true;
    err.textContent = "";
    try {
      const r = await fetch("/api/notes/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: f.password.value }) });
      const data = await r.json();
      if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
      f.password.value = "";
      await refreshMe();
      delete store["/api/notes"];
      after();
    } catch (e) {
      err.textContent = e.message;
      btn.disabled = false;
    }
  });
}
