/* The state / district / school an org admin has picked. Their lists open on
   nothing until they choose (District, then School); the choice carries
   across tabs and pages for the session and is forgotten at logout. */
import { useEffect, useState } from "react";

const KEY = "rnaf.orgScope";
const EVENT = "rnaf-org-scope";

function read() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) || "{}") || {};
  } catch {
    return {};
  }
}

export function useOrgScope() {
  const [scope, setLocal] = useState(read);
  useEffect(() => {
    const sync = () => setLocal(read());
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  const setScope = (next) => {
    try { sessionStorage.setItem(KEY, JSON.stringify(next)); } catch { /* kept in this page only */ }
    setLocal(next);
    window.dispatchEvent(new Event(EVENT));
  };
  return [scope, setScope];
}
