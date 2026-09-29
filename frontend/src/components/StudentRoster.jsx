import { useEffect, useMemo } from "react";
import { Check, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { splitList } from "../lib/fieldOptions";

/* Marks the class inside the entry that records it.

   The roster is whoever is registered against the lab + class + section(s)
   already chosen higher up the form, so the trainer never picks students by
   hand. Two ways of marking:
     default          a day's class: everyone starts present - marking the two
                      who didn't come is a two-tap job
     mode: "attend"   a visit or lecture: everyone starts not attended, with an
                      Attend button at the end of each name */
export default function StudentRoster({ field, values, value, onChange }) {
  const attendMode = field.mode === "attend";
  const startsPresent = !attendMode;
  const classGrade = values[field.classField || "class_taught"];
  const sections = splitList(values[field.sectionField || "section_taught"]);
  const labId = values.lab_id;
  const schoolId = values.school_id;

  const params = useMemo(() => {
    const p = new URLSearchParams({ page_size: "200", sort: "roll_number", order: "asc", enrolment_status: "Studying" });
    if (labId) p.set("lab_id", labId);
    else if (schoolId) p.set("school_id", schoolId);
    if (classGrade) p.set("class_grade", classGrade);
    if (sections.length) p.set("section", sections.join(","));
    return p.toString();
  }, [labId, schoolId, classGrade, sections.join(",")]); // eslint-disable-line

  const ready = !!(classGrade && (labId || schoolId));
  const roster = useQuery({
    queryKey: ["roster", params],
    queryFn: async () => (await api.get(`/students?${params}`)).data.data,
    enabled: ready,
    staleTime: 30000,
  });

  const students = roster.data || [];
  const marks = Array.isArray(value) ? value : [];
  const presentById = useMemo(() => {
    const m = {};
    for (const r of marks) m[String(r.student_id)] = r.present !== false;
    return m;
  }, [marks]);
  const isPresent = (id) => presentById[String(id)] ?? startsPresent;

  // A student who joins the class after the entry was first opened starts
  // like everyone else did.
  useEffect(() => {
    if (!students.length) return;
    const missing = students.filter((s) => presentById[String(s.id)] === undefined);
    if (!missing.length) return;
    onChange([
      ...marks.filter((r) => students.some((s) => String(s.id) === String(r.student_id))),
      ...missing.map((s) => ({ student_id: String(s.id), present: startsPresent })),
    ]);
  }, [students]); // eslint-disable-line

  const setAll = (present) =>
    onChange(students.map((s) => ({ student_id: String(s.id), present })));

  const toggle = (id) =>
    onChange(
      students.map((s) => ({
        student_id: String(s.id),
        present: String(s.id) === String(id) ? !isPresent(s.id) : isPresent(s.id),
      }))
    );

  if (!ready) {
    return (
      <div className="roster roster-empty">
        Pick the class{field.sectionField === null ? "" : " and section"} above and the
        student list will load here.
      </div>
    );
  }
  if (roster.isLoading) return <div className="roster roster-empty">Loading students…</div>;
  if (!students.length) {
    return (
      <div className="roster roster-empty">
        No students registered for Class {classGrade}
        {sections.length ? ` · Section ${sections.join(", ")}` : ""} in this lab yet.
      </div>
    );
  }

  const presentCount = students.filter((s) => isPresent(s.id)).length;

  if (attendMode) {
    return (
      <div className="roster">
        <div className="roster-head">
          <span className="roster-count">
            <b>{presentCount}</b> attended <span className="muted">of {students.length}</span>
          </span>
          <div className="roster-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll(true)}>Mark all attended</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll(false)}>Clear</button>
          </div>
        </div>
        <ul className="roster-list">
          {students.map((s) => {
            const attended = isPresent(s.id);
            return (
              <li key={s.id} className={`roster-row attend-row ${attended ? "present" : ""}`}>
                <span className="roster-name">{s.full_name}</span>
                <span className="roster-meta">
                  {[s.roll_number, s.section && `Sec ${s.section}`].filter(Boolean).join(" · ")}
                </span>
                <button
                  type="button"
                  className={`attend-btn ${attended ? "on" : ""}`}
                  aria-pressed={attended}
                  onClick={() => toggle(s.id)}
                  title={attended ? "Click to undo" : "Mark as attended"}
                >
                  {attended ? <><Check size={14} /> Attended</> : "Attend"}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }

  return (
    <div className="roster">
      <div className="roster-head">
        <span className="roster-count">
          <b>{presentCount}</b> present · <b>{students.length - presentCount}</b> absent
          <span className="muted"> of {students.length}</span>
        </span>
        <div className="roster-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll(true)}>All present</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAll(false)}>All absent</button>
        </div>
      </div>
      <ul className="roster-list">
        {students.map((s) => {
          const present = isPresent(s.id);
          return (
            <li key={s.id}>
              <button
                type="button"
                className={`roster-row ${present ? "present" : "absent"}`}
                onClick={() => toggle(s.id)}
              >
                <span className="roster-mark">{present ? <Check size={13} strokeWidth={3} /> : <X size={13} strokeWidth={3} />}</span>
                <span className="roster-name">{s.full_name}</span>
                <span className="roster-meta">
                  {[s.roll_number, s.section && `Sec ${s.section}`].filter(Boolean).join(" · ")}
                </span>
                <span className={`roster-state ${present ? "present" : "absent"}`}>
                  {present ? "Present" : "Absent"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
