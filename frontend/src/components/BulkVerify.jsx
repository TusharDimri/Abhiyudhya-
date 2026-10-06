/* The Principal verifying several attendance records at once: the bar under
   the list ("3 selected · Verify All") and the window that confirms it. */
import { useState } from "react";
import { CheckCheck, X } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";

export default function BulkVerify({ resource, ids, onClear, onDone }) {
  const { push } = useToast();
  const [confirming, setConfirming] = useState(false);
  const count = ids.size;
  const what = resource === "class-attendance" ? "class attendance" : "attendance";

  const save = useMutation({
    mutationFn: async () => (await api.post(`/workflow/${resource}/endorse-bulk`, { ids: [...ids] })).data,
    onSuccess: ({ verified, skipped }) => {
      push(`${verified} ${verified === 1 ? "record" : "records"} verified`
        + (skipped ? ` - ${skipped} skipped (already verified or can't be changed)` : ""), "success");
      setConfirming(false);
      onDone();
    },
    onError: (e) => push(apiError(e), "error"),
  });

  return (
    <>
      <div className="bulk-bar">
        <span className="bulk-count">
          {count ? `${count} selected` : `Tick the ${what} to verify, or the box at the top for all on this page`}
        </span>
        {count > 0 && <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>Clear</button>}
        <div className="grow" />
        <button type="button" className="btn btn-primary" disabled={!count} onClick={() => setConfirming(true)}>
          <CheckCheck size={16} /> Verify All{count ? ` (${count})` : ""}
        </button>
      </div>

      {confirming && (
        <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && !save.isPending && setConfirming(false)}>
          <div className="drawer" style={{ width: "min(460px,100%)" }}>
            <header>
              <h3 style={{ margin: 0 }}>Verify {count} {count === 1 ? "record" : "records"}?</h3>
              <button type="button" className="close" onClick={() => setConfirming(false)} disabled={save.isPending}>
                <X size={18} strokeWidth={2} />
              </button>
            </header>
            <div className="body">
              <p style={{ margin: 0 }}>
                The selected {what} will be marked as verified. Once verified, the trainer can't change them,
                and each trainer is told.
              </p>
            </div>
            <footer>
              <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)} disabled={save.isPending}>Cancel</button>
              <button type="button" className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? "Verifying…" : "Verify"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
