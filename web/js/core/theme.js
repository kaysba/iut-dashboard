/* Thème : système (par défaut), clair ou sombre. Enregistré dans les réglages ;
   localStorage n'en garde qu'une copie pour peindre la page sans flash au chargement. */
import { $ } from "./dom.js";
import { state } from "./state.js";
import { saveSettings, toast } from "./api.js";

const THEME_LABEL = { system: "Thème : système", light: "Thème : clair", dark: "Thème : sombre" };
const themeQuery = matchMedia("(prefers-color-scheme: dark)");

export function themeMode() {
  try { const t = localStorage.getItem("theme"); if (t === "light" || t === "dark") return t; } catch { /* stockage indisponible */ }
  return "system";
}

function applyTheme(mode) {
  try { if (mode === "system") localStorage.removeItem("theme"); else localStorage.setItem("theme", mode); } catch { /* stockage indisponible */ }
  document.documentElement.dataset.theme = mode === "system" ? (themeQuery.matches ? "dark" : "light") : mode;
  $("#theme-label").textContent = THEME_LABEL[mode];
}

export function setTheme(mode) {
  applyTheme(mode);
  if ((state.me || {}).loggedIn) saveSettings({ THEME: mode }, null).catch((e) => toast(e.message));
}

export function syncTheme() {
  const t = (state.me || {}).theme;
  if (t && t !== themeMode()) applyTheme(t);
}

export function initTheme() {
  themeQuery.addEventListener("change", () => { if (themeMode() === "system") applyTheme("system"); });
  applyTheme(themeMode());
  $("#theme").addEventListener("click", () => setTheme({ system: "light", light: "dark", dark: "system" }[themeMode()]));
}
