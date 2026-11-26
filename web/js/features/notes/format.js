/* Notes : formats des moyennes et couleur selon le seuil. */
export const fmt = (v, d = 2) => (v == null ? "–" : v.toFixed(d).replace(".", ","));
export const fmtInt = (v) => (Number.isInteger(v) ? String(v) : fmt(v, 1));
// ≥ 10 normal, de 8 à 10 orange, < 8 rouge (une UE sous 8 ne se compense pas en BUT).
export const gradeCls = (v) => (v == null ? "g-none" : v >= 10 ? "g-ok" : v >= 8 ? "g-warn" : "g-bad");
