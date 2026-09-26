import { useQuery } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { toDMY } from "../lib/dates";

/* A student's years: where they are now, then every year that ended - kept
   exactly as it was when they were promoted, held back or completed. */
export default function StudentHistory({ row, onClose }) {
  const q = useQuery({
    queryKey: ["promotion", "history", row.id],
    queryFn: async () => (await api.get(`/promotion/history/${row.id}`)).data,
  });
  const d = q.data;
  const place = (y) => [y.class_grade && `Class ${y.class_grade}`, y.section && `Section ${y.section}`].filter(Boolean).join(" · ");

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(560px,100%)" }}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>{row.full_name || "Student"}</h3>
            <span className="drawer-sub">Year-by-year record - earlier years are kept as they were</span>
          </div>
          <button className="close" onClick={onClose}>×</button>
        </header>
        <div className="body">
          {q.isLoading && <div className="skeleton" style={{ height: 120 }} />}
          {q.isError && <div className="form-error">{apiError(q.error)}</div>}
          {d && (
            <ol className="history">
              <li className="history-item now">
                <div className="history-year">{d.current.academic_year || "—"} <span className="badge info">Now</span></div>
                <div>{place(d.current)}{d.current.roll_number ? ` · Roll ${d.current.roll_number}` : ""}</div>
                <div className="muted">{[d.current.job_role, d.current.lab].filter(Boolean).join(" · ")}</div>
                <div className="muted">Status: {d.current.enrolment_status} · {d.current.verification_status}</div>
              </li>
              {d.years.map((y, i) => (
                <li key={i} className="history-item">
                  <div className="history-year">
                    {y.academic_year}{" "}
                    <span className={`badge ${y.outcome === "Held Back" ? "warning" : "success"}`}>{y.outcome}</span>
                  </div>
                  <div>{place(y)}{y.roll_number ? ` · Roll ${y.roll_number}` : ""}</div>
                  <div className="muted">{[y.job_role, y.lab].filter(Boolean).join(" · ")}</div>
                  <div className="muted">
                    {y.outcome === "Completed" ? "Completed the course" : `Moved to Class ${y.to_class} for ${y.to_academic_year}`}
                    {y.recorded_on ? ` · on ${toDMY(y.recorded_on)}` : ""}{y.recorded_by ? ` by ${y.recorded_by}` : ""}
                  </div>
                </li>
              ))}
              {d.years.length === 0 && <li className="muted history-empty">No earlier years yet - they appear here after promotion.</li>}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
