/* Formats de date (français) et durées relatives. */

export const DAY = 86400000;
const fr = (opts) => new Intl.DateTimeFormat("fr-FR", opts);
export const fWeekday = fr({ weekday: "long" });
export const fDayMonth = fr({ day: "numeric", month: "long" });
export const fShortMonth = fr({ month: "short" });
export const fDate = fr({ day: "numeric", month: "short" });
export const hm = (d) => `${d.getHours()}h${String(d.getMinutes()).padStart(2, "0")}`;
export const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
export const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
export const monday = (d) => addDays(startOfDay(d), -((d.getDay() + 6) % 7));
export const sameDay = (a, b) => a.toDateString() === b.toDateString();
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
export const longDay = (d) => cap(`${fWeekday.format(d)} ${fDayMonth.format(d)}`);

export function relDay(d) {
  const diff = Math.round((startOfDay(d) - startOfDay(new Date())) / DAY);
  if (diff === 0) return "aujourd'hui";
  if (diff === 1) return "demain";
  if (diff === -1) return "hier";
  if (diff > 1 && diff < 7) return fWeekday.format(d);
  return fDate.format(d);
}

export function countdown(ts) {
  const due = new Date(ts * 1000);
  const ms = due - Date.now();
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3600000);
  const m = Math.floor(abs / 60000);
  if (ms < 0) {
    if (h < 1) return `en retard de ${m} min`;
    if (h < 48) return `en retard de ${h} h`;
    return `en retard de ${Math.floor(h / 24)} jours`;
  }
  if (m < 60) return `dans ${m} min`;
  if (h < 24 && sameDay(due, new Date())) return `aujourd'hui à ${hm(due)}`;
  if (relDay(due) === "demain") return `demain à ${hm(due)}`;
  if (h < 24 * 7) return `${fWeekday.format(due)} à ${hm(due)}`;
  return `dans ${Math.round(h / 24)} jours`;
}

export function ago(ts) {
  const d = new Date(ts * 1000);
  if (sameDay(d, new Date())) return hm(d);
  if (relDay(d) === "hier") return "hier";
  return fDate.format(d);
}
