/* Panneau de dépôt : formulaire, écran rouge de vérification, résultat. */
import { $, esc, ICON } from "../../core/dom.js";
import { fDate, hm, countdown } from "../../core/dates.js";
import { store } from "../../core/api.js";
import { emit } from "../../core/events.js";
import { openModal } from "../../core/modal.js";
import { subjectOf, subjTag } from "../../core/subjects.js";
import { depotStore, disableDepot, rememberFiles } from "../../components/due.js";
import { fmtSize, fmtWhen, plural, typeLabel, constraints, checkFile, flags } from "./checks.js";
import { previewItem } from "./preview.js";

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

function head(st) {
  const a = st.a;
  const d = new Date(a.due * 1000);
  const late = a.due && a.due < Date.now() / 1000;
  return `<header class="dp-head"><div><h2 id="dp-title">${esc(a.name)}</h2>
    <p>${subjTag(subjectOf(a.course, a.courseShort), a.courseShort || a.course)}
    ${a.due ? `<span class="${late ? "dp-late" : ""}">date limite : ${esc(fDate.format(d))}, ${hm(d)} · ${esc(countdown(a.due))}</span>` : "<span>pas de date limite</span>"}</p></div>
    <button class="btn icon" type="button" data-act="close" aria-label="Fermer"${st.busy ? " disabled" : ""}>${ICON.close}</button></header>`;
}

const existing = (st) => st.depot.fichiers_actuels;
const kept = (st) => (st.garder ? existing(st).filter((f) => !st.staged.some((s) => s.file.name === f.nom)) : []);
const reviewItems = (st) => {
  const remote = (st.depot.remise_requise ? existing(st) : kept(st)).map((f) => ({ name: f.nom, size: f.taille, modified: (f.modifie || 0) * 1000, url: f.url }));
  const local = st.depot.remise_requise ? [] : st.staged.map((s) => ({ name: s.file.name, size: s.file.size, modified: s.file.lastModified, file: s.file }));
  return [...remote, ...local];
};

/* Vue 1 : formulaire (fichiers déjà déposés, zone de dépôt, envoi). */
function renderForm(st) {
  const a = st.a;
  const d = st.depot, ex = existing(st);
  const countKept = kept(st).length;
  const info = !ex.length || !st.staged.length ? ""
    : st.garder ? (ex.length > 1 ? `Ajouté aux ${ex.length} fichiers déjà déposés.` : "Ajouté au fichier déjà déposé.")
      : "Ces fichiers remplaceront ton dépôt actuel.";
  const actions = d.remise_requise
    ? `<button class="btn" type="button" data-act="save"${st.staged.length && !st.busy ? "" : " disabled"}>Enregistrer le brouillon</button>
       <button class="btn danger" type="button" data-act="review"${d.statut === "brouillon" && !st.staged.length && !st.busy ? "" : " disabled"}
         title="${d.statut === "brouillon" && !st.staged.length ? "" : "Enregistre d'abord ton brouillon"}">Rendre définitivement</button>`
    : `<button class="btn danger" type="button" data-act="review"${st.staged.length && !st.busy ? "" : " disabled"}>Déposer</button>`;
  return `${head(st)}<div class="dp-body">
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

/* Vue 2 : écran rouge de vérification avant la remise définitive. */
function renderReview(st) {
  const a = st.a;
  const d = st.depot, items = reviewItems(st);
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
        <ul class="dp-flags" id="fl-${i}">${flags(a, it).map((f) => `<li>${esc(f)}</li>`).join("")}</ul><div class="dp-zip" id="zip-${i}" hidden></div></li>`).join("")
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

/* Vue 3 : résultat, comparé à ce que Moodle affiche vraiment. */
function renderDone(st) {
  const a = st.a;
  const d = st.depot, files = existing(st).map((f) => f.nom);
  const expected = st.sent;
  const missing = expected.filter((n) => !files.includes(n));
  const expectStatus = d.remise_requise && st.result === "draft" ? "brouillon" : (d.remise_requise || st.result === "direct" ? "remis" : "remis");
  const bad = missing.length > 0 || d.statut !== expectStatus;
  const label = d.statut === "remis" ? "Remis" : d.statut === "brouillon" ? "Brouillon enregistré" : "Pas de dépôt";
  return `${head(st)}<div class="dp-body">
    ${bad ? `<div class="dp-alert" role="alert"><b>Moodle ne montre pas ce que tu viens d'envoyer.</b>
      <p>${missing.length ? `Fichiers absents : ${esc(missing.join(", "))}. ` : ""}${d.statut !== expectStatus ? `Statut affiché par Moodle : « ${esc(d.statut)} ». ` : ""}Vérifie sur la page Moodle avant la date limite.</p>
      <a class="btn" href="${esc(a.url)}" target="_blank" rel="noopener">Ouvrir la page Moodle</a></div>` : ""}
    <div class="dp-status ${bad ? "bad" : "ok"}"><b>${esc(label)}${d.modifie ? ` le ${esc(fmtWhen(d.modifie * 1000))}` : ""} · ${plural(files.length, "fichier")}</b></div>
    <ul class="dp-files">${existing(st).map((f) => `<li><span class="dp-name">${esc(f.nom)}</span><span class="dp-meta">${fmtSize(f.taille)}</span></li>`).join("")}</ul>
  </div><footer class="dp-foot"><a class="linkish" href="${esc(a.url)}" target="_blank" rel="noopener">Voir sur Moodle</a><span class="dp-spacer"></span>
    <button class="btn primary" type="button" data-act="close">Fermer</button></footer>`;
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
      if (st.dirty) { delete store["/api/assignments"]; emit("data-changed", "assignments"); }
    },
  });
  st.box = box;

  function render(focusSel) {
    box.innerHTML = st.view === "review" ? renderReview(st) : st.view === "done" ? renderDone(st) : renderForm(st);
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
      else if (st.staged.length + (st.garder ? existing(st).filter((f) => !st.staged.some((s) => s.file.name === f.nom) && f.nom !== file.name).length : 0) >= d.max_fichiers) {
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
      if (e.code === "login_required") { close(); emit("login-required", "Ta session a expiré. Reconnecte-toi."); return; }
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
      st.sent = [...kept(st).map((f) => f.nom), ...st.staged.map((s) => s.file.name)];
      await run(async () => {
        const r = await sendFiles();
        st.depot = r.depot; st.staged = []; st.dirty = true; st.busy = false; st.result = "draft";
        st.msg = `Brouillon enregistré · ${plural(r.depot.fichiers_actuels.length, "fichier")}. Tu peux encore le modifier ou le rendre définitivement.`;
        const missing = st.sent.filter((n) => !r.depot.fichiers_actuels.some((f) => f.nom === n));
        if (missing.length || r.depot.statut !== "brouillon") { st.view = "done"; st.result = "draft"; }
        render("[data-act=review]");
      });
    } else if (act === "del") {
      const f = existing(st)[i];
      await run(async () => {
        const r = await sendXhr(`/api/assignments/${a.id}/delete-file`, JSON.stringify({ nom: f.nom }));
        st.depot = r.depot; st.dirty = true; st.busy = false; st.msg = `« ${f.nom} » retiré du brouillon.`;
        render("#dp-zone");
      });
    } else if (act === "review") { st.view = "review"; st.errs = []; st.verifie = st.decl = false; render(); }
    else if (act === "back") { if (!st.busy) { clearInterval(st.timer); st.view = "form"; st.errs = []; render("[data-act=review]"); } }
    else if (act === "preview") previewItem(box, a, reviewItems(st)[i], i);
    else if (act === "go") {
      if (!(st.verifie && (st.decl || !st.depot.declaration))) return;
      const direct = !st.depot.remise_requise;
      st.sent = reviewItems(st).map((it) => it.name);
      await run(async () => {
        const r = direct
          ? await sendFiles({ verifie: "1", declaration: st.depot.declaration ? "1" : "0" })
          : await sendXhr(`/api/assignments/${a.id}/submit`, JSON.stringify({ declaration: !!st.decl, verifie: true }));
        st.depot = r.depot; st.staged = []; st.dirty = true; st.busy = false; st.result = "final"; st.view = "done";
        render("[data-act=close]");
      });
    }
  });

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

// Bouton « Déposer » d'une ligne de devoir, où qu'elle soit.
export function installDepotClicks() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest?.("[data-depot]");
    if (b) openDepot(+b.dataset.depot);
  });
}
