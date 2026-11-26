/* Table des routes (#/…), affichage de la vue et lien actif du menu. */
import { viewAssignments } from "./views/devoirs.js";
import { viewHome } from "./views/home.js";
import { viewMails } from "./views/mails.js";
import { viewNotes } from "./views/notes.js";
import { viewPlanning } from "./views/planning.js";
import { viewSettings } from "./views/reglages.js";
import { viewResources } from "./views/ressources.js";

const ROUTES = { "": ["home", viewHome], planning: ["planning", viewPlanning], ressources: ["ressources", viewResources], devoirs: ["devoirs", viewAssignments], notes: ["notes", viewNotes], mails: ["mails", viewMails], reglages: ["reglages", viewSettings] };

export function route() {
  if (document.body.classList.contains("locked")) return;
  const key = location.hash.replace(/^#\/?/, "").split("?")[0];
  const [name, view] = ROUTES[key] || ROUTES[""];
  document.querySelectorAll(".nav a, .side-link").forEach((a) => { if (a.dataset.route === name) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  return view();
}
