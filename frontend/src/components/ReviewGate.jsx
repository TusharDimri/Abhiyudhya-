/* Saved records can't be deleted (and most can't be edited), so every form asks for a second look
   before it saves: the first press ("Proceed") checks the form, jumps back to
   the top and starts a 30-second review; Submit unlocks when it runs out. */
import { useEffect, useState } from "react";

export const REVIEW_SECONDS = 30;

export function useReviewGate(seconds = REVIEW_SECONDS) {
  const [until, setUntil] = useState(null);   // null: still filling in
  const [now, setNow] = useState(() => Date.now());
  const left = until ? Math.max(0, Math.ceil((until - now) / 1000)) : seconds;

  useEffect(() => {
    if (!until || left === 0) return undefined;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [until, left]);

  return {
    reviewing: until !== null,
    left,
    ready: until !== null && left === 0,
    // begin the review and bring the top of the form into view
    start: (scroller) => {
      setNow(Date.now());
      setUntil(Date.now() + seconds * 1000);
      scroller?.scrollTo?.({ top: 0, behavior: "smooth" });
    },
    reset: () => setUntil(null),
  };
}

// the line at the top of the form while it is being reviewed
// `locked`: the record can't be changed after saving either (attendance,
// visits, lectures, equipment ...) - people's details can still be edited
export function ReviewNotice({ gate, locked = false }) {
  if (!gate.reviewing) return null;
  const rule = locked ? "Saved records can't be edited or deleted" : "Saved records can't be deleted";
  return (
    <div className={`review-note ${gate.ready ? "ready" : ""}`} role="status">
      <b>Please check every field before you submit.</b>{" "}
      {gate.ready
        ? `All checked? Press Submit to save. ${rule}.`
        : <>{rule}, so take a moment. Submit unlocks in <b>{gate.left}s</b>.</>}
    </div>
  );
}

// the button's text for each step
export function reviewLabel(gate, { busy, busyText = "Saving…", submitText = "Submit" } = {}) {
  if (busy) return busyText;
  if (!gate.reviewing) return "Proceed";
  return gate.ready ? submitText : `${submitText} (${gate.left}s)`;
}
