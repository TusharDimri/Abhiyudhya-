/* Saved records can't be deleted (and most can't be edited), so every form asks for a second look
   before it saves: the first press ("Proceed") checks the form and jumps back to
   the top; Submit is pressed next. On a trainer's daily records the review
   lasts 30 seconds - Submit unlocks when it runs out; elsewhere at once. */
import { useEffect, useState } from "react";

export const REVIEW_SECONDS = 30;

// The forms whose review lasts 30 seconds - a trainer's daily records. On
// every other form, Submit is ready as soon as Proceed is pressed.
const TIMED_FORMS = {
  VT: ["attendance", "class-attendance", "assessments", "field-visits", "guest-lectures", "ojt-placements"],
};
export const needsReview = (role, form) => !!TIMED_FORMS[role]?.includes(form);

// `timed`: false - no wait; Submit is ready as soon as Proceed is pressed
export function useReviewGate(timed = true) {
  const seconds = timed ? REVIEW_SECONDS : 0;
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
