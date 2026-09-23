import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";

// Principal endorsement + DM/OA issue transition (spec Part 5.21 / 3.12).
export default function WorkflowDialog({ resource, action, row, onClose, onDone }) {
  const { push } = useToast();
  const [remarks, setRemarks] = useState("");
  const initialDecision = action === "endorse" ? "endorsed" : action === "verify" ? "verified" : "in-progress";
  const [decision, setDecision] = useState(initialDecision);

  const run = useMutation({
    mutationFn: async () => {
      if (action === "endorse") {
        return api.post(`/workflow/attendance/${row.id}/endorse`, { decision, remarks });
      }
      if (action === "verify") {
        return api.post(`/workflow/students/${row.id}/verify`, { verification_status: decision, remarks });
      }
      return api.post(`/workflow/issues/${row.id}/transition`, {
        workflow_status: decision, resolution_note: remarks,
      });
    },
    onSuccess: () => { push("Updated", "success"); onDone(); },
    onError: (e) => push(apiError(e), "error"),
  });

  const TITLES = { endorse: "Endorse Attendance", verify: "Verify Student", transition: "Action Issue" };

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(440px,100%)" }}>
        <header>
          <h3 style={{ margin: 0 }}>{TITLES[action] || "Update"}</h3>
          <button className="close" onClick={onClose}>×</button>
        </header>
        <div className="body">
          <div className="field">
            <label>{action === "transition" ? "New status" : "Decision"}</label>
            <select className="select" value={decision} onChange={(e) => setDecision(e.target.value)}>
              {action === "endorse" &&
                [["endorsed", "Endorse"], ["returned", "Return for correction"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {action === "verify" &&
                [["verified", "Verify"], ["rejected", "Reject"], ["pending", "Mark pending"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {action === "transition" &&
                [["open", "Open"], ["in-progress", "In progress"], ["resolved", "Resolved"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Remarks / note</label>
            <textarea className="input" rows={3} value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          </div>
        </div>
        <footer>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Saving…" : "Confirm"}
          </button>
        </footer>
      </div>
    </div>
  );
}
