/* Simulateur de notes : fonctions pures, sans DOM ni réseau (tests/test_simulation.py en refait la logique en Python).
   r : relevé normalisé (/api/notes) ; sim : Map id d'évaluation -> note simulée (0 à 20).
   Seules les règles visibles dans les données sont appliquées :
   - moyenne d'un module = notes pondérées par leur coefficient (× poids de l'évaluation dans l'UE, quand on calcule
     pour une UE) ; une évaluation bonus (sans coefficient) ajoute sa note, plafonnée à 20 ;
   - moyenne d'une UE = moyennes des modules pondérées par le coefficient du module dans l'UE ;
   - moyenne générale = moyenne des UE (pondérée par les ECTS seulement s'ils diffèrent), + bonus du semestre.
   Un module qui contient un rattrapage, une session 2 ou une note non numérique (ABS…) n'est pas recalculé :
   sa moyenne officielle est gardée, et ses évaluations ne sont pas modifiables. */

export const ECART_MAX = 0.05;

const noteOf = (e, sim) => (sim && sim.has(e.id) ? sim.get(e.id) : e.note);
const typeOf = (e) => e.type || "normale";

// Module dont le calcul n'est pas connu (rattrapage, session 2, note « ABS »…).
export const moduleFige = (m) => m.evaluations.some((e) => e.etat || !["normale", "bonus"].includes(typeOf(e)));

// Poids de l'évaluation e dans l'UE ue (1 si le relevé ne donne pas de poids).
function poids(e, ue) {
  if (ue == null || !e.poids || !Object.keys(e.poids).length) return 1;
  return e.poids[ue] || 0;
}

export function moyenneModule(m, sim, ue = null) {
  let num = 0, den = 0, bonus = 0;
  for (const e of m.evaluations) {
    const n = noteOf(e, sim);
    if (n == null || !poids(e, ue)) continue;
    if (typeOf(e) === "bonus") { bonus += n; continue; }
    const c = (e.coef || 0) * poids(e, ue);
    if (!c) continue;
    num += n * c;
    den += c;
  }
  return den ? Math.min(20, num / den + bonus) : null;
}

const parCode = (r) => Object.fromEntries(r.modules.map((m) => [m.code, m]));

// Moyenne du module um (entrée de ue.modules) dans l'UE : recalculée, ou officielle si le module est figé.
export function moyenneModuleDansUE(um, ue, modules, sim) {
  const m = modules[um.code];
  if (!m || moduleFige(m)) return um.moyenne;
  return moyenneModule(m, sim, ue.code);
}

export function moyenneUE(ue, modules, sim) {
  let num = 0, den = 0;
  for (const um of ue.modules) {
    const v = moyenneModuleDansUE(um, ue, modules, sim);
    if (v == null || !um.coef) continue;
    num += v * um.coef;
    den += um.coef;
  }
  return den ? num / den : null;
}

export function moyenneGenerale(r, sim) {
  const modules = parCode(r);
  const ects = r.ues.map((u) => u.ects_total);
  const parEcts = ects.every((x) => x != null && x > 0) && new Set(ects).size > 1;
  let num = 0, den = 0;
  for (const u of r.ues) {
    const v = moyenneUE(u, modules, sim);
    if (v == null) continue;
    const w = parEcts ? u.ects_total : 1;
    num += v * w;
    den += w;
  }
  return den ? num / den + (r.semestre.bonus || 0) : null;
}

// Tout le relevé recalculé : { modules: {code: moy}, ues: {code: moy}, ueModules: {"UE|code": moy}, generale }.
export function recalculer(r, sim) {
  const modules = parCode(r);
  const out = { modules: {}, ues: {}, ueModules: {}, generale: moyenneGenerale(r, sim) };
  for (const m of r.modules) out.modules[m.code] = moduleFige(m) ? m.moyenne : moyenneModule(m, sim);
  for (const u of r.ues) {
    out.ues[u.code] = moyenneUE(u, modules, sim);
    for (const um of u.modules) out.ueModules[`${u.code}|${um.code}`] = moyenneModuleDansUE(um, u, modules, sim);
  }
  return out;
}

// Vérification de la formule : recalcul avec les vraies notes seulement, comparé aux moyennes officielles.
export function verifier(r) {
  const calc = recalculer(r, null);
  const ecarts = [];
  for (const u of r.ues) {
    const v = calc.ues[u.code];
    if (u.moyenne != null && (v == null || Math.abs(v - u.moyenne) > ECART_MAX)) ecarts.push({ code: u.code, officiel: u.moyenne, calcul: v });
  }
  const s = r.semestre.moyenne;
  const generale = s != null && (calc.generale == null || Math.abs(calc.generale - s) > ECART_MAX)
    ? { officiel: s, calcul: calc.generale } : null;
  return { ecarts, generale, base: calc };
}

// Coefficient proposé pour une note ajoutée : moyenne des coefficients du module (1 s'il n'en a pas).
export function coefParDefaut(m) {
  const c = m.evaluations.filter((e) => typeOf(e) === "normale" && e.coef > 0).map((e) => e.coef);
  return c.length ? Math.round((c.reduce((a, b) => a + b, 0) / c.length) * 100) / 100 : 1;
}

/* Relevé augmenté des notes ajoutées (« et si j'avais eu 14 en prog système »).
   ajouts : Map code du module -> [{ id (négatif), coef }] ; la note elle-même est dans sim, sous cet id.
   Une note ajoutée compte avec un poids 1 dans chaque UE où le module a un coefficient. Le relevé d'origine n'est pas modifié. */
export function avecAjouts(r, ajouts) {
  if (!ajouts || !ajouts.size) return r;
  const ues = {};
  r.ues.forEach((u) => u.modules.forEach((um) => { if (um.coef) (ues[um.code] ||= {})[u.code] = 1; }));
  return {
    ...r,
    modules: r.modules.map((m) => (ajouts.get(m.code) || []).length && !moduleFige(m)
      ? { ...m, evaluations: [...m.evaluations, ...ajouts.get(m.code).map((a) => ({
        id: a.id, titre: "Note ajoutée", type: "normale", etat: null, coef: a.coef, note: null, poids: { ...(ues[m.code] || {}) } }))] }
      : m),
  };
}

// Évaluations encore sans note (ni valeur simulée si sim est donné) qui comptent dans l'UE (hors bonus, hors modules figés).
export function restantes(ue, r, sim = null) {
  const modules = parCode(r);
  const out = [];
  for (const um of ue.modules) {
    const m = modules[um.code];
    if (!m || !um.coef || moduleFige(m)) continue;
    for (const e of m.evaluations) {
      if (e.note == null && !(sim && sim.has(e.id)) && !e.etat && typeOf(e) === "normale" && (e.coef || 0) * poids(e, ue.code) > 0) out.push(e);
    }
  }
  return out;
}

/* Note identique à mettre sur toutes les évaluations restantes de l'UE pour atteindre la cible
   (dichotomie entre 0 et 20, même calcul que moyenneUE ; les valeurs déjà saisies sont gardées).
   -> { statut: "aucune" | "acquise" | "impossible" | "note", note, n } */
export function noteMinimale(ue, r, sim, cible = 10) {
  const modules = parCode(r);
  const reste = restantes(ue, r, sim);
  if (!reste.length) return { statut: "aucune", note: null, n: 0 };
  const avec = (x) => {
    const s = new Map(sim || []);
    reste.forEach((e) => s.set(e.id, x));
    return moyenneUE(ue, modules, s);
  };
  const ok = (x) => avec(x) >= cible - 1e-9;
  if (ok(0)) return { statut: "acquise", note: 0, n: reste.length };
  if (!ok(20)) return { statut: "impossible", note: null, n: reste.length };
  let lo = 0, hi = 20;
  for (let i = 0; i < 50; i++) { const mid = (lo + hi) / 2; if (ok(mid)) hi = mid; else lo = mid; }
  return { statut: "note", note: Math.ceil(hi * 100 - 1e-6) / 100, n: reste.length };
}
