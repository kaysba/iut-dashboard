/* Lien ADE : instructions, collage, vérification par le serveur (assistant et réglages). */
import { dropStore, postJSON, refreshMe } from "../../core/api.js";
import { $, ICON } from "../../core/dom.js";
import { emit } from "../../core/events.js";

const ADE_SITE = "https://edtweb.univ-cotedazur.fr";
export function adeForm() {
  return `<div class="ade-form">
    <ol class="ade-steps">
      <li>Ouvre ADE avec le bouton ci-dessous et affiche ton emploi du temps.</li>
      <li>Clique sur l'icône <b>Exporter l'agenda</b> (un calendrier avec une flèche).</li>
      <li>Choisis une période quelconque, puis clique sur <b>Générer URL</b>.</li>
      <li>Copie l'adresse obtenue (elle contient <code>anonymous_cal.jsp</code>) et colle-la ci-dessous.</li>
    </ol>
    <a class="btn" href="${ADE_SITE}" target="_blank" rel="noopener">${ICON.ext}Ouvrir ADE</a>
    <form class="ade-input" novalidate>
      <label class="sr" for="ade-url">Lien d'export ADE</label>
      <input id="ade-url" name="url" type="url" inputmode="url" autocomplete="off" spellcheck="false"
        placeholder="https://edtweb.univ-cotedazur.fr/…/anonymous_cal.jsp?data=…">
      <button class="btn primary" type="submit">Vérifier</button>
    </form>
    <p class="check" role="status" aria-live="polite"></p>
  </div>`;
}

export const coursCount = (n) => (n === 0 ? "Le lien fonctionne, mais aucun cours n'est prévu cette semaine."
  : `${n} cours trouvé${n > 1 ? "s" : ""} cette semaine`);

export function bindAdeForm(root, onOk) {
  const form = $(".ade-input", root), input = form.url, msg = $(".check", root), btn = $("button", form);
  let busy = false;
  const check = async () => {
    const url = input.value.trim();
    if (!url) { msg.className = "check bad"; msg.textContent = "Colle d'abord le lien d'export ADE."; return; }
    if (busy) return;
    busy = true;
    btn.disabled = true;
    msg.className = "check wait";
    msg.textContent = "Vérification du lien auprès d'ADE…";
    try {
      const r = await postJSON("/api/settings/ade", { url });
      msg.className = "check ok";
      msg.textContent = coursCount(r.count);
      input.value = "";
      dropStore("/api/planning");
      await refreshMe();
      onOk(r);
    } catch (e) {
      if (e.code === "login_required") return emit("auth-required", "Ta session a expiré. Reconnecte-toi.");
      msg.className = "check bad";
      msg.textContent = e.message;
      input.select();
    } finally {
      busy = false;
      btn.disabled = false;
    }
  };
  form.addEventListener("submit", (ev) => { ev.preventDefault(); check(); });
  input.addEventListener("paste", () => setTimeout(check, 0));
}
