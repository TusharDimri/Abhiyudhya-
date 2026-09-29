import { useQuery } from "@tanstack/react-query";
import { FileText, X } from "lucide-react";
import api, { apiError } from "../lib/api";
import { toDMY } from "../lib/dates";

const LEAVING = { requested: "Leaving - waiting for the TC", tc_issued: "Leaving - TC issued, waiting for the org admin" };

// what one history entry says happened
function outcomeText(y) {
  switch (y.outcome) {
    case "Completed": return "Completed the course";
    case "Held Back": return `Held back in Class ${y.class_grade}`;
    case "Joined Class 11": return `Joined Class 11 for ${y.to_academic_year}`;
    case "TC issued": {
      const tc = y.snapshot || {};
      return `Transfer Certificate${tc.tc_number ? ` ${tc.tc_number}` : ""}${tc.tc_issued_on ? ` (dated ${toDMY(tc.tc_issued_on)})` : ""} recorded by the principal`;
    }
    case "Dropped Out": case "Transferred Out": return `Left the school (${y.outcome.toLowerCase()}) - TC verified by the org admin`;
    case "Marked as leaving": return `Marked as leaving by the trainer${y.snapshot?.left_reason ? `: ${y.snapshot.left_reason}` : ""}`;
    default: return `Moved to Class ${y.to_class} for ${y.to_academic_year}`;
  }
}

// a final leaving step shows as "Left" in its badge
const badgeText = (outcome) => (["Dropped Out", "Transferred Out"].includes(outcome) ? "Left" : outcome);

const badgeFor = (outcome) => (
  ["Held Back", "Marked as leaving", "TC issued"].includes(outcome) ? "warning"
    : ["Dropped Out", "Transferred Out"].includes(outcome) ? "danger" : "success");

/* A student's story: where they are now, then every step before - each year
   that ended (kept exactly as it was) and each step of leaving the school. */
export function HistoryList({ studentId }) {
  const q = useQuery({
    queryKey: ["promotion", "history", studentId],
    queryFn: async () => (await api.get(`/promotion/history/${studentId}`)).data,
  });
  const d = q.data;
  const place = (y) => [y.class_grade && `Class ${y.class_grade}`, y.section && `Section ${y.section}`].filter(Boolean).join(" · ");

  if (q.isLoading) return <div className="skeleton" style={{ height: 120 }} />;
  if (q.isError) return <div className="form-error">{apiError(q.error)}</div>;
  if (!d) return null;
  const now = d.current;
  return (
    <ol className="history">
      <li className="history-item now">
        <div className="history-year">{now.academic_year || "—"} <span className="badge info">Now</span></div>
        <div>{place(now)}{now.roll_number ? ` · Roll ${now.roll_number}` : ""}</div>
        <div className="muted">{[now.job_role, now.lab].filter(Boolean).join(" · ")}</div>
        <div className="muted">
          Status: {LEAVING[now.leaving_stage]
            || (["Dropped Out", "Transferred Out"].includes(now.enrolment_status) ? `Left (${now.enrolment_status.toLowerCase()})` : now.enrolment_status)}
          {" · "}{now.verification_status}
          {now.left_on ? ` · left on ${toDMY(now.left_on)}` : ""}
        </div>
        {now.left_reason && now.leaving_stage && <div className="muted">Reason: {now.left_reason}</div>}
        {(now.tc_number || now.tc_issued_on || now.has_tc_photo) && (
          <div className="history-tc">
            <div className="history-tc-title"><FileText size={14} /> Transfer Certificate</div>
            <div>
              {now.tc_number ? `TC ${now.tc_number}` : "TC"}
              {now.tc_issued_on ? ` · dated ${toDMY(now.tc_issued_on)}` : ""}
            </div>
            <div className="muted">
              {now.tc_verified_on ? `Verified by the org admin on ${toDMY(now.tc_verified_on)}` : "Waiting for the org admin to verify it"}
            </div>
            {now.tc_src ? <a href={now.tc_src} target="_blank" rel="noreferrer">View the TC photo</a>
              : <span className="muted">{now.has_tc_photo ? "Photo attached" : "No photo"}</span>}
          </div>
        )}
      </li>
      {d.years.map((y, i) => (
        <li key={i} className="history-item">
          <div className="history-year">
            {y.academic_year}{" "}
            <span className={`badge ${badgeFor(y.outcome)}`}>{badgeText(y.outcome)}</span>
          </div>
          <div>{place(y)}{y.roll_number ? ` · Roll ${y.roll_number}` : ""}</div>
          <div className="muted">{[y.job_role, y.lab].filter(Boolean).join(" · ")}</div>
          <div className="muted">
            {outcomeText(y)}
            {y.recorded_on ? ` · on ${toDMY(y.recorded_on)}` : ""}{y.recorded_by ? ` by ${y.recorded_by}` : ""}
          </div>
        </li>
      ))}
      {d.years.length === 0 && <li className="muted history-empty">No earlier steps yet - promotions and leaving appear here.</li>}
    </ol>
  );
}

/* The History button's side panel. */
export default function StudentHistory({ row, onClose }) {
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(560px,100%)" }}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>{row.full_name || "Student"}</h3>
            <span className="drawer-sub">Year-by-year record - earlier years are kept as they were</span>
          </div>
          <button className="close" onClick={onClose}><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <HistoryList studentId={row.id} />
        </div>
      </div>
    </div>
  );
}
