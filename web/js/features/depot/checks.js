/* Dépôt : formats d'affichage, contraintes du devoir, contrôles des fichiers et signaux d'alerte. */
import { DAY, fDate } from "../../core/dates.js";
import { knownFiles } from "../../components/due.js";

export const fmtSize = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(n >= 10485760 ? 0 : 1).replace(".", ",")} Mo`
  : n >= 1024 ? `${Math.round(n / 1024)} Ko` : `${n} o`);
export const extOf = (name) => ((name.match(/\.([^.]+)$/) || [])[1] || "").toLowerCase();
export const fmtWhen = (ms) => { const d = new Date(ms); return `${fDate.format(d)} à ${d.getHours()} h ${String(d.getMinutes()).padStart(2, "0")}`; };
export const plural = (n, w) => `${n} ${w}${n > 1 ? "s" : ""}`;
export const typeLabel = (name) => (extOf(name) ? `.${extOf(name)}` : "fichier");

export function constraints(d) {
  const parts = [`${plural(d.max_fichiers, "fichier")} max`];
  if (d.taille_max) parts.push(fmtSize(d.taille_max));
  if (d.types.length) parts.push(d.types.join(" ou "));
  return parts.join(" · ");
}

// Contrôle immédiat d'un fichier choisi (le serveur refait les mêmes contrôles).
export function checkFile(d, file) {
  if (d.types.length && !d.types.some((t) => file.name.toLowerCase().endsWith(t))) {
    return `${file.name} n'est pas accepté : ce devoir demande un ${d.types.join(" ou ")}.`;
  }
  if (d.taille_max && file.size > d.taille_max) {
    return `${file.name} est trop gros (${fmtSize(file.size)}) : ce devoir accepte ${fmtSize(d.taille_max)} au maximum.`;
  }
  return "";
}

// Signaux affichés sur l'écran de vérification, pour le fichier it du devoir a.
export function flags(a, it, zipInfo) {
  const out = [];
  if (it.size === 0) out.push("Fichier vide (0 octet)");
  if (it.modified && Date.now() - it.modified > 7 * DAY) out.push(`Modifié il y a ${Math.round((Date.now() - it.modified) / DAY)} jours`);
  const other = knownFiles.get(it.name.toLowerCase());
  if (other && other.id !== a.id) out.push(`Même nom qu'un fichier rendu pour « ${other.name} »`);
  if (zipInfo && !zipInfo.some((e) => !e.dir)) out.push("ZIP vide");
  if (zipInfo && zipInfo.some((e) => /^__MACOSX\//.test(e.name) || /(^|\/)\.git\//.test(e.name))) out.push("Contient des dossiers parasites (__MACOSX ou .git)");
  return out;
}
