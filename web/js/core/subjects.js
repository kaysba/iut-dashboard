/* Couleurs par matière.
   Matières et couleurs de secours viennent des réglages (via /api/me), premier motif qui correspond : l'ordre compte. */
import { esc } from "./dom.js";
import { state } from "./state.js";

const DEFAULT_FALLBACK = "#8A94A3";
let subjectCache = { me: null, list: [], fallback: [DEFAULT_FALLBACK] };

function subjectConfig() {
  const me = state.me || {};
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

const norm = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function subjectOf(...texts) {
  const { list, fallback } = subjectConfig();
  const t = norm(texts.join(" "));
  const hit = list.find((x) => x.re.test(t));
  if (hit) return hit;
  const code = (t.match(/\br\d\.\d+/) || [t])[0];
  let h = 0;
  for (const c of code) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return { name: "", color: fallback[h % fallback.length] };
}

export const subjStyle = (sub) => `--sc:${sub.color}`;
export const subjTag = (sub, label) => `<span class="tag subj" style="${subjStyle(sub)}">${esc(label || sub.name)}</span>`;
