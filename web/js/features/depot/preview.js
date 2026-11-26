/* Dépôt : aperçu d'un fichier avant la remise (contenu d'un ZIP, ou ouverture dans un nouvel onglet). */
import { $, esc } from "../../core/dom.js";
import { toast } from "../../core/api.js";
import { extOf, fmtSize, plural, flags } from "./checks.js";
import { zipEntries } from "./zip.js";

const PREVIEW_MIME = { pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", gif: "image/gif", webp: "image/webp",
  txt: "text/plain", md: "text/plain", csv: "text/plain", json: "text/plain", py: "text/plain", js: "text/plain", java: "text/plain",
  c: "text/plain", h: "text/plain", cpp: "text/plain", php: "text/plain", sql: "text/plain", sh: "text/plain", css: "text/plain", xml: "text/plain" };

async function itemBlob(it) {
  if (it.file) return it.file;
  const r = await fetch(`/api/file?u=${encodeURIComponent(it.url)}`);
  if (!r.ok) throw new Error("Impossible de télécharger ce fichier depuis Moodle.");
  return r.blob();
}

// it : fichier de la liste de vérification (n° i) du devoir a, affiché dans box.
export async function previewItem(box, a, it, i) {
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
      flags(a, it, entries).forEach((f) => { if (![...fl.children].some((li) => li.textContent === f)) fl.insertAdjacentHTML("beforeend", `<li>${esc(f)}</li>`); });
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
