import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import DateInput from "./DateInput";
import { todayISO } from "../lib/dates";

// Principal endorsement + DM/OA issue transition (spec Part 5.21 / 3.12).
export default function WorkflowDialog({ resource, action, row, onClose, onDone }) {
  const { push } = useToast();
  const [remarks, setRemarks] = useState("");
  const leaving = action === "status" && row.enrolment_status === "Studying";
  const initialDecision = action === "endorse" ? "endorsed" : action === "verify" ? "verified"
    : action === "status" ? (leaving ? "Dropped Out" : "Studying") : "in-progress";
  const [decision, setDecision] = useState(initialDecision);
  const [when, setWhen] = useState(todayISO());

  const run = useMutation({
    mutationFn: async () => {
      if (action === "endorse") {
        // daily or class attendance - each has its own endorsement route
        const kind = resource === "class-attendance" ? "class-attendance" : "attendance";
        return api.post(`/workflow/${kind}/${row.id}/endorse`, { decision, remarks });
      }
      if (action === "verify") {
        return api.post(`/workflow/students/${row.id}/verify`, { verification_status: decision, remarks });
      }
      if (action === "status") {
        return api.post(`/promotion/students/${row.id}/status`, { enrolment_status: decision, date: when, reason: remarks });
      }
      return api.post(`/workflow/issues/${row.id}/transition`, {
        workflow_status: decision, resolution_note: remarks,
      });
    },
    onSuccess: () => { push("Updated", "success"); onDone(); },
    onError: (e) => push(apiError(e), "error"),
  });

  const TITLES = {
    endorse: resource === "class-attendance" ? "Verify Class Attendance" : "Verify Attendance",
    verify: "Verify Student", transition: "Action Issue",
    status: leaving ? `${row.full_name || "Student"} left the school` : `${row.full_name || "Student"} rejoined`,
  };

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
                [["endorsed", "Verify"], ["returned", "Return for correction"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {action === "verify" &&
                [["verified", "Verify"], ["rejected", "Reject"], ["pending", "Mark pending"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {action === "transition" &&
                [["open", "Open"], ["in-progress", "In progress"], ["resolved", "Resolved"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              {action === "status" && (leaving
                ? [["Dropped Out", "Dropped out"], ["Transferred Out", "Transferred to another school"]]
                : [["Studying", `Rejoined (was ${String(row.enrolment_status || "").toLowerCase()})`]]
              ).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          {leaving && (
            <div className="field">
              <label>Date</label>
              <DateInput value={when} max={todayISO()} onChange={setWhen} />
            </div>
          )}
          <div className="field">
            <label>{leaving ? "Reason" : "Remarks / note"}{leaving && <span className="req"> *</span>}</label>
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
