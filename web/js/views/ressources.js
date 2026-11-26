/* Vue : Ressources (documents des cours Moodle). */
import { errorBox, resources, skel } from "../core/api.js";
import { fDate } from "../core/dates.js";
import { $, ICON, esc, main } from "../core/dom.js";
import { subjStyle, subjTag, subjectOf } from "../core/subjects.js";

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

export async function viewResources() {
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
