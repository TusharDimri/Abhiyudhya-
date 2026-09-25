import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import api from "./api";

/* Where the user is, as their browser reports it - one fix shared by the
   whole app. The top-bar "Detect My Location" button asks for it (the browser
   shows its own permission prompt the first time); forms that record a
   location read it when saving and take a new one if it has gone stale.

   Nothing here is shown on a form: the point is stored with the record for
   people who review it, not typed or seen by the one filling it in.

   The fix kept in session storage is sealed by the server when it is taken
   (POST /location/seal): editing it there makes the server refuse it. */

const FRESH_MS = 10 * 60 * 1000;  // a fix older than this is taken again
const STORE_KEY = "rnaf.location";

const Ctx = createContext(null);

function readStored() {
  try {
    const v = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
    return v && typeof v.lat === "number" && v.sig ? Object.freeze(v) : null;
  } catch {
    return null;
  }
}

const isFresh = (fix) => !!fix?.sig && Date.now() - fix.at < FRESH_MS;

export function locationErrorMessage(err) {
  if (err?.code === 1)
    return "Location access is blocked. Click the icon at the left of the address bar, allow Location, then try again.";
  if (err?.code === 3) return "Finding your location took too long. Try again, near a window if you're indoors.";
  if (err?.unsupported) return "This browser can't share your location.";
  return "Couldn't find your location. Check that location (GPS) is switched on, then try again.";
}

export function LocationProvider({ children }) {
  const [fix, setFix] = useState(readStored);   // {lat, lng, accuracy, at}
  const [status, setStatus] = useState("idle");  // idle | detecting | ok | denied | error
  const [error, setError] = useState("");
  const [, tick] = useState(0);
  const pending = useRef(null);

  // re-render once a minute so "fresh" turns into "stale" on its own
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 60 * 1000);
    return () => clearInterval(t);
  }, []);

  // notice a permission blocked (or unblocked) in the browser's own settings
  useEffect(() => {
    let perm;
    navigator.permissions?.query({ name: "geolocation" }).then((p) => {
      perm = p;
      const sync = () => setStatus((s) => (p.state === "denied" ? "denied" : s === "denied" ? "idle" : s));
      sync();
      p.onchange = sync;
    }).catch(() => {});
    return () => { if (perm) perm.onchange = null; };
  }, []);

  const detect = useCallback(() => {
    if (pending.current) return pending.current;
    if (!("geolocation" in navigator)) {
      setStatus("error");
      setError(locationErrorMessage({ unsupported: true }));
      return Promise.reject({ unsupported: true });
    }
    setStatus("detecting");
    setError("");
    pending.current = new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const at = pos.timestamp || Date.now();
          try {
            // the server signs it; only a fix with an intact seal is accepted
            const { data } = await api.post("/location/seal", {
              lat: pos.coords.latitude,
              lng: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
              captured_at: new Date(at).toISOString(),
            });
            const next = Object.freeze({ ...data, at });
            setFix(next);
            setStatus("ok");
            try { sessionStorage.setItem(STORE_KEY, JSON.stringify(next)); } catch { /* private mode */ }
            resolve(next);
          } catch (err) {
            setStatus("error");
            setError("Couldn't confirm your location with the server. Check your connection and try again.");
            reject(err);
          }
        },
        (err) => {
          setStatus(err.code === 1 ? "denied" : "error");
          setError(locationErrorMessage(err));
          reject(err);
        },
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
      );
    }).finally(() => { pending.current = null; });
    return pending.current;
  }, []);

  // what a form uses when saving: the current fix if fresh, else a new one
  const getFresh = useCallback(() => (isFresh(fix) ? Promise.resolve(fix) : detect()), [fix, detect]);

  const value = { fix, fresh: isFresh(fix), status, error, detect, getFresh };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useLocationFix = () => useContext(Ctx);

// what a form sends alongside its answers: the sealed fix, exactly as issued
export const locationPayload = (fix) => ({
  location_fix: {
    lat: fix.lat, lng: fix.lng, accuracy: fix.accuracy,
    captured_at: fix.captured_at, issued_at: fix.issued_at, sig: fix.sig,
  },
});
