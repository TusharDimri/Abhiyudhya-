/* The organisation / state / district / school an admin has picked on a
   list. Each list (tab) keeps its own pick - choosing a school on Guest
   Lectures doesn't change Field Visits. Kept in memory only: a refresh (or
   logging out) starts every list afresh. */
import { useEffect, useState } from "react";

const EVENT = "rnaf-org-scope";
let picks = {};   // { listKey: { organisation_id, state_id, district_id, school_id } }

// set one list's pick from outside it (e.g. a notification that opens a school)
export function setOrgScopeFor(key, next) {
  picks = { ...picks, [key]: next };
  window.dispatchEvent(new Event(EVENT));
}

// forget every pick (at logout)
export function clearOrgScopes() {
  picks = {};
  window.dispatchEvent(new Event(EVENT));
}

// `key`: which list - its resource, plus the sub-tab where a page has several
export function useOrgScope(key = "default") {
  const [scope, setLocal] = useState(() => picks[key] || {});
  useEffect(() => {
    setLocal(picks[key] || {});
    const sync = () => setLocal(picks[key] || {});
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, [key]);
  const setScope = (next) => {
    setLocal(next);
    setOrgScopeFor(key, next);
  };
  return [scope, setScope];
}
