import { Fragment, useMemo, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { useBootstrap } from "../hooks/useBootstrap";
import { labById, optionText } from "../lib/fieldOptions";
import { todayISO } from "../lib/dates";
import DateInput from "./DateInput";
import { useReviewGate, ReviewNotice, reviewLabel } from "./ReviewGate";
import SectionManager from "./SectionManager";
import PreviousStudents from "./PreviousStudents";

/* Adding students, as easy as it can be: pick the class and section once,
   then one row per student - as many as you like, saved together. Blank rows
   are ignored; pasting a column of names from a spreadsheet fills the rows. */

const blank = () => ({
  admission_number: "", first_name: "", last_name: "", gender: "", dob: "", father_name: "",
  mobile_primary: "", social_category_id: "", aadhaar_number: "", cwsn: false,
});
const isBlank = (r) => !Object.entries(r).some(([k, v]) => k !== "cwsn" && String(v || "").trim()) && !r.cwsn;
const START_ROWS = 3;

export default function AddStudents() {
  const qc = useQueryClient();
  const { push } = useToast();
  const { data: boot } = useBootstrap();
  const labs = boot?.options?.labs || [];
  const [labId, setLabId] = useState("");
  const lab = labById(boot, labId || labs[0]?.value);

  // Classes 9-12 - just the ones this lab (and this trainer's slot) runs.
  const classes = useMemo(() => {
    if (!lab) return [];
    const mine = Object.values(boot?.my_scope?.class_grades_by_job_role || {}).flat();
    const list = [];
    if (lab.job_role_9_10_id) list.push("9", "10");
    if (lab.job_role_11_12_id) list.push("11", "12");
    return mine.length ? list.filter((c) => mine.includes(c)) : list;
  }, [lab, boot]);
  const [cls, setCls] = useState("");
  const classGrade = classes.includes(cls) ? cls : classes[0] || "";
  const sections = (lab?.sections?.[classGrade]?.length ? lab.sections[classGrade] : ["A", "B", "C", "D"]);
  const [sec, setSec] = useState("");
  const section = sections.includes(sec) ? sec : sections[0] || "";

  // a trainer can add a section to the chosen class - or remove an empty one
  const [newSection, setNewSection] = useState(null);   // null: closed; string: typing
  const [managing, setManaging] = useState(null);       // the section whose students are shown
  const [previous, setPrevious] = useState(false);      // picking earlier Class 10 students for Class 11
  const changeSections = useMutation({
    mutationFn: async ({ path, name }) => (await api.post(`/students/sections${path}`, {
      lab_id: lab.value, class_grade: classGrade, section: name,
    })).data,
    onSuccess: (r, { path, name }) => {
      qc.invalidateQueries({ queryKey: ["bootstrap"] });   // the lab's section lists live there
      if (path === "") { setSec(name.toUpperCase()); setNewSection(null); push(`Section ${name.toUpperCase()} added to Class ${classGrade}`, "success"); }
      else { setSec(""); push(`Section ${name} removed from Class ${classGrade}`, "success"); }
    },
    onError: (e) => push(apiError(e), "error"),
  });
  const pickSection = (v) => {
    if (v === "__remove") { setManaging(section); return; }
    if (v !== "__add") { setSec(v); return; }
    if (!classGrade) { push("Select a class first, then add its section.", "error"); return; }
    setNewSection("");
  };
  const roleId = lab && classGrade ? (["9", "10"].includes(classGrade) ? lab.job_role_9_10_id : lab.job_role_11_12_id) : null;
  const jobRole = (boot?.options?.job_roles || []).find((j) => String(j.value) === String(roleId))?.label;

  const already = useQuery({
    queryKey: ["list", "students", "count", lab?.value, classGrade, section],
    queryFn: async () => (await api.get(`/students?page_size=1&lab_id=${lab.value}&class_grade=${classGrade}&section=${section}&enrolment_status=Studying`)).data.pagination.total,
    enabled: !!(lab && classGrade && section),
  });

  const [rows, setRows] = useState(() => Array.from({ length: START_ROWS }, blank));
  const [errors, setErrors] = useState({});   // row index -> message
  const [done, setDone] = useState(null);
  const review = useReviewGate();
  const topRef = useRef(null);
  const put = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const filled = rows.map((r, i) => [r, i]).filter(([r]) => !isBlank(r));

  // paste a spreadsheet column (or first/last/gender columns) into "First name"
  const pasteNames = (i, e) => {
    const text = e.clipboardData.getData("text");
    if (!/[\r\n\t]/.test(text)) return;
    e.preventDefault();
    const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    const genders = (boot?.enums?.genders || []).map((g) => g.value);
    setRows((rs) => {
      const next = [...rs];
      lines.forEach((line, k) => {
        const cells = line.includes("\t") ? line.split("\t").map((c) => c.trim()) : null;
        let first, last, gender;
        if (cells) [first, last, gender] = cells;
        else { const parts = line.split(/\s+/); first = parts[0]; last = parts.slice(1).join(" "); }
        const g = genders.find((x) => x.toLowerCase() === String(gender || "").toLowerCase());
        const at = i + k;
        while (next.length <= at) next.push(blank());
        next[at] = { ...next[at], first_name: first || "", last_name: last || next[at].last_name, gender: g || next[at].gender };
      });
      return next;
    });
  };

  const save = useMutation({
    mutationFn: async () => (await api.post("/students/bulk", {
      lab_id: lab.value, class_grade: classGrade, section,
      students: filled.map(([r]) => ({ ...r, social_category_id: r.social_category_id || null })),
    })).data,
    onSuccess: (r) => {
      setDone(r);
      setErrors({});
      review.reset();
      setRows(Array.from({ length: START_ROWS }, blank));
      push(`Added ${r.added} student${r.added === 1 ? "" : "s"} to Class ${r.class_grade} ${r.section}`, "success");
      for (const key of [["list", "students"], ["roster"], ["promotion"], ["dashboard"]]) qc.invalidateQueries({ queryKey: key });
    },
    onError: (e) => {
      const list = e?.response?.data?.errors;
      if (Array.isArray(list)) {
        // the server numbers the rows it was sent; map back to the grid
        const map = {};
        for (const { row, message } of list) map[filled[row - 1]?.[1]] = message;
        setErrors(map);
      }
      push(apiError(e), "error");
    },
  });

  if (!labs.length) return <div className="card card-pad">You aren't assigned to a lab yet - ask your admin.</div>;

  return (
    <section className="card add-students" ref={topRef}>
      <div className="add-students-head">
        {labs.length > 1 && (
          <label className="field compact">
            <span>Lab</span>
            <select className="select" value={lab?.value || ""} onChange={(e) => setLabId(e.target.value)}>
              {labs.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </label>
        )}
        <label className="field compact">
          <span>Class <b className="req">*</b></span>
          <select className="select" value={classGrade} onChange={(e) => { setCls(e.target.value); setSec(""); }}>
            {classes.map((c) => <option key={c} value={c}>Class {c}</option>)}
          </select>
        </label>
        <div className="field compact">
          <span>Section <b className="req">*</b></span>
          <select className="select" value={section} onChange={(e) => pickSection(e.target.value)}>
            {sections.map((s) => <option key={s} value={s}>Section {s}</option>)}
            <option value="__add">+ Add a section…</option>
            {section && sections.length > 1 && <option value="__remove">－ Remove Section {section}…</option>}
          </select>
          {newSection !== null ? (
            <div className="section-add">
              <input className="input" autoFocus maxLength={3} placeholder="e.g. C" value={newSection}
                onChange={(e) => setNewSection(e.target.value.toUpperCase())}
                onKeyDown={(e) => { if (e.key === "Enter" && newSection.trim()) changeSections.mutate({ path: "", name: newSection.trim() }); if (e.key === "Escape") setNewSection(null); }} />
              <button type="button" className="btn btn-primary btn-sm" disabled={!newSection.trim() || changeSections.isPending}
                onClick={() => changeSections.mutate({ path: "", name: newSection.trim() })}>Add to Class {classGrade}</button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNewSection(null)}>Cancel</button>
            </div>
          ) : null}
        </div>
        <div className="field compact">
          <span>Job role</span>
          <div className="input derived-value">{jobRole || "—"}</div>
        </div>
        <div className="add-students-count muted">
          {already.data != null && <>Class {classGrade} {section} has <b>{already.data}</b> student{already.data === 1 ? "" : "s"} now</>}
        </div>
      </div>
      <ReviewNotice gate={review} />
      {classGrade === "11" && section && (
        <div className="prefill-note previous-note">
          <span>Class 11 can also take this lab's earlier Class 10 students. They're verified again, as at Class 9.</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPrevious(true)}><Plus size={15} /> Add previous students</button>
        </div>
      )}
      <p className="muted add-students-hint">
        One row per student. Every student needs the fields marked *; roll numbers are given automatically.
        Tip: paste a column of names from Excel into a “First name” box.
      </p>

      <div className="table-wrap">
        <table className="data add-grid">
          <thead>
            <tr>
              <th>#</th><th>Adm. No. *</th><th>First name *</th><th>Last name</th><th>Gender *</th>
              <th>Date of birth *</th><th>Father's name *</th><th>Contact No. *</th><th>Category *</th>
              <th>Aadhaar No. *</th><th>CWSN</th><th>Roll no.</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <Fragment key={i}>
              <tr className={errors[i] ? "has-error" : ""}>
                <td className="muted">{i + 1}</td>
                <td><input className="input" value={r.admission_number} onChange={(e) => put(i, "admission_number", e.target.value)} /></td>
                <td><input className="input" value={r.first_name} onChange={(e) => put(i, "first_name", e.target.value)} onPaste={(e) => pasteNames(i, e)} /></td>
                <td><input className="input" value={r.last_name} onChange={(e) => put(i, "last_name", e.target.value)} /></td>
                <td>
                  <select className="select" value={r.gender} onChange={(e) => put(i, "gender", e.target.value)}>
                    <option value="">—</option>
                    {(boot?.enums?.genders || []).map((g) => <option key={g.value} value={g.value}>{optionText(g.label)}</option>)}
                  </select>
                </td>
                <td><DateInput value={r.dob} max={todayISO()} onChange={(v) => put(i, "dob", v)} /></td>
                <td><input className="input" value={r.father_name} onChange={(e) => put(i, "father_name", e.target.value)} /></td>
                <td><input className="input" inputMode="numeric" placeholder="10 digits" value={r.mobile_primary} onChange={(e) => put(i, "mobile_primary", e.target.value)} /></td>
                <td>
                  <select className="select" value={r.social_category_id} onChange={(e) => put(i, "social_category_id", e.target.value)}>
                    <option value="">—</option>
                    {(boot?.options?.social_categories || []).map((c) => <option key={c.value} value={c.value}>{optionText(c.label)}</option>)}
                  </select>
                </td>
                <td><input className="input" inputMode="numeric" placeholder="12 digits" maxLength={14} value={r.aadhaar_number} onChange={(e) => put(i, "aadhaar_number", e.target.value)} /></td>
                <td className="center"><input type="checkbox" checked={r.cwsn} onChange={(e) => put(i, "cwsn", e.target.checked)} /></td>
                <td><input className="input" value="Auto" disabled title="Given automatically when the students are saved" /></td>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" title="Remove this row"
                    onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : [blank()]))}><X size={15} /></button>
                </td>
              </tr>
              {errors[i] && <tr className="row-error"><td colSpan={13}>Row {i + 1}: {errors[i]}</td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="profile-actions">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRows((rs) => [...rs, blank()])}><Plus size={15} /> Add row</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRows((rs) => [...rs, ...Array.from({ length: 5 }, blank)])}><Plus size={15} /> Add 5 rows</button>
        <span className="grow" />
        <button type="button" className="btn btn-primary"
          disabled={!filled.length || save.isPending || !classGrade || (review.reviewing && !review.ready)}
          onClick={() => {
            if (!review.reviewing) { review.start(); topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); return; }
            save.mutate();
          }}>
          {reviewLabel(review, { busy: save.isPending, submitText: `Add ${filled.length || ""} student${filled.length === 1 ? "" : "s"} to Class ${classGrade} ${section}` })}
        </button>
      </div>

      {done && (
        <div className="prefill-note" style={{ marginTop: ".8rem" }}>
          Added {done.added} to Class {done.class_grade} {done.section} ({done.academic_year}):{" "}
          {done.students.map((s) => `${s.full_name} (${s.roll_number})`).join(", ")}. They're waiting for your admin to verify them.
        </div>
      )}
      {previous && <PreviousStudents lab={lab} section={section} onClose={() => setPrevious(false)} />}
      {managing && (
        <SectionManager lab={lab} classGrade={classGrade} section={managing} sections={sections}
          onClose={() => setManaging(null)}
          onRemoved={() => { setManaging(null); setSec(""); }} />
      )}
    </section>
  );
}
