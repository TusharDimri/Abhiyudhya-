import { useLocationFix } from "../lib/location";

// "3 min ago" for the tooltip
const ago = (at) => {
  const mins = Math.round((Date.now() - at) / 60000);
  return mins < 1 ? "just now" : `${mins} min ago`;
};

/* Top-bar button: pulses softly until the browser has shared a fresh
   location, then settles. Clicking always takes a new reading. */
export default function LocationButton() {
  const loc = useLocationFix();
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
      onClick={() => detect().catch(() => {})}
      disabled={state === "busy"}
      title={title}
      aria-live="polite"
    >
      <span className="loc-dot" aria-hidden="true" />
      <span className="loc-label">{label}</span>
    </button>
  );
}
