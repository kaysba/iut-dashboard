/* Dashboard IUT : interface. Modules ES natifs, aucune dépendance. */
import { $, main, esc, ICON } from "./core/dom.js";
import { DAY, fWeekday, fDayMonth, fDate, hm, startOfDay, addDays, monday, sameDay, cap, longDay, relDay, countdown } from "./core/dates.js";
import { store, setForceNext, api, setStatus, errorBox, skel, toast, planning, assignments, mailsData, resources, postJSON, refreshMe, dropStore, saveSettings, logout } from "./core/api.js";
import { state } from "./core/state.js";
import { on } from "./core/events.js";
import { subjectOf, subjStyle, subjTag } from "./core/subjects.js";
import { openModal, confirmModal } from "./core/modal.js";
import { themeMode, setTheme, syncTheme, initTheme } from "./core/theme.js";
import { evMeta, strip, slots } from "./components/strip.js";
import { rankPill } from "./components/rank.js";
import { depotStore, knownFiles, disableDepot, rememberFiles, dueRow } from "./components/due.js";
import { renderDS } from "./components/ds.js";
import { mailRow, installMailClicks, mailConnect, bindMailConnect } from "./components/mail.js";

function badges() {
  assignments().then((list) => {
    const now = Date.now() / 1000;
    const n = list.filter((a) => a.status !== "rendu" && a.due && a.due < now + 7 * 86400).length;
    $("#nav-devoirs").textContent = n || "";
  }).catch(() => {});
  if (state.me.sources.notes) {
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


/* ── Dépôt de fichiers ─────────────────────────────────── */
const fmtSize = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(n >= 10485760 ? 0 : 1).replace(".", ",")} Mo`
  : n >= 1024 ? `${Math.round(n / 1024)} Ko` : `${n} o`);
const extOf = (name) => ((name.match(/\.([^.]+)$/) || [])[1] || "").toLowerCase();
const fmtWhen = (ms) => { const d = new Date(ms); return `${fDate.format(d)} à ${d.getHours()} h ${String(d.getMinutes()).padStart(2, "0")}`; };
const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;
const typeLabel = (name) => (extOf(name) ? `.${extOf(name)}` : "fichier");


function constraints(d) {
  const parts = [`${plural(d.max_fichiers, "fichier")} max`];
  if (d.taille_max) parts.push(fmtSize(d.taille_max));
  if (d.types.length) parts.push(d.types.join(" ou "));
  return parts.join(" · ");
}

// Contrôle immédiat d'un fichier choisi (le serveur refait les mêmes contrôles).
function checkFile(d, file) {
  if (d.types.length && !d.types.some((t) => file.name.toLowerCase().endsWith(t))) {
    return `${file.name} n'est pas accepté : ce devoir demande un ${d.types.join(" ou ")}.`;
  }
  if (d.taille_max && file.size > d.taille_max) {
    return `${file.name} est trop gros (${fmtSize(file.size)}) : ce devoir accepte ${fmtSize(d.taille_max)} au maximum.`;
  }
  return "";
}

/* Lecture du répertoire central d'un ZIP, sans bibliothèque : liste des fichiers qu'il contient. */
async function zipEntries(blob) {
  const tailLen = Math.min(blob.size, 65557);
  const tail = new DataView(await blob.slice(blob.size - tailLen).arrayBuffer());
  let eocd = -1;
  for (let i = tailLen - 22; i >= 0; i--) if (tail.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("Ce fichier n'est pas un ZIP valide.");
  const cdSize = tail.getUint32(eocd + 12, true), cdOff = tail.getUint32(eocd + 16, true);
  if (cdOff === 0xffffffff) throw new Error("ZIP64 : liste non disponible.");
  const cd = new DataView(await blob.slice(cdOff, cdOff + cdSize).arrayBuffer());
  const entries = [];
  for (let p = 0; p + 46 <= cd.byteLength && cd.getUint32(p, true) === 0x02014b50;) {
    const flags = cd.getUint16(p + 8, true), size = cd.getUint32(p + 24, true);
    const n = cd.getUint16(p + 28, true), e = cd.getUint16(p + 30, true), c = cd.getUint16(p + 32, true);
    const name = new TextDecoder(flags & 0x800 ? "utf-8" : "windows-1252").decode(new Uint8Array(cd.buffer, cd.byteOffset + p + 46, n));
    entries.push({ name, size, dir: name.endsWith("/") });
    p += 46 + n + e + c;
  }
  return entries;
}

const PREVIEW_MIME = { pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  txt: "text/plain", md: "text/plain", csv: "text/plain", json: "text/plain", py: "text/plain", js: "text/plain", java: "text/plain",
  c: "text/plain", h: "text/plain", cpp: "text/plain", php: "text/plain", sql: "text/plain", sh: "text/plain", css: "text/plain", xml: "text/plain" };

async function itemBlob(it) {
  if (it.file) return it.file;
  const r = await fetch(`/api/file?u=${encodeURIComponent(it.url)}`);
  if (!r.ok) throw new Error("Impossible de télécharger ce fichier depuis Moodle.");
  return r.blob();
}

function sendXhr(url, body, onProgress, tooBig) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", url);
    if (typeof body === "string") x.setRequestHeader("Content-Type", "application/json");
    x.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total); };
    x.onload = () => {
      let data;
      try { data = JSON.parse(x.responseText); } catch { data = { error: `Réponse illisible (HTTP ${x.status})` }; }
      if (x.status >= 200 && x.status < 300 && !data.error) resolve(data);
      else reject(Object.assign(new Error(x.status === 413 && tooBig && tooBig() ? "Fichier trop gros pour ce devoir" : (data.error || `HTTP ${x.status}`)), { code: data.code }));
    };
    x.onerror = () => reject(new Error(tooBig && tooBig() ? "Fichier trop gros pour ce devoir" : "Envoi interrompu : vérifie que le dashboard tourne toujours."));
    x.send(body);
  });
}

function openDepot(id) {
  const a = depotStore[id];
  if (!a || $("#depot-modal")) return;
  const st = { a, depot: a.depot, staged: [], garder: true, view: "form", busy: false, msg: "", errs: [], dirty: false,
    verifie: false, decl: false, opener: document.activeElement, result: null, sent: [] };
  const { box, close } = openModal({
    id: "depot-modal",
    className: "dp",
    labelledBy: "dp-title",
    opener: st.opener,
    // Pas de fermeture pendant un envoi ; Échap revient au formulaire depuis l'écran rouge.
    onEscape: (shut) => {
      if (st.busy) return;
      if (st.view === "review") { st.view = "form"; render("[data-act=review]"); } else shut();
    },
    onBackdrop: (shut) => { if (!st.busy && st.view === "form") shut(); },
    onClose: () => {
      clearInterval(st.timer);
      if (st.dirty) { delete store["/api/assignments"]; route(); badges(); }
    },
  });
  st.box = box;

  const head = () => {
    const d = new Date(a.due * 1000);
    const late = a.due && a.due < Date.now() / 1000;
    return `<header class="dp-head"><div><h2 id="dp-title">${esc(a.name)}</h2>
      <p>${subjTag(subjectOf(a.course, a.courseShort), a.courseShort || a.course)}
      ${a.due ? `<span class="${late ? "dp-late" : ""}">date limite : ${esc(fDate.format(d))}, ${hm(d)} · ${esc(countdown(a.due))}</span>` : "<span>pas de date limite</span>"}</p></div>
      <button class="btn icon" type="button" data-act="close" aria-label="Fermer"${st.busy ? " disabled" : ""}>${ICON.close}</button></header>`;
  };

  const existing = () => st.depot.fichiers_actuels;
  const kept = () => (st.garder ? existing().filter((f) => !st.staged.some((s) => s.file.name === f.nom)) : []);
  const reviewItems = () => {
    const remote = (st.depot.remise_requise ? existing() : kept()).map((f) => ({ name: f.nom, size: f.taille, modified: (f.modifie || 0) * 1000, url: f.url }));
    const local = st.depot.remise_requise ? [] : st.staged.map((s) => ({ name: s.file.name, size: s.file.size, modified: s.file.lastModified, file: s.file }));
    return [...remote, ...local];
  };

  function renderForm() {
    const d = st.depot, ex = existing();
    const countKept = kept().length;
    const info = !ex.length || !st.staged.length ? ""
      : st.garder ? (ex.length > 1 ? `Ajouté aux ${ex.length} fichiers déjà déposés.` : "Ajouté au fichier déjà déposé.")
        : "Ces fichiers remplaceront ton dépôt actuel.";
    const actions = d.remise_requise
      ? `<button class="btn" type="button" data-act="save"${st.staged.length && !st.busy ? "" : " disabled"}>Enregistrer le brouillon</button>
         <button class="btn danger" type="button" data-act="review"${d.statut === "brouillon" && !st.staged.length && !st.busy ? "" : " disabled"}
           title="${d.statut === "brouillon" && !st.staged.length ? "" : "Enregistre d'abord ton brouillon"}">Rendre définitivement</button>`
      : `<button class="btn danger" type="button" data-act="review"${st.staged.length && !st.busy ? "" : " disabled"}>Déposer</button>`;
    return `${head()}<div class="dp-body">
      <p class="dp-rules">${esc(constraints(d))}</p>
      ${st.msg ? `<p class="dp-ok" role="status">${esc(st.msg)}</p>` : ""}
      ${ex.length ? `<h3>Fichiers déjà déposés</h3><ul class="dp-files">${ex.map((f, i) => `<li><span class="dp-name">${esc(f.nom)}</span>
        <span class="dp-meta">${fmtSize(f.taille)}</span><a class="linkish" href="/api/file?u=${encodeURIComponent(f.url)}" target="_blank" rel="noopener">Télécharger</a>
        ${ex.length > 1 && d.remise_requise ? `<button class="btn ghost" type="button" data-act="del" data-i="${i}"${st.busy ? " disabled" : ""}>Retirer</button>` : ""}</li>`).join("")}</ul>` : ""}
      <div class="dp-zone" id="dp-zone" role="button" tabindex="0" aria-label="Glisser des fichiers ici ou choisir un fichier">
        <p>${ICON.dl}<span>Glisse ${d.max_fichiers > 1 ? "tes fichiers" : "ton fichier"} ici</span></p>
        <button class="btn" type="button" data-act="pick"${st.busy ? " disabled" : ""}>Choisir ${d.max_fichiers > 1 ? "des fichiers" : "un fichier"}</button>
        <input type="file" id="dp-input" ${d.max_fichiers > 1 ? "multiple" : ""} accept="${esc(d.types.join(","))}" hidden></div>
      ${st.errs.length ? `<ul class="dp-errs" role="alert">${st.errs.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
      ${st.staged.length ? `<h3>À envoyer</h3><ul class="dp-files">${st.staged.map((s, i) => `<li><span class="dp-name">${esc(s.file.name)}</span>
        <span class="dp-meta">${fmtSize(s.file.size)}</span>
        <button class="btn ghost" type="button" data-act="unstage" data-i="${i}"${st.busy ? " disabled" : ""}>Retirer</button></li>`).join("")}</ul>` : ""}
      ${st.staged.length && ex.length ? `<fieldset class="dp-mode"><legend class="sr">Que faire des fichiers déjà déposés ?</legend>
        <label><input type="radio" name="mode" value="add"${st.garder ? " checked" : ""}> Ajouter aux fichiers déjà déposés</label>
        <label><input type="radio" name="mode" value="replace"${st.garder ? "" : " checked"}> Remplacer mon dépôt actuel</label></fieldset>` : ""}
      ${info ? `<p class="dp-note" role="status">${esc(info)}${st.garder && countKept + st.staged.length > d.max_fichiers ? " (trop de fichiers pour ce devoir : choisis « Remplacer »)" : ""}</p>` : ""}
      ${st.busy ? `<div class="dp-prog"><div class="dp-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${st.pct || 0}"><i style="width:${st.pct || 0}%"></i></div>
        <p id="dp-prog-txt">${st.pct >= 100 ? "Enregistrement dans Moodle…" : `Envoi… ${st.pct || 0} %`}</p></div>` : ""}
    </div>
    <footer class="dp-foot"><a class="linkish" href="${esc(a.url)}" target="_blank" rel="noopener">Voir sur Moodle</a><span class="dp-spacer"></span>${actions}</footer>`;
  }

  function flags(it, zipInfo) {
    const out = [];
    if (it.size === 0) out.push("Fichier vide (0 octet)");
    if (it.modified && Date.now() - it.modified > 7 * DAY) out.push(`Modifié il y a ${Math.round((Date.now() - it.modified) / DAY)} jours`);
    const other = knownFiles.get(it.name.toLowerCase());
    if (other && other.id !== a.id) out.push(`Même nom qu'un fichier rendu pour « ${other.name} »`);
    if (zipInfo && !zipInfo.some((e) => !e.dir)) out.push("ZIP vide");
    if (zipInfo && zipInfo.some((e) => /^__MACOSX\//.test(e.name) || /(^|\/)\.git\//.test(e.name))) out.push("Contient des dossiers parasites (__MACOSX ou .git)");
    return out;
  }

  function renderReview() {
    const d = st.depot, items = reviewItems();
    const late = a.due && a.due < Date.now() / 1000;
    const due = new Date(a.due * 1000);
    return `<div class="dp-danger"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 2.8 19.5h18.4zM12 10v4.5M12 17.2v.1"/></svg>
        <div><h2 id="dp-title">Tu es sûr de vouloir rendre ce devoir ?</h2><p>Après la remise, tu ne pourras peut-être plus modifier ton dépôt.</p></div></div>
      <div class="dp-body">
        <div class="dp-recap"><h3>${esc(a.name)}</h3>
          <p>${subjTag(subjectOf(a.course, a.courseShort), a.courseShort || a.course)}
          ${a.due ? `date limite : ${esc(fDate.format(due))}, ${hm(due)}` : "pas de date limite"}
          ${late ? `<b class="dp-late"> · En retard de ${esc(countdown(a.due).replace(/^en retard de /, ""))}</b>` : ""}</p></div>
        <h3>Ce qui sera rendu (${plural(items.length, "fichier")})</h3>
        <ul class="dp-review">${items.length ? items.map((it, i) => `<li data-i="${i}"><div class="dp-row"><div class="dp-fi"><span class="dp-name">${esc(it.name)}</span>
          <span class="dp-meta">${fmtSize(it.size)} · ${esc(typeLabel(it.name))}${it.modified ? ` · modifié le ${esc(fmtWhen(it.modified))}` : ""}</span></div>
          <button class="btn" type="button" data-act="preview" data-i="${i}">Aperçu</button></div>
          <ul class="dp-flags" id="fl-${i}">${flags(it).map((f) => `<li>${esc(f)}</li>`).join("")}</ul><div class="dp-zip" id="zip-${i}" hidden></div></li>`).join("")
          : '<li class="dp-meta">Aucun fichier : ce dépôt serait vide.</li>'}</ul>
        <div class="dp-checks">
          <label class="dp-check"><input type="checkbox" id="dp-verif"${st.verifie ? " checked" : ""}> <span>J'ai vérifié les fichiers que je rends.</span></label>
          ${d.declaration ? `<label class="dp-check"><input type="checkbox" id="dp-decl"${st.decl ? " checked" : ""}> <span>${esc(d.texte_declaration)}</span></label>` : ""}
        </div>
        ${st.errs.length ? `<ul class="dp-errs" role="alert">${st.errs.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}
        ${st.busy ? `<div class="dp-prog"><div class="dp-bar"><i style="width:${st.pct || 0}%"></i></div><p>${st.pct >= 100 || st.pct === undefined ? "Enregistrement dans Moodle…" : `Envoi… ${st.pct} %`}</p></div>` : ""}
      </div>
      <footer class="dp-foot"><button class="btn" type="button" data-act="back"${st.busy ? " disabled" : ""}>Revenir en arrière</button><span class="dp-spacer"></span>
        <button class="btn danger" type="button" id="dp-go" data-act="go" disabled>Rendre définitivement</button></footer>`;
  }

  function renderDone() {
    const d = st.depot, files = existing().map((f) => f.nom);
    const expected = st.sent;
    const missing = expected.filter((n) => !files.includes(n));
    const expectStatus = d.remise_requise && st.result === "draft" ? "brouillon" : (d.remise_requise || st.result === "direct" ? "remis" : "remis");
    const bad = missing.length > 0 || d.statut !== expectStatus;
    const label = d.statut === "remis" ? "Remis" : d.statut === "brouillon" ? "Brouillon enregistré" : "Pas de dépôt";
    return `${head()}<div class="dp-body">
      ${bad ? `<div class="dp-alert" role="alert"><b>Moodle ne montre pas ce que tu viens d'envoyer.</b>
        <p>${missing.length ? `Fichiers absents : ${esc(missing.join(", "))}. ` : ""}${d.statut !== expectStatus ? `Statut affiché par Moodle : « ${esc(d.statut)} ». ` : ""}Vérifie sur la page Moodle avant la date limite.</p>
        <a class="btn" href="${esc(a.url)}" target="_blank" rel="noopener">Ouvrir la page Moodle</a></div>` : ""}
      <div class="dp-status ${bad ? "bad" : "ok"}"><b>${esc(label)}${d.modifie ? ` le ${esc(fmtWhen(d.modifie * 1000))}` : ""} · ${plural(files.length, "fichier")}</b></div>
      <ul class="dp-files">${existing().map((f) => `<li><span class="dp-name">${esc(f.nom)}</span><span class="dp-meta">${fmtSize(f.taille)}</span></li>`).join("")}</ul>
    </div><footer class="dp-foot"><a class="linkish" href="${esc(a.url)}" target="_blank" rel="noopener">Voir sur Moodle</a><span class="dp-spacer"></span>
      <button class="btn primary" type="button" data-act="close">Fermer</button></footer>`;
  }

  function render(focusSel) {
    box.innerHTML = st.view === "review" ? renderReview() : st.view === "done" ? renderDone() : renderForm();
    bind();
    const target = (focusSel && box.querySelector(focusSel)) || (st.view === "review" ? $("[data-act=back]", box) : st.view === "done" ? $("[data-act=close]", box) : $("#dp-zone", box));
    if (target) target.focus();
  }

  function addFiles(list) {
    const d = st.depot;
    st.errs = [];
    st.msg = "";
    for (const file of list) {
      const err = checkFile(d, file);
      if (err) { st.errs.push(err); continue; }
      if (d.max_fichiers === 1) st.staged = [{ file }];
      else if (st.staged.some((s) => s.file.name === file.name)) st.staged = st.staged.map((s) => (s.file.name === file.name ? { file } : s));
      else if (st.staged.length + (st.garder ? existing().filter((f) => !st.staged.some((s) => s.file.name === f.nom) && f.nom !== file.name).length : 0) >= d.max_fichiers) {
        st.errs.push(`Trop de fichiers : ce devoir en accepte ${d.max_fichiers} au maximum.`);
      } else st.staged.push({ file });
    }
    render("#dp-zone");
  }

  function bind() {
    const zone = $("#dp-zone", box), input = $("#dp-input", box);
    if (zone) {
      ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); if (!st.busy) zone.classList.add("over"); }));
      ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("over"); }));
      zone.addEventListener("drop", (e) => { if (!st.busy) addFiles([...e.dataTransfer.files]); });
      zone.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === zone) { e.preventDefault(); input.click(); } });
      input.addEventListener("change", () => { addFiles([...input.files]); input.value = ""; });
      box.querySelectorAll("input[name=mode]").forEach((r) => r.addEventListener("change", () => { st.garder = r.value === "add"; render(`input[name=mode][value=${r.value}]`); }));
    }
    const verif = $("#dp-verif", box), decl = $("#dp-decl", box);
    if (verif) {
      const gate = () => {
        st.verifie = verif.checked;
        st.decl = decl ? decl.checked : true;
        clearInterval(st.timer);
        const go = $("#dp-go", box);
        if (!go) return;
        if (!(st.verifie && st.decl)) { go.disabled = true; go.textContent = "Rendre définitivement"; return; }
        let left = 3;
        go.disabled = true;
        go.textContent = `Rendre définitivement (${left})`;
        st.timer = setInterval(() => {
          left -= 1;
          if (left <= 0) { clearInterval(st.timer); go.disabled = st.busy; go.textContent = "Rendre définitivement"; } else go.textContent = `Rendre définitivement (${left})`;
        }, 1000);
      };
      verif.addEventListener("change", gate);
      if (decl) decl.addEventListener("change", gate);
      if (st.verifie && (!decl || st.decl)) gate();
    }
  }

  async function run(fn) {
    st.busy = true; st.errs = []; st.pct = 0;
    render(st.view === "review" ? null : "[data-act=save]");
    try { await fn(); } catch (e) {
      st.busy = false;
      if (e.code === "login_required") { close(); showLogin("Ta session a expiré. Reconnecte-toi."); return; }
      if (e.code === "depot_refuse") {
        disableDepot();
        st.dirty = true;
        st.view = "form";
        st.errs = [e.message];
        st.depot = { ...st.depot, ouvert: false, raison_fermeture: e.message };
        render();
        return;
      }
      st.errs = [e.message];
      render(st.view === "review" ? "[data-act=back]" : "#dp-zone");
      return;
    }
    st.busy = false;
  }

  const sendFiles = (extra) => {
    const fd = new FormData();
    fd.append("garder_existants", st.garder ? "1" : "0");
    Object.entries(extra || {}).forEach(([k, v]) => fd.append(k, v));
    st.staged.forEach((s) => fd.append("fichiers", s.file, s.file.name));
    return sendXhr(`/api/assignments/${a.id}/draft`, fd, (p) => {
      st.pct = Math.round(p * 100);
      const bar = $(".dp-bar i", box), txt = $("#dp-prog-txt", box);
      if (bar) bar.style.width = `${st.pct}%`;
      if (txt) txt.textContent = st.pct >= 100 ? "Enregistrement dans Moodle…" : `Envoi… ${st.pct} %`;
    }, () => st.depot.taille_max && st.staged.reduce((n, s) => n + s.file.size, 0) > st.depot.taille_max);
  };

  box.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-act]");
    if (!b || b.disabled) return;
    const act = b.dataset.act, i = +b.dataset.i;
    if (act === "close") { if (!st.busy) close(); }
    else if (act === "pick") $("#dp-input", box).click();
    else if (act === "unstage") { st.staged.splice(i, 1); st.errs = []; render("#dp-zone"); }
    else if (act === "save") {
      st.sent = [...kept().map((f) => f.nom), ...st.staged.map((s) => s.file.name)];
      await run(async () => {
        const r = await sendFiles();
        st.depot = r.depot; st.staged = []; st.dirty = true; st.busy = false; st.result = "draft";
        st.msg = `Brouillon enregistré · ${plural(r.depot.fichiers_actuels.length, "fichier")}. Tu peux encore le modifier ou le rendre définitivement.`;
        const missing = st.sent.filter((n) => !r.depot.fichiers_actuels.some((f) => f.nom === n));
        if (missing.length || r.depot.statut !== "brouillon") { st.view = "done"; st.result = "draft"; }
        render("[data-act=review]");
      });
    } else if (act === "del") {
      const f = existing()[i];
      await run(async () => {
        const r = await sendXhr(`/api/assignments/${a.id}/delete-file`, JSON.stringify({ nom: f.nom }));
        st.depot = r.depot; st.dirty = true; st.busy = false; st.msg = `« ${f.nom} » retiré du brouillon.`;
        render("#dp-zone");
      });
    } else if (act === "review") { st.view = "review"; st.errs = []; st.verifie = st.decl = false; render(); }
    else if (act === "back") { if (!st.busy) { clearInterval(st.timer); st.view = "form"; st.errs = []; render("[data-act=review]"); } }
    else if (act === "preview") previewItem(reviewItems()[i], i);
    else if (act === "go") {
      if (!(st.verifie && (st.decl || !st.depot.declaration))) return;
      const direct = !st.depot.remise_requise;
      st.sent = reviewItems().map((it) => it.name);
      await run(async () => {
        const r = direct
          ? await sendFiles({ verifie: "1", declaration: st.depot.declaration ? "1" : "0" })
          : await sendXhr(`/api/assignments/${a.id}/submit`, JSON.stringify({ declaration: !!st.decl, verifie: true }));
        st.depot = r.depot; st.staged = []; st.dirty = true; st.busy = false; st.result = "final"; st.view = "done";
        render("[data-act=close]");
      });
    }
  });

  async function previewItem(it, i) {
    const ext = extOf(it.name);
    if (ext === "zip") {
      const holder = $(`#zip-${i}`, box);
      if (!holder.hidden) { holder.hidden = true; return; }
      holder.hidden = false;
      holder.textContent = "Lecture du ZIP…";
      try {
        const entries = await zipEntries(await itemBlob(it));
        const files = entries.filter((x) => !x.dir);
        holder.innerHTML = `<p class="dp-meta">${plural(files.length, "fichier")} dans cette archive :</p><ul>${entries.slice(0, 60).map((x) => `<li${x.dir ? ' class="dir"' : ""}>${esc(x.name)}${x.dir ? "" : ` <span class="dp-meta">${fmtSize(x.size)}</span>`}</li>`).join("")}</ul>${entries.length > 60 ? `<p class="dp-meta">… et ${entries.length - 60} autres.</p>` : ""}`;
        const fl = $(`#fl-${i}`, box);
        flags(it, entries).forEach((f) => { if (![...fl.children].some((li) => li.textContent === f)) fl.insertAdjacentHTML("beforeend", `<li>${esc(f)}</li>`); });
      } catch (err) { holder.textContent = err.message; }
      return;
    }
    const mime = PREVIEW_MIME[ext];
    if (!mime) { toast("Pas d'aperçu pour ce type de fichier : ouvre-le sur ton ordinateur pour vérifier."); return; }
    const w = window.open("", "_blank");   // ouvert tout de suite (anti-bloqueur), rempli ensuite
    try {
      const blob = new Blob([await itemBlob(it)], { type: mime });
      const url = URL.createObjectURL(blob);
      if (w) w.location.href = url; else window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 120000);
    } catch (err) { if (w) w.close(); toast(err.message); }
  }

  render();
  // État à jour depuis Moodle (le panneau ne se fie pas à la liste, qui peut dater de quelques minutes).
  fetch(`/api/assignments/${id}/depot`).then((r) => r.json()).then((s) => {
    if (s.depot && !st.busy && st.view === "form") {
      st.depot = s.depot;
      rememberFiles({ ...a, depot: s.depot });
      if (!st.staged.length) render();
    }
  }).catch(() => {});
}

document.addEventListener("click", (e) => {
  const b = e.target.closest?.("[data-depot]");
  if (b) openDepot(+b.dataset.depot);
});
installMailClicks();

/* ── Vue : Aujourd'hui ─────────────────────────────────── */
async function viewHome() {
  const today = startOfDay(new Date());
  const me = state.me;
  main.innerHTML = `<div class="home-grid">
    <header class="head">
      <div><h1>Bonjour${me.prenom ? ` ${esc(me.prenom)}` : ""}</h1><p id="next">${longDay(today)}</p></div>
      ${me.demo ? '<span class="demo-banner">Mode démo : données fictives</span>' : ""}
    </header>
    <section class="day" id="day"><div class="day-top"><h2>Ta journée</h2><span></span></div>${skel(2)}</section>
    <aside class="panel notes-col" aria-label="Notes"><div class="notes-card" id="home-notes">${skel(5)}</div></aside>
    <div class="cols">
      <div class="stack">
        <section><div class="h2"><h2>À rendre</h2><a href="#/devoirs">Tous les devoirs</a></div><div id="home-due">${skel(4)}</div></section>
        <section id="home-ds"><div class="h2"><h2>DS à venir</h2><a href="#/planning">Planning</a></div>${skel(3)}</section>
      </div>
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

  planning(today, addDays(today, 60)).then(renderDS)
    .catch((e) => { $("#home-ds").innerHTML = errorBox(e, "Emploi du temps"); });

  assignments().then((list) => {
    const now = Date.now() / 1000;
    const todo = list.filter((a) => a.status !== "rendu" && a.due && a.due > now - 7 * 86400)
      .sort((a, b) => a.due - b.due).slice(0, 3);
    $("#home-due").innerHTML = todo.length ? `<div class="due-list">${todo.map(dueRow).join("")}</div>`
      : '<div class="empty">Rien à rendre pour le moment.</div>';
  }).catch((e) => { $("#home-due").innerHTML = errorBox(e, "Moodle"); });

  mailsData().then((m) => {
    state.webmail = m.webmail;
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
        <span class="ti">${esc(e.title)}</span><span class="me">${hm(e.s)} – ${hm(e.e)}</span>${h > 62 ? `<span class="me">${esc(e.room)}</span>` : ""}${h > 76 && e.teacher ? `<span class="me">${esc(e.teacher)}</span>` : ""}</div>`;
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
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  if (params.has("cours") || params.has("cat")) {   // lien « Annales » : #/ressources?cours=R3.06&cat=Examen
    res.q = "";
    res.cat = CATS.includes(params.get("cat")) ? params.get("cat") : "Tout";
    const code = (params.get("cours") || "").toUpperCase();
    const c = code && (courses.find((x) => (x.short || "").toUpperCase() === code)
      || courses.find((x) => (x.name.match(/\b[RS]\d\.\d{2}\b/i) || [""])[0].toUpperCase() === code));
    res.course = c ? c.id : "all";
  }
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
const notesData = (sem) => api(`/api/notes${sem ? `?semestre=${sem}` : ""}`, { source: "notes", maxAge: 600000 });

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
      state.me = await fetch("/api/me").then((x) => x.json());
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
  main.innerHTML = `<header class="head"><div><h1>Mails</h1><p>${esc(state.me.mail)}</p></div><div class="toolbar" id="mail-tools"></div></header><div id="mails">${skel(8)}</div>`;
  try {
    const m = await mailsData();
    state.webmail = m.webmail;
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
const ROUTES = { "": ["home", viewHome], planning: ["planning", viewPlanning], ressources: ["ressources", viewResources], devoirs: ["devoirs", viewAssignments], notes: ["notes", viewNotes], mails: ["mails", viewMails], reglages: ["reglages", viewSettings] };

function route() {
  if (document.body.classList.contains("locked")) return;
  const key = location.hash.replace(/^#\/?/, "").split("?")[0];
  const [name, view] = ROUTES[key] || ROUTES[""];
  document.querySelectorAll(".nav a, .side-link").forEach((a) => { if (a.dataset.route === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  return view();
}

$("#refresh").addEventListener("click", async () => {
  const b = $("#refresh");
  b.classList.add("spin");
  setForceNext(true);
  try { await route(); badges(); } finally {
    setForceNext(false);
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



/* ── Connexion : assistant au premier lancement, sinon écran simple ── */
function showAuth(message) {
  if ((state.me || {}).setup) return showSetup();
  return showLogin(message);
}

const brandHTML = '<div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i></span><span>IUT Nice<small>BUT Informatique</small></span></div>';

function accountFields(me) {
  return `<label>Identifiant UniCA<input name="login" value="${esc(me.login || "")}" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="ex. ab123456" required></label>
    <label>Mot de passe<input name="password" type="password" autocomplete="current-password"></label>
    <label class="remember"><input name="remember" type="checkbox"> Se souvenir de moi</label>`;
}

// Connexion Moodle + Notes. onOk est appelé une fois connecté (après relecture de /api/me).
function bindAccount(form, label, onOk) {
  const btn = $("button[type=submit]", form), msg = $(".msg", form);
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    btn.disabled = true;
    btn.textContent = "Connexion à Moodle…";
    msg.textContent = "";
    try {
      await postJSON("/api/login", { login: form.login.value, password: form.password.value, remember: form.remember.checked });
      form.password.value = "";
      await refreshMe();
      onOk();
    } catch (e) {
      msg.textContent = e.message;
      btn.disabled = false;
      btn.textContent = label;
      form.password.focus();
    }
  });
}

const PW_NOTE = "Ton mot de passe n'est jamais enregistré. « Se souvenir de moi » garde seulement une session Moodle et Outlook sur cet ordinateur, jusqu'à ce que tu cliques sur Se déconnecter.";

function showLogin(message) {
  document.body.classList.add("locked");
  main.innerHTML = `<form class="panel login" id="login" autocomplete="off">
    ${brandHTML}
    <h1>Connexion</h1>
    <p>Avec ton compte de l'université.</p>
    <div class="msg" role="alert">${esc(message || "")}</div>
    ${accountFields(state.me)}
    <button class="btn primary" type="submit">Se connecter</button>
    <p class="note">${PW_NOTE} Après un redémarrage, les notes te redemanderont ton mot de passe.</p>
  </form>`;
  const f = $("#login");
  (f.login.value ? f.password : f.login).focus();
  bindAccount(f, "Se connecter", start);
}

/* ── Lien ADE : instructions, collage, vérification par le serveur ── */
const ADE_SITE = "https://edtweb.univ-cotedazur.fr";
function adeForm() {
  return `<div class="ade-form">
    <ol class="ade-steps">
      <li>Ouvre ADE avec le bouton ci-dessous et affiche ton emploi du temps.</li>
      <li>Clique sur l'icône <b>Exporter l'agenda</b> (un calendrier avec une flèche).</li>
      <li>Choisis une période quelconque, puis clique sur <b>Générer URL</b>.</li>
      <li>Copie l'adresse obtenue (elle contient <code>anonymous_cal.jsp</code>) et colle-la ci-dessous.</li>
    </ol>
    <a class="btn" href="${ADE_SITE}" target="_blank" rel="noopener">${ICON.ext}Ouvrir ADE</a>
    <form class="ade-input" novalidate>
      <label class="sr" for="ade-url">Lien d'export ADE</label>
      <input id="ade-url" name="url" type="url" inputmode="url" autocomplete="off" spellcheck="false"
        placeholder="https://edtweb.univ-cotedazur.fr/…/anonymous_cal.jsp?data=…">
      <button class="btn primary" type="submit">Vérifier</button>
    </form>
    <p class="check" role="status" aria-live="polite"></p>
  </div>`;
}

const coursCount = (n) => (n === 0 ? "Le lien fonctionne, mais aucun cours n'est prévu cette semaine."
  : `${n} cours trouvé${n > 1 ? "s" : ""} cette semaine`);

function bindAdeForm(root, onOk) {
  const form = $(".ade-input", root), input = form.url, msg = $(".check", root), btn = $("button", form);
  let busy = false;
  const check = async () => {
    const url = input.value.trim();
    if (!url) { msg.className = "check bad"; msg.textContent = "Colle d'abord le lien d'export ADE."; return; }
    if (busy) return;
    busy = true;
    btn.disabled = true;
    msg.className = "check wait";
    msg.textContent = "Vérification du lien auprès d'ADE…";
    try {
      const r = await postJSON("/api/settings/ade", { url });
      msg.className = "check ok";
      msg.textContent = coursCount(r.count);
      input.value = "";
      dropStore("/api/planning");
      await refreshMe();
      onOk(r);
    } catch (e) {
      if (e.code === "login_required") return showAuth("Ta session a expiré. Reconnecte-toi.");
      msg.className = "check bad";
      msg.textContent = e.message;
      input.select();
    } finally {
      busy = false;
      btn.disabled = false;
    }
  };
  form.addEventListener("submit", (ev) => { ev.preventDefault(); check(); });
  input.addEventListener("paste", () => setTimeout(check, 0));
}

/* ── Assistant de premier lancement ────────────────────── */
const wizard = { step: 1 };
const WIZ_STEPS = ["Compte UniCA", "Emploi du temps", "Mails"];

function stepsBar(n) {
  return `<ol class="steps" aria-label="Étapes">${WIZ_STEPS.map((label, i) => {
    const st = i + 1 < n ? "done" : i + 1 === n ? "current" : "";
    return `<li class="${st}"${st === "current" ? ' aria-current="step"' : ""}><b>${i + 1 < n ? "✓" : i + 1}</b><span>${label}</span></li>`;
  }).join("")}</ol>`;
}

function showSetup() {
  document.body.classList.add("locked");
  const n = wizard.step;
  const me = state.me;
  const wrap = (inner) => `<div class="panel wizard">${brandHTML}${stepsBar(n)}${inner}</div>`;
  if (n === 1) {
    main.innerHTML = wrap(`<form id="login" autocomplete="off" class="wiz-body">
      <h1>Bienvenue</h1>
      <p class="lead">Trois étapes pour régler ton tableau de bord. Seule la première est obligatoire.</p>
      <div class="msg" role="alert"></div>
      ${accountFields(me)}
      <p class="hint">Ton prénom et ton adresse mail sont lus dans ton profil Moodle : rien d'autre à remplir.</p>
      <div class="wiz-foot"><span></span><button class="btn primary" type="submit">Continuer</button></div>
      <p class="note">${PW_NOTE}</p>
    </form>`);
    const f = $("#login");
    (f.login.value ? f.password : f.login).focus();
    bindAccount(f, "Continuer", () => { wizard.step = 2; showSetup(); });
    return;
  }
  if (n === 2) {
    main.innerHTML = wrap(`<div class="wiz-body">
      <h1>Ton emploi du temps</h1>
      <p class="lead">${me.prenom ? `Bonjour ${esc(me.prenom)} ! ` : ""}Le dashboard lit ton emploi du temps dans ADE grâce à ton lien d'export personnel.</p>
      ${adeForm()}
      <div class="wiz-foot"><button class="btn ghost" type="button" id="wiz-skip">Passer cette étape</button>
        <button class="btn primary" type="button" id="wiz-next" hidden>Continuer</button></div>
    </div>`);
    bindAdeForm(main, () => { $("#wiz-next").hidden = false; $("#wiz-skip").hidden = true; $("#wiz-next").focus(); });
    $("#wiz-skip").addEventListener("click", () => { wizard.step = 3; showSetup(); });
    $("#wiz-next").addEventListener("click", () => { wizard.step = 3; showSetup(); });
    $("#ade-url").focus();
    return;
  }
  const s = me.settings || {};
  const connected = s.outlook;
  main.innerHTML = wrap(`<div class="wiz-body">
    <h1>Tes mails <span class="opt">facultatif</span></h1>
    <p class="lead">Pour voir tes derniers mails de l'université sur l'accueil.</p>
    <label class="field">Adresse mail<input id="wiz-mail" type="email" autocomplete="email" spellcheck="false"
      value="${esc(s.mail || s.mailSuggestion || "")}"></label>
    <p class="check bad" id="wiz-mail-err" role="alert"></p>
    ${connected ? '<p class="check ok">Outlook est connecté.</p>' : mailConnect({ bare: true })}
    <div class="wiz-foot"><button class="btn ghost" type="button" id="wiz-skip">Passer</button>
      <button class="btn primary" type="button" id="wiz-done">Terminer</button></div>
  </div>`);
  const mailInput = $("#wiz-mail");
  const saveMail = async () => {
    const v = mailInput.value.trim();
    if (!v || v === (state.me.settings || {}).mail) return true;
    try {
      await saveSettings({ MAIL_ADRESSE: v }, null);
      $("#wiz-mail-err").textContent = "";
      return true;
    } catch (e) {
      $("#wiz-mail-err").textContent = e.message;
      mailInput.focus();
      return false;
    }
  };
  bindMailConnect(main, async () => { await refreshMe(); showSetup(); }, saveMail);
  $("#wiz-skip").addEventListener("click", finishSetup);
  $("#wiz-done").addEventListener("click", async () => { if (await saveMail()) finishSetup(); });
}

async function finishSetup() {
  wizard.step = 1;
  await refreshMe();
  if (location.hash && location.hash !== "#/") location.hash = "#/";
  start();
}


const SET_ORIGIN = { config: "vient de config.py", defaut: "valeur par défaut" };
const originNote = (s, key) => (s.origine && SET_ORIGIN[s.origine[key]] && s.origine[key] === "config"
  ? `<span class="from">${SET_ORIGIN.config}</span>` : "");
const CACHE_LABELS = { CACHE_PLANNING: "Emploi du temps", CACHE_MOODLE: "Moodle (cours, devoirs)", CACHE_MAILS: "Mails", CACHE_NOTES: "Notes" };

function validRegex(src) { try { new RegExp(src); return ""; } catch (e) { return e.message; } }

async function viewSettings() {
  const me = state.me;
  const s = me.settings || {};
  const matieres = me.matieres || [];
  main.innerHTML = `<header class="head"><div><h1>Réglages</h1>
      <p>Enregistrés sur cet ordinateur, dès que tu changes quelque chose.</p></div></header>
    <div class="settings">
    <section class="panel set-sec" aria-labelledby="set-account"><h2 id="set-account">Compte</h2>
      <div class="set-row"><span class="set-label">Identifiant UniCA</span><span class="set-val"><b>${esc(me.login || "–")}</b></span></div>
      <div class="set-row"><span class="set-label">Prénom</span><span class="set-val"><b>${esc(me.prenom || "–")}</b><span class="from">lu dans Moodle</span></span></div>
      <div class="set-row"><span></span><span class="set-val"><button class="btn" type="button" id="set-logout">Se déconnecter</button></span></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-ade"><h2 id="set-ade">Emploi du temps</h2>
      <div class="set-row"><span class="set-label">Lien ADE</span>
        <span class="set-val">${s.ade ? `<code class="token" title="Lien masqué : il contient un jeton personnel">${esc(s.ade)}</code>${originNote(s, "ADE_ICAL_URL")}` : '<span class="muted">Aucun lien : l\'emploi du temps n\'est pas affiché.</span>'}
        <button class="btn" type="button" id="ade-change" aria-expanded="false">${s.ade ? "Changer" : "Ajouter"}</button></span></div>
      <div id="ade-box" hidden></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-mail"><h2 id="set-mail">Mails</h2>
      <div class="set-row"><label class="set-label" for="set-mail-input">Adresse</label>
        <span class="set-val"><input class="inp" id="set-mail-input" type="email" spellcheck="false" autocomplete="email"
          value="${esc(s.mail || "")}" placeholder="${esc(s.mailSuggestion || "prenom.nom@etu.unice.fr")}">${originNote(s, "MAIL_ADRESSE")}</span></div>
      <div class="set-row"><span class="set-label">Outlook</span>
        <span class="set-val"><span class="state"><i class="dot ${s.outlook ? "ok" : ""}"></i>${s.outlook ? "Connecté" : "Non connecté"}</span>
        <button class="btn" type="button" id="mail-toggle">${s.outlook ? "Déconnecter" : "Connecter"}</button></span></div>
      <div id="mail-box" hidden></div>
    </section>

    <section class="panel set-sec" aria-labelledby="set-colors"><h2 id="set-colors">Couleurs des matières</h2>
      <p class="set-help">La couleur sert dans le planning, les devoirs et les ressources.${originNote(s, "MATIERES")}</p>
      <ul class="subj-list">${matieres.map((m, i) => `<li><input type="color" value="${esc(m.couleur.toLowerCase())}" data-i="${i}" aria-label="Couleur de ${esc(m.nom || m.motif)}"><span>${esc(m.nom || m.motif)}</span></li>`).join("") || '<li class="muted">Aucune matière définie.</li>'}</ul>
      <div class="set-actions"><button class="btn" type="button" id="colors-reset">Couleurs par défaut</button></div>
      <details class="adv"><summary>Avancé : reconnaître les matières</summary>
        <p class="set-help">Chaque motif est une expression régulière, sans accents ni majuscules, comparée au nom du cours. La première qui correspond gagne.</p>
        <div class="motifs">${matieres.map((m, i) => `<div class="motif-row"><input class="inp" data-nom="${i}" value="${esc(m.nom)}" aria-label="Nom affiché">
          <input class="inp mono" data-motif="${i}" value="${esc(m.motif)}" spellcheck="false" aria-label="Motif de ${esc(m.nom)}"><span class="check bad" data-err="${i}"></span></div>`).join("")}</div>
      </details>
    </section>

    <section class="panel set-sec" aria-labelledby="set-display"><h2 id="set-display">Affichage</h2>
      <div class="set-row"><span class="set-label">Thème</span><span class="set-val">
        <span class="seg" role="group" aria-label="Thème">${["system", "light", "dark"].map((t) => `<button type="button" data-theme="${t}" aria-pressed="${themeMode() === t}">${{ system: "Système", light: "Clair", dark: "Sombre" }[t]}</button>`).join("")}</span></span></div>
      <div class="set-row top"><label class="set-label" for="set-hidden">Cours à masquer</label>
        <span class="set-val col"><textarea class="inp" id="set-hidden" rows="3" spellcheck="false" placeholder="Espace étudiants&#10;Bibliothèque">${esc((s.coursMasques || []).join("\n"))}</textarea>
        <span class="set-help">Un mot par ligne : les cours Moodle dont le nom contient ce mot sont masqués.</span></span></div>
    </section>

    <details class="panel set-sec adv-sec"><summary><h2>Avancé</h2></summary>
      <p class="set-help">Durée pendant laquelle le dashboard garde les données avant de les redemander (en minutes).</p>
      ${Object.entries(CACHE_LABELS).map(([k, label]) => `<div class="set-row"><label class="set-label" for="c-${k}">${label}</label>
        <span class="set-val"><input class="inp num" id="c-${k}" type="number" min="0" max="1440" step="1" data-cache="${k}" value="${Math.round(((s.cache || {})[k] || 0) / 60)}"> min</span></div>`).join("")}
      <div class="set-row"><label class="set-label" for="set-port">Port</label>
        <span class="set-val"><input class="inp num" id="set-port" type="number" min="1024" max="65535" value="${esc(s.port || "")}">
        <span class="set-help">Pris en compte au prochain lancement.${s.portActuel && s.port !== s.portActuel ? ` En ce moment : ${s.portActuel}.` : ""}</span></span></div>
    </details>

    <section class="panel set-sec danger-sec" aria-labelledby="set-wipe"><h2 id="set-wipe">Effacer</h2>
      <p class="set-help">Supprime de cet ordinateur la session, les jetons Moodle et Outlook et tous les réglages (lien ADE, couleurs…). Le dashboard revient à l'assistant de premier lancement.</p>
      <div class="set-actions"><button class="btn danger" type="button" id="wipe">Tout effacer de cet ordinateur</button></div>
    </section>
    </div>`;

  const fail = (e) => toast(e.message);
  $("#set-logout")?.addEventListener("click", logout);

  // Emploi du temps
  $("#ade-change").addEventListener("click", (ev) => {
    const box = $("#ade-box");
    box.hidden = !box.hidden;
    ev.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
    if (box.hidden) return;
    box.innerHTML = adeForm();
    bindAdeForm(box, (r) => { toast(`Enregistré : ${coursCount(r.count).toLowerCase()}`); setTimeout(viewSettings, 1200); });
    $("#ade-url", box).focus();
  });

  // Mails
  const mailInput = $("#set-mail-input");
  mailInput.addEventListener("change", () => {
    saveSettings({ MAIL_ADRESSE: mailInput.value.trim() || null }).then(viewSettings).catch(fail);
  });
  $("#mail-toggle").addEventListener("click", async (ev) => {
    if (s.outlook) {
      await postJSON("/api/mail/disconnect").catch(fail);
      dropStore("/api/mails");
      await refreshMe();
      toast("Outlook déconnecté");
      return viewSettings();
    }
    const box = $("#mail-box");
    box.hidden = !box.hidden;
    ev.currentTarget.setAttribute("aria-expanded", String(!box.hidden));
    box.innerHTML = box.hidden ? "" : mailConnect({ bare: true });
    bindMailConnect(box, async () => { await refreshMe(); badges(); viewSettings(); }, async () => {
      if (!mailInput.value.trim() && !s.mailSuggestion) { toast("Indique d'abord ton adresse mail."); mailInput.focus(); return false; }
      return true;
    });
  });

  // Couleurs
  const currentList = () => (state.me.matieres || []).map((m) => ({ ...m }));
  main.querySelectorAll("input[type=color]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const list = currentList();
      list[+inp.dataset.i].couleur = inp.value.toUpperCase();
      saveSettings({ MATIERES: list }).catch(fail);
    });
  });
  $("#colors-reset").addEventListener("click", () => saveSettings({ MATIERES: null }, "Couleurs par défaut remises").then(viewSettings).catch(fail));
  main.querySelectorAll("[data-motif], [data-nom]").forEach((inp) => {
    inp.addEventListener("change", () => {
      const i = +(inp.dataset.motif ?? inp.dataset.nom);
      const err = $(`[data-err="${i}"]`);
      const list = currentList();
      if (inp.dataset.motif !== undefined) {
        const bad = inp.value.trim() ? validRegex(inp.value) : "motif vide";
        err.textContent = bad ? `Motif invalide : ${bad}` : "";
        if (bad) return;
        list[i].motif = inp.value.trim();
      } else list[i].nom = inp.value.trim();
      saveSettings({ MATIERES: list }).catch((e) => { err.textContent = e.message; });
    });
  });

  // Affichage
  main.querySelectorAll("[data-theme]").forEach((b) => b.addEventListener("click", () => {
    setTheme(b.dataset.theme);
    main.querySelectorAll("[data-theme]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  }));
  const hidden = $("#set-hidden");
  hidden.addEventListener("change", () => {
    const words = hidden.value.split("\n").map((w) => w.trim()).filter(Boolean);
    saveSettings({ COURS_MASQUES: words }).catch(fail);
  });

  // Avancé
  main.querySelectorAll("[data-cache]").forEach((inp) => inp.addEventListener("change", () => {
    const v = Math.round(Number(inp.value));
    if (!Number.isFinite(v) || v < 0 || v > 1440) return toast("Durée entre 0 et 1440 minutes.");
    saveSettings({ [inp.dataset.cache]: v * 60 }).catch(fail);
  }));
  const port = $("#set-port");
  port.addEventListener("change", () => {
    const v = Number(port.value);
    if (!Number.isInteger(v) || v < 1024 || v > 65535) return toast("Le port doit être un nombre entre 1024 et 65535.");
    saveSettings({ PORT: v }, "Enregistré : pris en compte au prochain lancement").then(viewSettings).catch(fail);
  });

  // Tout effacer
  $("#wipe").addEventListener("click", async () => {
    const ok = await confirmModal({
      title: "Tout effacer de cet ordinateur ?",
      text: "Session, jetons Moodle et Outlook, lien ADE, couleurs et autres réglages seront supprimés. Il faudra refaire l'assistant.",
      ok: "Tout effacer",
    });
    if (!ok) return;
    try {
      await postJSON("/api/reset", { confirm: true });
      try { localStorage.clear(); sessionStorage.clear(); } catch { /* sans stockage */ }
      location.hash = "";
      location.reload();
    } catch (e) { fail(e); }
  });
}

function start() {
  document.body.classList.remove("locked");
  Object.keys(store).forEach((k) => delete store[k]);
  setStatus("moodle", "idle");
  if (!state.me.sources.mail) setStatus("mail", "off");
  if (!state.me.sources.notes) setStatus("notes", "off");
  if (!state.me.sources.ade) setStatus("ade", "off");
  syncTheme();
  route();
  badges();
}

on("auth-required", (message) => showAuth(message));
initTheme();
$("#logout").addEventListener("click", logout);

(async function init() {
  await refreshMe();
  syncTheme();
  if (state.me.demo && !state.me.setup && state.me.loggedIn) $("#logout").hidden = true;
  if (!state.me.loggedIn) return showAuth();
  start();
})();
