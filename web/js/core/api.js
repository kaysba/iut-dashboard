/* Appels au serveur local, cache des réponses, état des sources, messages. */
import { $, esc } from "./dom.js";
import { iso } from "./dates.js";
import { state } from "./state.js";
import { emit } from "./events.js";

export const store = {};
const status = { moodle: "idle", ade: "idle", notes: "idle", mail: "idle" };
let forceNext = false;
export const setForceNext = (v) => { forceNext = v; };

export async function api(path, { maxAge = 300000, source } = {}) {
  const hit = store[path];
  if (!forceNext && hit && Date.now() - hit.t < maxAge) return hit.p;
  const sep = path.includes("?") ? "&" : "?";
  const p = fetch(path + (forceNext ? `${sep}refresh=1` : ""))
    .then(async (r) => {
      const data = await r.json().catch(() => ({ error: `Réponse illisible (HTTP ${r.status})` }));
      if (!r.ok || data.error) {
        const e = new Error(data.error || `HTTP ${r.status}`);
        e.code = data.code;
        throw e;
      }
      if (source) setStatus(source, "ok");
      return data;
    })
    .catch((e) => {
      delete store[path];
      if (e.code === "login_required") { emit("auth-required", "Ta session a expiré. Reconnecte-toi."); throw e; }
      const off = ["mail_not_connected", "notes_login_required", "ade_not_set"].includes(e.code);
      if (source) setStatus(source, off ? "off" : "err", e.message);
      throw e;
    });
  store[path] = { t: Date.now(), p };
  if (source) setStatus(source, "wait");
  return p;
}

export function setStatus(src, s, msg) {
  status[src] = s;
  const labels = { moodle: "Moodle", ade: "Emploi du temps", notes: "Notes", mail: "Outlook" };
  const text = { ok: "connecté", err: "erreur", wait: "…", off: "non connecté", idle: "" };
  $("#sources").innerHTML = Object.keys(labels).map((k) => {
    const st = status[k];
    const cls = st === "ok" ? "ok" : st === "err" ? "err" : st === "wait" ? "wait" : "";
    return `<li title="${esc(k === src && msg ? msg : "")}"><i class="dot ${cls}"></i>${labels[k]}<span>${text[st]}</span></li>`;
  }).join("");
}

export function errorBox(e, what) {
  if (e.code === "ade_not_set") {
    return `<div class="empty">Ton emploi du temps n'est pas encore relié au dashboard.
      <a class="linkish" href="#/reglages">Ajouter mon lien ADE dans les réglages</a></div>`;
  }
  return `<div class="err"><b>${esc(what)} indisponible</b>${esc(e.message)}</div>`;
}

export const skel = (n = 3) => Array.from({ length: n }, (_, i) => `<div class="skel" style="width:${92 - i * 14}%"></div>`).join("");

export function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2400);
}

/* ── Données communes ──────────────────────────────────── */
export const planning = (start, end) => api(`/api/planning?start=${iso(start)}&end=${iso(end)}`, { source: "ade" })
  .then((d) => d.events.map((e) => ({ ...e, s: new Date(e.start), e: new Date(e.end) })));
export const assignments = () => api("/api/assignments", { source: "moodle" }).then((d) => d.assignments);
export const mailsData = () => api("/api/mails", { source: "mail", maxAge: 120000 });
export const resources = () => api("/api/resources", { source: "moodle", maxAge: 300000 }).then((d) => d.courses);

/* ── Envoi JSON commun (connexion, réglages) ───────────── */
export async function postJSON(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({ error: `Réponse illisible (HTTP ${r.status})` }));
  if (!r.ok || data.error) throw Object.assign(new Error(data.error || `HTTP ${r.status}`), { code: data.code });
  return data;
}
export const refreshMe = async () => { state.me = await fetch("/api/me").then((x) => x.json()); return state.me; };
export const dropStore = (...prefixes) => Object.keys(store).forEach((k) => { if (prefixes.some((p) => k.startsWith(p))) delete store[k]; });

// Enregistre tout de suite (POST /api/settings) ; le serveur valide et vide le cache concerné.
export async function saveSettings(changes, msg = "Enregistré") {
  const data = await postJSON("/api/settings", changes).catch((e) => {
    if (e.code === "login_required") emit("auth-required", "Ta session a expiré. Reconnecte-toi.");
    throw e;
  });
  state.me = data.me;
  const keys = Object.keys(changes);
  if (keys.some((k) => k === "ADE_ICAL_URL" || k === "CACHE_PLANNING")) dropStore("/api/planning");
  if (keys.some((k) => k === "COURS_MASQUES" || k === "CACHE_MOODLE")) dropStore("/api/resources", "/api/assignments");
  if (keys.some((k) => k === "MAIL_ADRESSE" || k === "CACHE_MAILS")) dropStore("/api/mails");
  if (msg) toast(msg);
  return data.me;
}

export async function logout() {
  await fetch("/api/logout", { method: "POST" });
  location.hash = "";
  location.reload();
}
