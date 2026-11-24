/* Dashboard IUT : interface. Vanilla JS, aucune dépendance. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const main = $("#main");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const ICON = {
  close: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  ext: '<svg viewBox="0 0 24 24"><path d="M13.5 5.5H18.5V10.5M18 6l-7.5 7.5M16 13.5V18a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 18V9.5A1.5 1.5 0 0 1 6 8h4.5"/></svg>',
  dl: '<svg viewBox="0 0 24 24"><path d="M12 4.5v10M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>',
  clip: '<svg viewBox="0 0 24 24"><path d="m19 11.5-6.8 6.8a4.2 4.2 0 0 1-6-6l7.2-7.1a2.8 2.8 0 0 1 4 4l-7.1 7.1a1.4 1.4 0 0 1-2-2l6.4-6.4"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>',
  left: '<svg viewBox="0 0 24 24"><path d="m14.5 6-6 6 6 6"/></svg>',
  right: '<svg viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6"/></svg>',
  link: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  folder: '<svg viewBox="0 0 24 24"><path d="M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4.2l2 2.2H19a1.5 1.5 0 0 1 1.5 1.5v8.3A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/></svg>',
  page: '<svg viewBox="0 0 24 24"><path d="M7 3.5h7l4.5 4.5v12.5H7z"/><path d="M13.5 3.5V8.5H18.5M10 12.5h5.5M10 16h5.5"/></svg>',
  assign: '<svg viewBox="0 0 24 24"><path d="M12 15V4.5M7.5 9 12 4.5 16.5 9M5 15.5v3a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-3"/></svg>',
  quiz: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M9.8 9.6a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.5v.4M12 16.6v.1"/></svg>',
  forum: '<svg viewBox="0 0 24 24"><path d="M5 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6.5A1.5 1.5 0 0 1 16 15H10l-4 3.5V15H5a1.5 1.5 0 0 1-1.5-1.5V7A1.5 1.5 0 0 1 5 5.5z"/></svg>',
  trophy: '<svg viewBox="0 0 24 24"><path d="M8 4.5h8v5a4 4 0 0 1-8 0zM8 6.5H5v1.5a3 3 0 0 0 3 3M16 6.5h3v1.5a3 3 0 0 1-3 3M12 13.5v3.5M8.5 19.5h7M10 17h4"/></svg>',
  medal: '<svg viewBox="0 0 24 24"><circle cx="12" cy="14.5" r="4.5"/><path d="m9 10.2-2.5-6h4l1.5 3M15 10.2l2.5-6h-4L12 7.5"/></svg>',
  video: '<svg viewBox="0 0 24 24"><rect x="3.5" y="6" width="12" height="12" rx="2"/><path d="m15.5 10.5 5-3v9l-5-3"/></svg>',
};

/* ── Dates ─────────────────────────────────────────────── */
const DAY = 86400000;
const fr = (opts) => new Intl.DateTimeFormat("fr-FR", opts);
const fWeekday = fr({ weekday: "long" });
const fDayMonth = fr({ day: "numeric", month: "long" });
const fShortMonth = fr({ month: "short" });
const fDate = fr({ day: "numeric", month: "short" });
const hm = (d) => `${d.getHours()}h${String(d.getMinutes()).padStart(2, "0")}`;
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const monday = (d) => addDays(startOfDay(d), -((d.getDay() + 6) % 7));
const sameDay = (a, b) => a.toDateString() === b.toDateString();
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const longDay = (d) => cap(`${fWeekday.format(d)} ${fDayMonth.format(d)}`);

function relDay(d) {
  const diff = Math.round((startOfDay(d) - startOfDay(new Date())) / DAY);
  if (diff === 0) return "aujourd'hui";
  if (diff === 1) return "demain";
  if (diff === -1) return "hier";
  if (diff > 1 && diff < 7) return fWeekday.format(d);
  return fDate.format(d);
}

function countdown(ts) {
  const due = new Date(ts * 1000);
  const ms = due - Date.now();
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3600000);
  const m = Math.floor(abs / 60000);
  if (ms < 0) {
    if (h < 1) return `en retard de ${m} min`;
    if (h < 48) return `en retard de ${h} h`;
    return `en retard de ${Math.floor(h / 24)} jours`;
  }
  if (m < 60) return `dans ${m} min`;
  if (h < 24 && sameDay(due, new Date())) return `aujourd'hui à ${hm(due)}`;
  if (relDay(due) === "demain") return `demain à ${hm(due)}`;
  if (h < 24 * 7) return `${fWeekday.format(due)} à ${hm(due)}`;
  return `dans ${Math.round(h / 24)} jours`;
}

function ago(ts) {
  const d = new Date(ts * 1000);
  if (sameDay(d, new Date())) return hm(d);
  if (relDay(d) === "hier") return "hier";
  return fDate.format(d);
}

/* ── API ───────────────────────────────────────────────── */
const store = {};
const status = { moodle: "idle", ade: "idle", notes: "idle", mail: "idle" };
let forceNext = false;

async function api(path, { maxAge = 300000, source } = {}) {
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
      if (e.code === "login_required") { showLogin("Ta session a expiré. Reconnecte-toi."); throw e; }
      if (source) setStatus(source, e.code === "mail_not_connected" || e.code === "notes_login_required" ? "off" : "err", e.message);
      throw e;
    });
  store[path] = { t: Date.now(), p };
  if (source) setStatus(source, "wait");
  return p;
}

function setStatus(src, s, msg) {
  status[src] = s;
  const labels = { moodle: "Moodle", ade: "Emploi du temps", notes: "Notes", mail: "Outlook" };
  const text = { ok: "connecté", err: "erreur", wait: "…", off: "non connecté", idle: "" };
  $("#sources").innerHTML = Object.keys(labels).map((k) => {
    const st = status[k];
    const cls = st === "ok" ? "ok" : st === "err" ? "err" : st === "wait" ? "wait" : "";
    return `<li title="${esc(k === src && msg ? msg : "")}"><i class="dot ${cls}"></i>${labels[k]}<span>${text[st]}</span></li>`;
  }).join("");
}

function errorBox(e, what) {
  return `<div class="err"><b>${esc(what)} indisponible</b>${esc(e.message)}</div>`;
}

const skel = (n = 3) => Array.from({ length: n }, (_, i) => `<div class="skel" style="width:${92 - i * 14}%"></div>`).join("");

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 2400);
}

/* ── Données communes ──────────────────────────────────── */
const planning = (start, end) => api(`/api/planning?start=${iso(start)}&end=${iso(end)}`, { source: "ade" })
  .then((d) => d.events.map((e) => ({ ...e, s: new Date(e.start), e: new Date(e.end) })));
const assignments = () => api("/api/assignments", { source: "moodle" }).then((d) => d.assignments);
const mailsData = () => api("/api/mails", { source: "mail", maxAge: 120000 });
const resources = () => api("/api/resources", { source: "moodle", maxAge: 300000 }).then((d) => d.courses);

function badges() {
  assignments().then((list) => {
    const now = Date.now() / 1000;
    const n = list.filter((a) => a.status !== "rendu" && a.due && a.due < now + 7 * 86400).length;
    $("#nav-devoirs").textContent = n || "";
  }).catch(() => {});
  if (window.__me.sources.notes) {
    notesData().then((d) => {
      const n = d.releve.publie ? newEvals(d.releve).size : 0;
      if (location.hash !== "#/notes") $("#nav-notes").textContent = n || "";
    }).catch(() => {});
  }
  mailsData().then((m) => {
    const el = $("#nav-mails");
    el.textContent = m.unread || "";
    el.classList.add("calm");
  }).catch(() => {});
}

/* ── Couleurs par matière ──────────────────────────────── */
// Matières et couleurs de secours viennent de config.py (via /api/me), premier motif qui correspond : l'ordre compte.
const DEFAULT_FALLBACK = "#8A94A3";
let subjectCache = { me: null, list: [], fallback: [DEFAULT_FALLBACK] };
function subjectConfig() {
  const me = window.__me || {};
  if (subjectCache.me !== me) {
    const list = [];
    for (const m of me.matieres || []) {
      try { list.push({ re: new RegExp(m.motif), name: m.nom, color: m.couleur }); }
      catch (e) { console.error(`Motif de matière invalide « ${m.motif} » :`, e.message); }
    }
    const fallback = (me.couleursSecours || []).length ? me.couleursSecours : [DEFAULT_FALLBACK];
    subjectCache = { me, list, fallback };
  }
  return subjectCache;
}
const norm = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
function subjectOf(...texts) {
  const { list, fallback } = subjectConfig();
  const t = norm(texts.join(" "));
  const hit = list.find((x) => x.re.test(t));
  if (hit) return hit;
  const code = (t.match(/\br\d\.\d+/) || [t])[0];
  let h = 0;
  for (const c of code) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return { name: "", color: fallback[h % fallback.length] };
}
const subjStyle = (sub) => `--sc:${sub.color}`;
const subjTag = (sub, label) => `<span class="tag subj" style="${subjStyle(sub)}">${esc(label || sub.name)}</span>`;

/* ── Composants ────────────────────────────────────────── */
function evMeta(ev) {
  return [ev.room, ev.teacher].filter(Boolean).join(", ");
}

function strip(events, day) {
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
      <span class="ti">${esc(e.title)}</span><span class="me">${hm(e.s)}, ${esc(e.room || "salle ?")}</span></div>`;
  }).join("");
  const line = showNow ? `<div class="now-line" style="left:${pos(now)}%"><span>${hm(now)}</span></div>` : "";
  return `<div class="strip"><div class="strip-grid">${grid}</div>${evs}${line}</div><div class="hours">${hours}</div>`;
}

function slots(events) {
  const now = new Date();
  return events.map((e) => `<div class="slot${e.e < now ? " past" : ""}">
    <time>${hm(e.s)} – ${hm(e.e)}</time>
    <div><div class="ti">${esc(e.title)}</div><div class="me">${esc(evMeta(e) || "Salle non indiquée")}</div></div>
    <span class="tags"><span class="tag subj" style="${subjStyle(subjectOf(e.title))}">${e.type === "Autre" ? "Cours" : e.type}</span></span></div>`).join("");
}

function dueRow(a) {
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
  const action = done
    ? `<a class="btn ghost" href="${esc(a.url)}" target="_blank" rel="noopener">Voir le dépôt</a>`
    : `<a class="btn${late || soon ? " hot" : ""}" href="${esc(a.submitUrl)}" target="_blank" rel="noopener">${ICON.assign}Déposer</a>`;
  return `<div class="due${done ? " done" : late ? " late" : soon ? " soon" : ""}">
    <div class="due-date">${d ? `<b>${d.getDate()}</b><span>${esc(fShortMonth.format(d))}</span>` : "<b>–</b>"}</div>
    <div><a class="due-name" href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.name)}</a>
      <div class="due-meta">${subjTag(subjectOf(a.course, a.courseShort), a.courseShort || a.course)}<span>${esc(when)}</span>${stateTag}</div></div>
    <div class="due-act">${action}</div></div>`;
}

const mailStore = [];
function mailRow(m) {
  const i = mailStore.push(m) - 1;
  return `<button type="button" class="mail${m.unread ? " unread" : ""}" data-mail="${i}">
    <i class="ud"></i><span class="mail-from">${esc(m.from)}</span><span class="mail-time">${esc(ago(m.date))}</span>
    <span class="mail-subj">${esc(m.subject)}${m.attachment ? ICON.clip : ""}</span>
    <span class="mail-snip">${esc(m.snippet)}</span></button>`;
}

function openMail(m) {
  closeMail();
  const url = esc(window.__webmail || "https://outlook.office.com/mail/inbox");
  const d = m.date ? new Date(m.date * 1000) : null;
  const el = document.createElement("div");
  el.className = "modal-back";
  el.id = "mail-modal";
  el.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="mail-title">
    <header class="modal-head">
      <div><h2 id="mail-title">${esc(m.subject)}</h2>
        <p><b>${esc(m.from)}</b>${m.fromAddr && m.fromAddr !== m.from ? ` &lt;${esc(m.fromAddr)}&gt;` : ""}${d ? ` · ${esc(fDate.format(d))}, ${hm(d)}` : ""}${m.attachment ? " · pièce jointe" : ""}</p></div>
      <a class="btn icon" href="${url}" target="_blank" rel="noopener" title="Ouvrir sur Outlook" aria-label="Ouvrir sur Outlook">${ICON.ext}</a>
      <button class="btn icon" type="button" id="mail-close" aria-label="Fermer">${ICON.close}</button>
    </header>
    <div class="modal-body">${esc(m.body || m.snippet || "(message vide)")}</div></div>`;
  el.addEventListener("click", (ev) => { if (ev.target === el) closeMail(); });
  document.body.appendChild(el);
  $("#mail-close", el).addEventListener("click", closeMail);
  $("#mail-close", el).focus();
  document.body.classList.add("modal-open");
}
function closeMail() {
  $("#mail-modal")?.remove();
  document.body.classList.remove("modal-open");
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMail(); });
document.addEventListener("click", (e) => {
  const b = e.target.closest?.("[data-mail]");
  if (b) openMail(mailStore[+b.dataset.mail]);
});

function mailConnect() {
  return `<div class="panel connect">
    <h2>Connecter ta boîte Outlook</h2>
    <p>Microsoft demande une connexion unique. Elle se renouvelle ensuite toute seule.</p>
    <ol>
      <li>Clique sur <b>Ouvrir la connexion Microsoft</b> et connecte-toi dans le nouvel onglet.</li>
      <li>À la fin, cet onglet affiche <b>« La connexion a échoué »</b> (adresse <code>localhost</code>). C'est normal : la connexion a réussi.</li>
      <li>Dans cet onglet, clique dans la barre d'adresse, fais <b>Ctrl+A</b> puis <b>Ctrl+C</b>. Reviens ici et colle avec <b>Ctrl+V</b> dans le champ ci-dessous.</li>
    </ol>
    <form id="mail-form">
      <button class="btn primary" type="button" id="mail-login">Ouvrir la connexion Microsoft</button>
      <input name="url" placeholder="Colle ici l'adresse copiée (https://localhost/?code=…)" aria-label="Adresse copiée" autocomplete="off">
      <button class="btn" type="submit">Valider</button>
    </form></div>`;
}

function bindMailConnect(root, after) {
  const login = $("#mail-login", root);
  if (!login) return;
  const form = $("#mail-form", root);
  const input = form.url;
  login.addEventListener("click", async () => {
    const r = await fetch("/api/mail/auth-url").then((x) => x.json());
    window.open(r.url, "_blank", "noopener");
    input.focus();
  });
  let busy = false;
  const submit = async () => {
    const url = input.value.trim();
    if (!url || busy) return;
    busy = true;
    try {
      const r = await fetch("/api/mail/finish", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      const data = await r.json();
      if (data.error) return toast(data.error);
      toast("Outlook connecté");
      delete store["/api/mails"];
      after();
    } finally { busy = false; }
  };
  form.addEventListener("submit", (ev) => { ev.preventDefault(); submit(); });
  input.addEventListener("paste", () => setTimeout(() => { if (/[?&]code=/.test(input.value)) submit(); }, 0));
}

/* ── Vue : Aujourd'hui ─────────────────────────────────── */
async function viewHome() {
  const today = startOfDay(new Date());
  const me = window.__me;
  main.innerHTML = `<div class="home-grid">
    <header class="head">
      <div><h1>Bonjour ${esc(me.prenom)}</h1><p id="next">${longDay(today)}</p></div>
      ${me.demo ? '<span class="demo-banner">Mode démo : données fictives</span>' : ""}
    </header>
    <section class="day" id="day"><div class="day-top"><h2>Ta journée</h2><span></span></div>${skel(2)}</section>
    <aside class="panel notes-col" aria-label="Notes"><div class="notes-card" id="home-notes">${skel(5)}</div></aside>
    <div class="cols">
      <section><div class="h2"><h2>À rendre</h2><a href="#/devoirs">Tous les devoirs</a></div><div id="home-due">${skel(4)}</div></section>
      <section><div class="h2"><h2>Mails récents</h2><a href="#/mails">Boîte de réception</a></div><div id="home-mail">${skel(4)}</div></section>
    </div></div>`;
  renderNotesCard();

  planning(today, addDays(today, 7)).then((evs) => {
    const now = new Date();
    const todays = evs.filter((e) => sameDay(e.s, today));
    const next = evs.find((e) => e.e > now);
    const live = evs.find((e) => e.s <= now && now < e.e);
    let line = longDay(today);
    if (live) line += `. En ce moment : <strong>${esc(live.title)}</strong>, ${esc(live.room || "salle ?")}, jusqu'à ${hm(live.e)}`;
    else if (next) {
      const mins = Math.round((next.s - now) / 60000);
      const when = sameDay(next.s, now) ? (mins < 90 ? `dans ${mins} min` : `à ${hm(next.s)}`) : `${relDay(next.s)} à ${hm(next.s)}`;
      line += `. Prochain cours ${when} : <strong>${esc(next.title)}</strong>, ${esc(next.room || "salle ?")}`;
    }
    $("#next").innerHTML = line;
    const day = $("#day");
    const end = todays.length ? todays[todays.length - 1].e : null;
    day.innerHTML = `<div class="day-top"><h2>Ta journée</h2><span>${todays.length
      ? `${todays.length} créneau${todays.length > 1 ? "x" : ""}, fin à ${hm(end)}` : ""}</span></div>
      ${todays.length ? strip(todays, today) + `<div class="day-list">${slots(todays)}</div>`
        : `<div class="day-empty">Pas de cours aujourd'hui.${next ? ` Prochain : ${esc(next.title)}, ${relDay(next.s)} à ${hm(next.s)}.` : ""}</div>`}`;
  }).catch((e) => { $("#day").innerHTML = errorBox(e, "Emploi du temps"); });

  assignments().then((list) => {
    const now = Date.now() / 1000;
    const todo = list.filter((a) => a.status !== "rendu" && a.due && a.due > now - 7 * 86400)
      .sort((a, b) => a.due - b.due).slice(0, 6);
    $("#home-due").innerHTML = todo.length ? `<div class="due-list">${todo.map(dueRow).join("")}</div>`
      : '<div class="empty">Rien à rendre pour le moment.</div>';
  }).catch((e) => { $("#home-due").innerHTML = errorBox(e, "Moodle"); });

  mailsData().then((m) => {
    window.__webmail = m.webmail;
    $("#home-mail").innerHTML = m.messages.length ? `<div class="mail-list">${m.messages.slice(0, 6).map(mailRow).join("")}</div>`
      : '<div class="empty">Boîte de réception vide.</div>';
  }).catch((e) => {
    const box = $("#home-mail");
    box.innerHTML = e.code === "mail_not_connected"
      ? `<div class="empty">Outlook n'est pas encore connecté. <a class="linkish" href="#/mails">Connecter ma boîte</a></div>`
      : errorBox(e, "Outlook");
  });
}

/* ── Vue : Planning ────────────────────────────────────── */
const plan = { mode: "week", anchor: startOfDay(new Date()) };

async function viewPlanning() {
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
        <span class="ti">${esc(e.title)}</span><span class="me">${hm(e.s)} – ${hm(e.e)}</span>${h > 62 ? `<span class="me">${esc(e.room)}</span>` : ""}</div>`;
    }).join("");
    const line = sameDay(d, now) && now.getHours() >= from && now.getHours() < to ? `<div class="now-line" style="top:${top(now)}px"></div>` : "";
    return `<div class="dcol${sameDay(d, now) ? " today" : ""}" style="height:${height}px">${evs}${line}</div>`;
  }).join("");
  return `<div class="week week-grid" style="--days:${days.length};--hh:${HH}px">
    <div class="wh"></div>${head}
    <div class="hcol" style="height:${height}px">${hours}</div>${cols}</div>`;
}

/* ── Vue : Ressources ──────────────────────────────────── */
const res = { course: "all", q: "", cat: "Tout", group: "section" };
const KIND_LABEL = { pdf: "PDF", slides: "PPT", doc: "DOC", sheet: "XLS", archive: "ZIP", code: "CODE", image: "IMG", file: "FICHIER", audio: "SON" };
const CATS = ["Tout", "CM", "TD", "TP", "Examen", "Autre"];
const CAT_LABEL = { Tout: "Tout", CM: "Cours", TD: "TD", TP: "TP", Examen: "Examens", Autre: "Autres" };
const fresh = (it) => it.modified && Date.now() / 1000 - it.modified < 7 * 86400;
const size = (b) => b > 1e6 ? `${(b / 1e6).toFixed(1).replace(".", ",")} Mo` : `${Math.max(1, Math.round(b / 1e3))} Ko`;

function extBadge(it) {
  if (KIND_LABEL[it.kind]) {
    const ext = it.files[0]?.name?.split(".").pop()?.toUpperCase();
    const label = ext && ext.length <= 4 ? ext : KIND_LABEL[it.kind];
    return `<span class="ext k-${it.kind}">${esc(label)}</span>`;
  }
  const ic = { link: ICON.link, folder: ICON.folder, page: ICON.page, assign: ICON.assign, quiz: ICON.quiz, forum: ICON.forum, video: ICON.video }[it.kind] || ICON.page;
  return `<span class="ext round k-${it.kind}">${ic}</span>`;
}

function itemRow(it, course, showCourse) {
  const file = it.files.length === 1 && it.files[0].fileurl ? it.files[0] : null;
  const kindText = { link: "Lien", folder: `Dossier, ${it.files.length} fichier${it.files.length > 1 ? "s" : ""}`, page: "Page", assign: "Devoir", quiz: "Quiz", forum: "Forum" }[it.kind];
  const meta = [
    `<span class="tag t-${it.category}">${CAT_LABEL[it.category] || it.category}</span>`,
    it.correction ? '<span class="tag s-done">Corrigé</span>' : "",
    subjTag(subjectOf(course.name, course.short), course.short || course.name),
    kindText ? `<span>${kindText}</span>` : "",
    file && file.size ? `<span>${size(file.size)}</span>` : "",
    it.modified ? `<span class="${fresh(it) ? "fresh" : ""}">${fresh(it) ? "Nouveau, " : ""}${fDate.format(new Date(it.modified * 1000))}</span>` : "",
  ].join("");
  const openUrl = it.external || it.url;
  return `<div class="item">${extBadge(it)}
    <div><a class="item-name" href="${esc(openUrl)}" target="_blank" rel="noopener">${esc(it.name)}</a><div class="item-meta">${meta}</div></div>
    <div class="item-act">
      ${file ? `<a class="btn ghost" href="/api/file?u=${encodeURIComponent(file.fileurl)}" title="Télécharger ${esc(file.name)}">${ICON.dl}<span class="sr">Télécharger</span></a>` : ""}
      <a class="btn ghost" href="${esc(it.url)}" target="_blank" rel="noopener" title="Ouvrir sur Moodle">${ICON.ext}<span class="sr">Ouvrir sur Moodle</span></a>
    </div></div>`;
}

async function viewResources() {
  main.innerHTML = `<header class="head"><div><h1>Ressources</h1><p>Tous les documents de tes cours Moodle</p></div></header><div id="res">${skel(8)}</div>`;
  let courses;
  try { courses = await resources(); } catch (e) { $("#res").innerHTML = errorBox(e, "Moodle"); return; }
  renderResources(courses);
}

function renderResources(courses) {
  const box = $("#res");
  if (!box) return;
  const q = res.q.trim().toLowerCase();
  const scope = res.course === "all" ? courses : courses.filter((c) => c.id === res.course);
  const rows = [];
  scope.forEach((c) => c.sections.forEach((s) => s.items.forEach((it) => rows.push({ it, c, s }))));
  const matchQ = rows.filter(({ it, c, s }) => !q || `${it.name} ${s.name} ${c.name} ${it.files.map((f) => f.name).join(" ")}`.toLowerCase().includes(q));
  const counts = Object.fromEntries(CATS.map((k) => [k, k === "Tout" ? matchQ.length : matchQ.filter((r) => r.it.category === k).length]));
  const shown = matchQ.filter((r) => res.cat === "Tout" || r.it.category === res.cat);

  const groups = new Map();
  const all = res.course === "all";
  if (res.group === "section" && !all) {
    shown.forEach((r) => { const k = r.s.name; groups.set(k, [...(groups.get(k) || []), r]); });
  } else if (res.group === "section") {
    shown.forEach((r) => { const k = r.c.name; groups.set(k, [...(groups.get(k) || []), r]); });
  } else {
    ["CM", "TD", "TP", "Examen", "Autre"].forEach((k) => {
      const list = shown.filter((r) => r.it.category === k).sort((a, b) => b.it.modified - a.it.modified);
      if (list.length) groups.set(CAT_LABEL[k], list);
    });
  }

  const current = all ? null : courses.find((c) => c.id === res.course);
  const totalFresh = (c) => c.sections.reduce((n, s) => n + s.items.filter(fresh).length, 0);
  box.innerHTML = `<div class="res">
    <nav class="courses" aria-label="Cours">
      <button class="course" type="button" data-course="all" aria-pressed="${all}"><span class="cn">Tous les cours<span class="cs">${courses.length} cours</span></span></button>
      ${courses.map((c) => {
        const n = totalFresh(c);
        return `<button class="course subj" type="button" style="${subjStyle(subjectOf(c.name, c.short))}" data-course="${c.id}" aria-pressed="${res.course === c.id}">
          <span class="cn">${esc(c.short || c.name)}<span class="cs">${esc(c.name.replace(c.short, "").replace(/^[\s:–-]+/, "") || c.name)}</span></span>${n ? `<span class="new">${n} nouv.</span>` : ""}</button>`;
      }).join("")}
    </nav>
    <section>
      <h2 class="res-title">${esc(current ? current.name : "Tous les cours")}</h2>
      <p class="res-sub">${shown.length} élément${shown.length > 1 ? "s" : ""}${current ? `. <a class="linkish" href="${esc(current.url)}" target="_blank" rel="noopener">Ouvrir le cours sur Moodle</a>` : ""}</p>
      <div class="res-tools">
        <label class="search">${ICON.search}<input id="res-q" type="search" placeholder="Rechercher un document, un TD…" value="${esc(res.q)}" aria-label="Rechercher"></label>
        <div class="seg" role="group" aria-label="Regrouper par">
          <button type="button" data-group="section" aria-pressed="${res.group === "section"}">${all ? "Par cours" : "Par section"}</button>
          <button type="button" data-group="type" aria-pressed="${res.group === "type"}">Par type</button>
        </div>
      </div>
      <div class="chips" style="margin-bottom:22px">${CATS.map((k) => `<button class="chip" type="button" data-cat="${k}" aria-pressed="${res.cat === k}">${CAT_LABEL[k]}<b>${counts[k]}</b></button>`).join("")}</div>
      ${groups.size ? [...groups].map(([name, list]) => `<div class="group"><h3>${esc(name)}<span>${list.length}</span></h3>
        <div class="items">${list.map((r) => itemRow(r.it, r.c, all && res.group === "type")).join("")}</div></div>`).join("")
        : '<div class="empty">Aucun document ne correspond. Essaie un autre filtre ou un autre mot.</div>'}
    </section></div>`;

  box.querySelectorAll("[data-course]").forEach((b) => b.addEventListener("click", () => {
    res.course = b.dataset.course === "all" ? "all" : +b.dataset.course;
    renderResources(courses);
    window.scrollTo({ top: 0 });
  }));
  box.querySelectorAll("[data-cat]").forEach((b) => b.addEventListener("click", () => { res.cat = b.dataset.cat; renderResources(courses); }));
  box.querySelectorAll("[data-group]").forEach((b) => b.addEventListener("click", () => { res.group = b.dataset.group; renderResources(courses); }));
  const input = $("#res-q", box);
  input.addEventListener("input", () => {
    res.q = input.value;
    clearTimeout(renderResources._t);
    renderResources._t = setTimeout(() => {
      const pos = input.selectionStart;
      renderResources(courses);
      const again = $("#res-q");
      again.focus();
      again.setSelectionRange(pos, pos);
    }, 160);
  });
}

/* ── Vue : Devoirs ─────────────────────────────────────── */
async function viewAssignments() {
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

/* ── Notes ─────────────────────────────────────────────── */
const fmt = (v, d = 2) => (v == null ? "–" : v.toFixed(d).replace(".", ","));
const fmtInt = (v) => (Number.isInteger(v) ? String(v) : fmt(v, 1));
// ≥ 10 normal, de 8 à 10 orange, < 8 rouge (une UE sous 8 ne se compense pas en BUT).
const gradeCls = (v) => (v == null ? "g-none" : v >= 10 ? "g-ok" : v >= 8 ? "g-warn" : "g-bad");
const ordinal = (n) => (n === 1 ? "1er" : `${n}e`);
const notesData = (sem) => api(`/api/notes${sem ? `?semestre=${sem}` : ""}`, { source: "notes", maxAge: 600000 });

// Pastille de rang, réutilisée partout : podium or / argent / bronze (avec icône), puis bleu.
function rankPill(rang, total) {
  if (rang == null || !total) return "";
  const tier = rang <= 3 ? `r${rang}` : "rn";
  const icon = rang === 1 ? ICON.trophy : rang <= 3 ? ICON.medal : "";
  return `<span class="rank ${tier}" title="Rang ${rang} sur ${total}" aria-label="Rang : ${ordinal(rang)} sur ${total}">${icon}${ordinal(rang)} / ${total}</span>`;
}

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
function newEvals(releve) {
  const graded = gradedEvals(releve);
  let seen = loadSeen();
  if (!seen) {
    seen = new Set(graded.filter((e) => !e.date || Date.now() - new Date(`${e.date}T12:00:00`) > 4 * DAY).map((e) => e.id));
    saveSeen(seen);
  }
  return new Set(graded.filter((e) => !seen.has(e.id)).map((e) => e.id));
}
function markSeen(releve) {
  const seen = loadSeen() || new Set();
  gradedEvals(releve).forEach((e) => seen.add(e.id));
  saveSeen(seen);
  $("#nav-notes").textContent = "";
}

// Champ de mot de passe quand il n'y en a plus en mémoire (session « Se souvenir de moi »).
function notesLoginForm() {
  return `<form class="pw-form" id="notes-pw" autocomplete="off">
    <input type="password" name="password" placeholder="Mot de passe pour afficher tes notes" aria-label="Mot de passe pour afficher tes notes" autocomplete="current-password" required>
    <p class="pw-err" role="alert"></p>
    <button class="btn primary" type="submit">Afficher mes notes</button></form>`;
}
function bindNotesLogin(root, after) {
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
      window.__me = await fetch("/api/me").then((x) => x.json());
      delete store["/api/notes"];
      after();
    } catch (e) {
      err.textContent = e.message;
      btn.disabled = false;
    }
  });
}

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

async function renderNotesCard() {
  const box = $("#home-notes");
  if (!box) return;
  try {
    box.innerHTML = notesCard(await notesData());
  } catch (e) {
    if (e.code === "notes_login_required") {
      box.innerHTML = `<div class="nc-top"><h2>Notes</h2></div>${notesLoginForm()}`;
      bindNotesLogin(box, () => { renderNotesCard(); badges(); });
    } else box.innerHTML = errorBox(e, "Notes");
  }
}

/* ── Vue : Notes ───────────────────────────────────────── */
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

async function viewNotes() {
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

/* ── Vue : Mails ───────────────────────────────────────── */
async function viewMails() {
  main.innerHTML = `<header class="head"><div><h1>Mails</h1><p>${esc(window.__me.mail)}</p></div><div class="toolbar" id="mail-tools"></div></header><div id="mails">${skel(8)}</div>`;
  try {
    const m = await mailsData();
    window.__webmail = m.webmail;
    $("#mail-tools").innerHTML = `<a class="btn" href="${esc(m.webmail)}" target="_blank" rel="noopener">${ICON.ext}Ouvrir Outlook</a>
      <button class="btn ghost" type="button" id="mail-out">Déconnecter</button>`;
    $("#mail-out").addEventListener("click", async () => {
      await fetch("/api/mail/disconnect", { method: "POST" });
      delete store["/api/mails"];
      toast("Outlook déconnecté");
      viewMails();
    });
    $("#mails").innerHTML = `<p style="margin:-10px 0 16px;color:var(--muted)">${m.unread} non lu${m.unread > 1 ? "s" : ""} dans la boîte de réception</p>
      <div class="panel mail-list mails-page">${m.messages.map(mailRow).join("") || '<div class="empty">Boîte de réception vide.</div>'}</div>`;
  } catch (e) {
    const box = $("#mails");
    if (e.code === "mail_not_connected") {
      box.innerHTML = mailConnect();
      bindMailConnect(box, () => { viewMails(); badges(); });
    } else box.innerHTML = errorBox(e, "Outlook");
  }
}

/* ── Routeur ───────────────────────────────────────────── */
const ROUTES = { "": ["home", viewHome], planning: ["planning", viewPlanning], ressources: ["ressources", viewResources], devoirs: ["devoirs", viewAssignments], notes: ["notes", viewNotes], mails: ["mails", viewMails] };

function route() {
  if (document.body.classList.contains("locked")) return;
  const key = location.hash.replace(/^#\/?/, "").split("?")[0];
  const [name, view] = ROUTES[key] || ROUTES[""];
  document.querySelectorAll(".nav a").forEach((a) => { if (a.dataset.route === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  return view();
}

$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh");
  b.classList.add("spin");
  forceNext = true;
  try { await route(); badges(); } finally {
    forceNext = false;
    setTimeout(() => b.classList.remove("spin"), 600);
  }
});

window.addEventListener("hashchange", () => { route(); main.focus({ preventScroll: true }); window.scrollTo({ top: 0 }); });

// Rafraîchit l'affichage chaque minute (ligne « maintenant », comptes à rebours).
setInterval(() => {
  if (document.hidden) return;
  const key = location.hash.replace(/^#\/?/, "");
  if (key === "" || key === "planning" || key === "devoirs") route();
  badges();
}, 60000);

function showLogin(message) {
  document.body.classList.add("locked");
  const me = window.__me;
  main.innerHTML = `<form class="panel login" id="login" autocomplete="off">
    <div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i></span><span>IUT Nice<small>BUT Informatique</small></span></div>
    <h1>Connexion</h1>
    <p>Avec ton compte de l'université.</p>
    <div class="msg" id="login-msg" role="alert">${esc(message || "")}</div>
    <label>Identifiant UniCA<input name="login" value="${esc(me.login || "")}" autocomplete="username" autofocus required></label>
    <label>Adresse mail<input name="mail" type="email" value="${esc(me.mail || "")}" autocomplete="email"></label>
    <label>Mot de passe<input name="password" type="password" autocomplete="current-password"></label>
    <label class="remember"><input name="remember" type="checkbox"> Se souvenir de moi</label>
    <button class="btn primary" type="submit">Se connecter</button>
    <p class="note">Ton mot de passe n'est jamais enregistré. « Se souvenir de moi » garde seulement une session Moodle et Outlook sur cet ordinateur, jusqu'à ce que tu cliques sur Se déconnecter. Après un redémarrage, les notes te redemanderont ton mot de passe.</p>
  </form>`;
  $("#login").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target, btn = $("button", f), msg = $("#login-msg");
    btn.disabled = true;
    btn.textContent = "Connexion à Moodle…";
    msg.textContent = "";
    try {
      const r = await fetch("/api/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login: f.login.value, mail: f.mail.value, password: f.password.value, remember: f.remember.checked }),
      });
      const data = await r.json();
      if (!r.ok || data.error) throw new Error(data.error || `HTTP ${r.status}`);
      f.password.value = "";
      window.__me = await fetch("/api/me").then((x) => x.json());
      start();
    } catch (e) {
      msg.textContent = e.message;
      btn.disabled = false;
      btn.textContent = "Se connecter";
      f.password.focus();
    }
  });
}

function start() {
  document.body.classList.remove("locked");
  Object.keys(store).forEach((k) => delete store[k]);
  setStatus("moodle", "idle");
  if (!window.__me.sources.mail) setStatus("mail", "off");
  if (!window.__me.sources.notes) setStatus("notes", "off");
  route();
  badges();
}

/* ── Thème clair / sombre (mémorisé dans localStorage, clair par défaut) ── */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#theme-label").textContent = t === "dark" ? "Thème clair" : "Thème sombre";
  try { localStorage.setItem("theme", t); } catch { /* stockage indisponible */ }
}
$("#theme-label").textContent = document.documentElement.dataset.theme === "dark" ? "Thème clair" : "Thème sombre";
$("#theme").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

$("#logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  location.hash = "";
  location.reload();
});

(async function init() {
  window.__me = await fetch("/api/me").then((r) => r.json());
  if (window.__me.demo) $("#logout").hidden = true;
  if (!window.__me.loggedIn) return showLogin();
  start();
})();
