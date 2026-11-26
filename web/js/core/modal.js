/* Modale commune (mail, dépôt, confirmations) : Échap, clic sur le fond, piège du focus, retour du focus.
   Une seule modale à la fois. onEscape / onBackdrop reçoivent close() et décident (le dépôt refuse
   de se fermer pendant un envoi, et Échap revient en arrière depuis l'écran rouge). */
import { esc } from "./dom.js";

let current = null;

export const modalOpen = () => current !== null;
export const closeModal = () => { if (current) current.close(); };

export function openModal({ id = "", className = "", labelledBy = "", html = "", onEscape, onBackdrop, onClose, opener = document.activeElement } = {}) {
  const back = document.createElement("div");
  back.className = "modal-back";
  if (id) back.id = id;
  back.innerHTML = `<div class="modal${className ? ` ${className}` : ""}" role="dialog" aria-modal="true" aria-labelledby="${esc(labelledBy)}">${html}</div>`;
  document.body.appendChild(back);
  document.body.classList.add("modal-open");
  const box = back.firstElementChild;
  const focusables = () => [...box.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), [tabindex="0"]')].filter((e) => e.offsetParent !== null);

  const close = () => {
    if (!back.isConnected) return;
    back.remove();
    document.body.classList.remove("modal-open");
    document.removeEventListener("keydown", onKey, true);
    if (current && current.back === back) current = null;
    if (opener && opener.focus) opener.focus();
    if (onClose) onClose();
  };
  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation();
      if (onEscape) onEscape(close); else close();
    } else if (e.key === "Tab") {
      const f = focusables();
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      else if (!box.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    }
  };
  document.addEventListener("keydown", onKey, true);
  back.addEventListener("mousedown", (e) => {
    if (e.target !== back) return;
    if (onBackdrop) onBackdrop(close); else close();
  });
  current = { back, box, close };
  return current;
}

// Remplace confirm() : résout true si l'action est confirmée, false sinon (Annuler, Échap, clic sur le fond).
export function confirmModal({ title, text, ok, cancel = "Annuler" }) {
  return new Promise((resolve) => {
    let answer = false;
    const m = openModal({
      className: "confirm",
      labelledBy: "confirm-title",
      html: `<header class="modal-head"><div><h2 id="confirm-title">${esc(title)}</h2></div></header>
        <div class="modal-body">${esc(text)}</div>
        <footer class="modal-foot"><button class="btn" type="button" data-act="cancel">${esc(cancel)}</button>
          <button class="btn danger" type="button" data-act="ok">${esc(ok)}</button></footer>`,
      onClose: () => resolve(answer),
    });
    m.box.addEventListener("click", (e) => {
      const b = e.target.closest("[data-act]");
      if (!b) return;
      answer = b.dataset.act === "ok";
      m.close();
    });
    m.box.querySelector("[data-act=cancel]").focus();
  });
}
