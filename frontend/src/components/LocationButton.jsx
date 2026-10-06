import { useLocationFix, locationErrorMessage } from "../lib/location";
import { useToast } from "../lib/toast";

// "3 min ago" for the tooltip
const ago = (at) => {
  const mins = Math.round((Date.now() - at) / 60000);
  return mins < 1 ? "just now" : `${mins} min ago`;
};

/* Top-bar button: pulses softly until the browser has shared a fresh
   location, then settles. Clicking always takes a new reading. */
export default function LocationButton() {
  const loc = useLocationFix();
  const { push } = useToast();
  if (!loc) return null;
  const { fix, fresh, status, error, detect } = loc;

  let label = "Detect My Location";
  let title = "Share your location - it is saved with the records you add.";
  let state = "need";
  if (status === "detecting") {
    label = "Detecting…";
    state = "busy";
  } else if (status === "denied") {
    label = "Location Blocked";
    title = error || "Allow location for this site from the icon at the left of the address bar, then click here.";
  } else if (fresh) {
    label = "Location On";
    state = "ok";
    title = `Detected ${ago(fix.at)}, accurate to about ${Math.round(fix.accuracy)} m. Click to detect again.`;
  } else if (status === "error") {
    title = error;
  }

  return (
    <button
      type="button"
      className={`loc-btn loc-${state}`}
      // a phone has no hover for the tooltip - say what went wrong out loud
      onClick={() => detect().catch((err) => push(err?.response ? "Couldn't confirm your location with the server. Check your connection and try again."
        : locationErrorMessage(err), "error"))}
      disabled={state === "busy"}
      title={title}
      aria-label={label}
      aria-live="polite"
    >
      <span className="loc-dot" aria-hidden="true" />
      <span className="loc-label">{label}</span>
    </button>
  );
}
