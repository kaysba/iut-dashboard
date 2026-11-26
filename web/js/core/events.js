/* Petit bus d'événements : les modules signalent un changement, main.js décide quoi redessiner.
   « data-changed » (détail : "assignments", "notes", "mails" ou "settings") ;
   « auth-required » / « login-required » (détail : message) ; « logged-in ». */
const bus = new EventTarget();

export const emit = (name, detail) => bus.dispatchEvent(new CustomEvent(name, { detail }));
export const on = (name, fn) => bus.addEventListener(name, (e) => fn(e.detail));
