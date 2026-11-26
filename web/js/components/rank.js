/* Pastille de rang, réutilisée partout : podium or / argent / bronze (avec icône), puis bleu. */
import { ICON } from "../core/dom.js";

const ordinal = (n) => (n === 1 ? "1er" : `${n}e`);

export function rankPill(rang, total) {
  if (rang == null || !total) return "";
  const tier = rang <= 3 ? `r${rang}` : "rn";
  const icon = rang === 1 ? ICON.trophy : rang <= 3 ? ICON.medal : "";
  return `<span class="rank ${tier}" title="Rang ${rang} sur ${total}" aria-label="Rang : ${ordinal(rang)} sur ${total}">${icon}${ordinal(rang)} / ${total}</span>`;
}
