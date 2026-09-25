import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";

const STATUSES = [
  { key: "", label: "All" },
  { key: "not_met", label: "Not met" },
  { key: "met", label: "Met" },
];

/* How far each level is towards its yearly target (15 guest lectures / 2
   field visits per level per academic year). Clicking a level narrows the
   table below to exactly the records that count towards it. */
export default function TargetProgress({ resource, onPick, picked }) {
  const [year, setYear] = useState("");
  const [status, setStatus] = useState("");

  const params = new URLSearchParams();
  if (year) params.set("academic_year", year);
  if (status) params.set("status", status);
  const q = useQuery({
    queryKey: ["targets", resource, params.toString()],
    queryFn: async () => (await api.get(`/targets/${resource}?${params}`)).data,
  });

  const data = q.data;
  if (q.isLoading) return <div className="card targets"><div className="skeleton" style={{ height: 90 }} /></div>;
  if (!data) return null;

  const rows = data.rows || [];
  const manyLabs = new Set(rows.map((r) => r.lab_id)).size > 1;
  const showYear = data.academic_year === "all";
  const metCount = rows.filter((r) => r.met).length;
  const isPicked = (r) =>
    picked && picked.academic_year === r.academic_year &&
    String(picked.class_grade) === String(r.class_grade) && (!picked.lab_id || picked.lab_id === r.lab_id);

  return (
    <section className="card targets">
      <div className="targets-head">
        <div>
          <h3>Yearly target</h3>
          <span className="muted">{data.target} {data.noun} per level, every academic year</span>
        </div>
        <div className="targets-controls">
          <select className="select filter-ctl" value={year || data.academic_year} onChange={(e) => setYear(e.target.value)} aria-label="Academic year">
            {data.years.map((y) => (
              <option key={y} value={y}>{y}{y === data.current_year ? " (this year)" : ""}</option>
            ))}
            <option value="all">All years</option>
          </select>
          <div className="seg" role="group" aria-label="Show">
            {STATUSES.map((s) => (
              <button key={s.key} type="button" className={status === s.key ? "on" : ""} onClick={() => setStatus(s.key)}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="empty" style={{ padding: "1rem 0" }}>
          {status === "met" ? "No level has met its target yet." : status === "not_met" ? "Every level has met its target. 🎉" : "No levels to show."}
        </div>
      ) : (
        <>
          {!status && (
            <div className="targets-summary">
              <b>{metCount}</b> of <b>{rows.length}</b> level{rows.length === 1 ? "" : "s"} met the target
            </div>
          )}
          <div className="targets-grid">
            {rows.map((r) => {
              const pct = Math.min(100, Math.round((r.count / r.target) * 100));
              return (
                <button
                  key={`${r.academic_year}-${r.lab_id}-${r.class_grade}`}
                  type="button"
                  className={`target-tile ${r.met ? "met" : ""} ${isPicked(r) ? "picked" : ""}`}
                  onClick={() => onPick(r)}
                  title={`Show the ${data.noun} that count towards this level`}
                >
                  <div className="target-top">
                    <span className="target-level">Level {r.level} · Class {r.class_grade}</span>
                    <span className={`badge ${r.met ? "success" : "warning"}`}>{r.met ? "Target met" : `${r.remaining} to go`}</span>
                  </div>
                  {(manyLabs || showYear) && (
                    <div className="target-where muted">
                      {[showYear && r.academic_year, manyLabs && r.lab_name].filter(Boolean).join(" · ")}
                    </div>
                  )}
                  <div className="target-count"><b>{r.count}</b> <span className="muted">of {r.target}</span></div>
                  <div className="target-bar" aria-hidden="true"><span style={{ width: `${pct}%` }} /></div>
                </button>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
