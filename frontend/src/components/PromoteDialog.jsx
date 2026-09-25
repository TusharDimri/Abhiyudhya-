import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { toDMY } from "../lib/dates";

/* End-of-year promotion for one class: every student is promoted unless the
   trainer switches them to "Hold back" (repeat the class next year). Class 12
   - or Class 10 in a lab without 11-12 - completes the course instead. */
export default function PromoteDialog({ onClose, onDone }) {
  const { push } = useToast();
  const opts = useQuery({
    queryKey: ["promotion", "options"],
    queryFn: async () => (await api.get("/promotion/options")).data.groups,
  });
  const groups = opts.data || [];
  const years = [...new Set(groups.map((g) => g.academic_year))].sort().reverse();

  const [year, setYear] = useState("");
  const [cls, setCls] = useState("");
  const [held, setHeld] = useState({});   // student id -> true when held back

  // start on the most recent year that has ended (the one to promote)
  useEffect(() => {
    if (year || !groups.length) return;
    const ended = groups.filter((g) => g.ended).map((g) => g.academic_year).sort().reverse();
    setYear(ended[0] || years[0]);
  }, [groups.length]); // eslint-disable-line

  const classes = groups.filter((g) => g.academic_year === year);
  useEffect(() => {
    if (classes.length && !classes.some((g) => g.class_grade === cls)) setCls(classes[0].class_grade);
  }, [year, classes.length]); // eslint-disable-line

  const preview = useQuery({
    queryKey: ["promotion", "preview", year, cls],
    queryFn: async () => (await api.get(`/promotion/preview?from_year=${encodeURIComponent(year)}&class_grade=${cls}`)).data,
    enabled: !!(year && cls),
  });
  useEffect(() => { setHeld({}); }, [year, cls]);

  const p = preview.data;
  const students = p?.students || [];
  const eligible = students.filter((s) => s.eligible);
  const upCount = eligible.filter((s) => !held[s.id]).length;
  const backCount = eligible.filter((s) => held[s.id]).length;
  const completes = eligible.length > 0 && eligible.every((s) => s.to_class == null);
  const target = useMemo(() => {
    const to = eligible.find((s) => s.to_class)?.to_class;
    return completes ? "Course completed" : to ? `Class ${to}` : "";
  }, [p]); // eslint-disable-line

  const run = useMutation({
    mutationFn: async () => (await api.post("/promotion", {
      from_year: year, class_grade: cls,
      promote: eligible.filter((s) => !held[s.id]).map((s) => s.id),
      hold_back: eligible.filter((s) => held[s.id]).map((s) => s.id),
    })).data,
    onSuccess: (r) => {
      const parts = [
        r.promoted && `${r.promoted} promoted to ${r.to_year}`,
        r.completed && `${r.completed} completed the course`,
        r.held_back && `${r.held_back} held back`,
      ].filter(Boolean);
      push(parts.join(" · ") || "Done", "success");
      onDone();
    },
    onError: (e) => push(apiError(e), "error"),
  });

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(620px,100%)" }}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>Promote Students</h3>
            <span className="drawer-sub">At the end of the year, move a class up - or hold students back to repeat it.</span>
          </div>
          <button className="close" onClick={onClose}>×</button>
        </header>
        <div className="body">
          {opts.isLoading ? <div className="skeleton" style={{ height: 80 }} /> : groups.length === 0 ? (
            <div className="empty">No students to promote.</div>
          ) : (
            <>
              <div className="fgrid">
                <div className="field">
                  <label>Academic year</label>
                  <select className="select" value={year} onChange={(e) => setYear(e.target.value)}>
                    {years.map((y) => {
                      const ended = groups.some((g) => g.academic_year === y && g.ended);
                      return <option key={y} value={y}>{y}{ended ? " (ended)" : " (in progress)"}</option>;
                    })}
                  </select>
                </div>
                <div className="field">
                  <label>Class</label>
                  <select className="select" value={cls} onChange={(e) => setCls(e.target.value)}>
                    {classes.map((g) => (
                      <option key={g.class_grade} value={g.class_grade}>Class {g.class_grade} · {g.students} student{g.students === 1 ? "" : "s"}</option>
                    ))}
                  </select>
                </div>
              </div>

              {p && (
                <div className={`promote-banner ${p.ended ? "" : "wait"}`}>
                  {p.ended ? (
                    <>Class {p.class_grade} · {p.from_year} <b>→</b> {target} {completes ? "" : `· ${p.to_year}`}</>
                  ) : (
                    <>{p.from_year} ends on {toDMY(p.ends_on)}. Students can be promoted after that.</>
                  )}
                </div>
              )}

              {preview.isLoading ? <div className="skeleton" style={{ height: 120 }} /> : (
                <ul className="roster-list promote-list">
                  {students.map((s) => (
                    <li key={s.id} className={`roster-row attend-row ${s.eligible && !held[s.id] ? "present" : ""}`}>
                      <span className="roster-name">{s.full_name}</span>
                      <span className="roster-meta">
                        {[s.roll_number, s.section && `Sec ${s.section}`].filter(Boolean).join(" · ")}
                        {s.eligible && s.to_class && s.to_job_role && !held[s.id] ? ` · ${s.to_job_role}` : ""}
                      </span>
                      {s.eligible ? (
                        <div className="seg promote-seg" role="group">
                          <button type="button" className={!held[s.id] ? "on" : ""} onClick={() => setHeld((h) => ({ ...h, [s.id]: false }))}>
                            {s.to_class ? "Promote" : "Complete"}
                          </button>
                          <button type="button" className={held[s.id] ? "on" : ""} onClick={() => setHeld((h) => ({ ...h, [s.id]: true }))}>
                            Hold back
                          </button>
                        </div>
                      ) : (
                        <span className="badge warning" style={{ marginLeft: "auto" }}>{s.reason}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <footer>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-primary"
            disabled={!p?.ended || !eligible.length || run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? "Saving…" : `${completes ? "Complete" : "Promote"} ${upCount}${backCount ? ` · Hold back ${backCount}` : ""}`}
          </button>
        </footer>
      </div>
    </div>
  );
}
