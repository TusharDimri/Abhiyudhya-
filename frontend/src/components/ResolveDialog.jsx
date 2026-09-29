/* An admin resolves what was raised: the org admin (or district manager) a
   trainer's or a principal's issue, or a maintenance log entry; the super
   admin an org admin's own issue. What was raised is shown (filled in,
   nothing to type); they write the resolution and set Open / Resolved.
   Resolving it tells whoever raised it. */
import { useState } from "react";
import { Check, X } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { toDMY } from "../lib/dates";

// what each list shows of the item being resolved
const KNOWN = {
  issues: (r) => [
    ["Raised by (VT)", r.trainer_name], ["School", r.school_name], ["Lab", r.lab_name],
    ["Date", toDMY(r.reporting_date)], ["Issue", r.details || [r.main_issue, r.sub_issue].filter(Boolean).join(" - ")],
  ],
  "principal-issues": (r) => [
    ["Raised by (Principal)", r.principal_name], ["School", r.school_name],
    ["Date", toDMY(r.reporting_date)], ["Issue", r.details],
  ],
  "org-issues": (r) => [
    ["Raised by (Org Admin)", r.raised_by_name], ["Organisation", r.organisation_name],
    ["Date", toDMY(r.reporting_date)], ["Issue", r.details],
  ],
  "equipment-maintenance": (r) => [
    ["Lab equipment", r.equipment_name], ["Lab", r.lab_name], ["School", r.school_name],
    ["Logged by (VT)", r.logged_by], ["Date", toDMY(r.date)], ["Problem", r.issue],
    ["Current status", r.maintenance_status],
  ],
};

export default function ResolveDialog({ resource, row, onClose, onDone }) {
  const { push } = useToast();
  const maintenance = resource === "equipment-maintenance";
  const wasResolved = maintenance ? row.maintenance_status === "Resolved" : row.workflow_status === "resolved";
  const [status, setStatus] = useState(wasResolved ? "open" : "resolved");
  const [resolution, setResolution] = useState((maintenance ? row.action : row.resolution_note) || "");
  const needsText = status === "resolved";

  const save = useMutation({
    mutationFn: async () => (maintenance
      ? api.post(`/workflow/equipment-maintenance/${row.id}/status`, {
          maintenance_status: status === "resolved" ? "Resolved" : "Open", resolution })
      : api.post(`/workflow/${resource}/${row.id}/transition`, { workflow_status: status, resolution_note: resolution })),
    onSuccess: () => {
      push(status === "resolved" ? "Resolved - whoever raised it has been told" : "Marked as open", "success");
      onDone();
    },
    onError: (e) => push(apiError(e), "error"),
  });

  const known = (KNOWN[resource] || (() => []))(row).filter(([, v]) => v);

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(520px,100%)" }}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>Resolve {maintenance ? "maintenance" : "issue"}</h3>
            <span className="drawer-sub">Write what was done, and set the status.</span>
          </div>
          <button type="button" className="close" onClick={onClose}><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <div className="known-panel">
            <div className="known-title"><Check size={14} /> {maintenance ? "What was logged" : "What was raised"}</div>
            <div className="known-grid">
              {known.map(([k, v]) => (
                <div className={`known-item ${["Issue", "Problem"].includes(k) ? "wide" : ""}`} key={k}>
                  <span className="known-k">{k}</span>
                  <span className="known-v known-wrap">{v}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Resolution {needsText && <span className="req">*</span>}</label>
            <textarea className="input" rows={4} value={resolution} onChange={(e) => setResolution(e.target.value)}
              placeholder={maintenance ? "e.g. Power supply replaced by the vendor" : "e.g. Roof repaired by the PWD on 20/09"} />
          </div>
          <div className="field">
            <label>Status <span className="req">*</span></label>
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
            </select>
            {status === "resolved" && (
              <span className="hint">
                {maintenance ? "The trainer who logged it will be told." : "Whoever raised it will be told."}
              </span>
            )}
          </div>
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={save.isPending || (needsText && !resolution.trim())}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save"}
          </button>
        </footer>
      </div>
    </div>
  );
}
