/* The state / district / school an org admin has picked on a list. Each
   list (tab) keeps its own pick - choosing a school on Guest Lectures doesn't
   change Field Visits - remembered for the session and forgotten at logout. */
import { useEffect, useState } from "react";

const KEY = "rnaf.orgScope";
const EVENT = "rnaf-org-scope";

function readAll() {
  try {
    const all = JSON.parse(sessionStorage.getItem(KEY) || "{}");
    return all && typeof all === "object" ? all : {};
  } catch {
    return {};
  }
}

// set one list's pick from outside it (e.g. a notification that opens a school)
export function setOrgScopeFor(key, next) {
  const all = readAll();
  all[key] = next;
  try { sessionStorage.setItem(KEY, JSON.stringify(all)); } catch { /* kept in this page only */ }
  window.dispatchEvent(new Event(EVENT));
}

// `key`: which list - its resource, plus the sub-tab where a page has several
export function useOrgScope(key = "default") {
  const [scope, setLocal] = useState(() => readAll()[key] || {});
  useEffect(() => {
    setLocal(readAll()[key] || {});
    const sync = () => setLocal(readAll()[key] || {});
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, [key]);
  const setScope = (next) => {
    setLocal(next);
    setOrgScopeFor(key, next);
  };
  return [scope, setScope];
}
