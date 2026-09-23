import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../lib/api";
import { splitList } from "../lib/fieldOptions";

/* Marks the class present/absent inside the entry that records the class.

   The roster is whoever is registered against the lab + class + section(s)
   already chosen higher up the form, so the trainer never picks students by
   hand. Everyone starts present - marking the two who didn't come is a
   two-tap job, where marking the thirty who did is not. */
export default function StudentRoster({ field, values, value, onChange }) {
  const classGrade = values[field.classField || "class_taught"];
  const sections = splitList(values[field.sectionField || "section_taught"]);
  const labId = values.lab_id;
  const schoolId = values.school_id;

  const params = useMemo(() => {
    const p = new URLSearchParams({ page_size: "200", sort: "roll_number", order: "asc" });
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

  // A student who joins the class after the entry was first opened defaults to
  // present, like everyone else.
  useEffect(() => {
    if (!students.length) return;
    const missing = students.filter((s) => presentById[String(s.id)] === undefined);
    if (!missing.length) return;
    onChange([
      ...marks.filter((r) => students.some((s) => String(s.id) === String(r.student_id))),
      ...missing.map((s) => ({ student_id: String(s.id), present: true })),
    ]);
  }, [students]); // eslint-disable-line

  const setAll = (present) =>
    onChange(students.map((s) => ({ student_id: String(s.id), present })));

  const toggle = (id) =>
    onChange(
      students.map((s) => ({
        student_id: String(s.id),
        present: String(s.id) === String(id)
          ? !(presentById[String(s.id)] ?? true)
          : presentById[String(s.id)] ?? true,
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

  const presentCount = students.filter((s) => presentById[String(s.id)] ?? true).length;

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
          const present = presentById[String(s.id)] ?? true;
          return (
            <li key={s.id}>
              <button
                type="button"
                className={`roster-row ${present ? "present" : "absent"}`}
                onClick={() => toggle(s.id)}
              >
                <span className="roster-mark">{present ? "✓" : "✕"}</span>
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
