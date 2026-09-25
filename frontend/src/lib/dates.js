/* Dates are stored and sent as ISO (YYYY-MM-DD) and always shown as
   DD/MM/YYYY, whatever language the browser is set to. */

const ISO = /^(\d{4})-(\d{2})-(\d{2})/;

// "2026-09-25" or "2026-09-25T10:30:00" -> "25/09/2026"; anything else as-is
export function toDMY(value) {
  const m = ISO.exec(String(value ?? ""));
  return m ? `${m[3]}/${m[2]}/${m[1]}` : value;
}

// "25/09/2026" -> "2026-09-25"; null unless it is a real calendar date
export function fromDMY(text) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(String(text ?? "").trim());
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
  return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

// is this string an ISO date or timestamp (as the API sends them)?
export const isISODate = (v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}(T|$)/.test(v);

// the user's local date as ISO (toISOString alone is UTC - still yesterday
// in India until 5:30 AM)
export function todayISO() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

export function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}
