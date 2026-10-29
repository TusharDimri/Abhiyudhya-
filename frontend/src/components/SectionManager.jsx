/* Removing a section: the section's students are listed first, so each one
   can be moved to another section of the class or marked as left (a student
   is never deleted - they stay on record as having left). Once it is empty,
   the section can go. */
import { useState } from "react";
import { X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { todayISO } from "../lib/dates";

const LEAVING = ["Dropped Out", "Transferred Out"];

function StudentRow({ s, n, others, busy, onMove, onLeave }) {
  const [leaving, setLeaving] = useState(false);
  const [status, setStatus] = useState(LEAVING[0]);
  const [reason, setReason] = useState("");
  return (
    <tr>
      <td className="muted">{n}</td>
      <td>{s.roll_number || "—"}</td>
      <td>{s.full_name}</td>
      <td>{s.admission_number || "—"}</td>
      <td>
        {s.leaving_stage ? (
          <span className="leaving-note">{s.leaving_stage === "requested" ? "Leaving · TC pending" : "Leaving · TC issued"}</span>
        ) : !leaving ? (
          <div className="section-student-actions">
            {others.length > 0 && (
              <select className="select select-sm" value="" disabled={busy} onChange={(e) => e.target.value && onMove(s, e.target.value)}
                aria-label={`Move ${s.full_name} to another section`}>
                <option value="">Move to section…</option>
                {others.map((o) => <option key={o} value={o}>Section {o}</option>)}
              </select>
            )}
            <button type="button" className="btn btn-danger btn-sm" disabled={busy} onClick={() => setLeaving(true)}>
              Mark as left
            </button>
          </div>
        ) : (
          <div className="section-leave">
            <select className="select select-sm" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Why">
              {LEAVING.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <input className="input input-sm" placeholder="Reason, e.g. Family moved" value={reason}
              onChange={(e) => setReason(e.target.value)} autoFocus />
            <button type="button" className="btn btn-danger btn-sm" disabled={busy || !reason.trim()}
              onClick={() => onLeave(s, status, reason.trim())}>Mark as left</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLeaving(false)}>Cancel</button>
          </div>
        )}
      </td>
    </tr>
  );
}

export default function SectionManager({ lab, classGrade, section, sections, onClose, onRemoved }) {
  const qc = useQueryClient();
  const { push } = useToast();
  const others = sections.filter((x) => x !== section);
  const key = ["section-students", lab.value, classGrade, section];
  const list = useQuery({
    queryKey: key,
    queryFn: async () => (await api.get(
      `/students?page_size=200&lab_id=${lab.value}&class_grade=${classGrade}&section=${section}&enrolment_status=Studying&sort=roll_number&order=asc`,
    )).data.data,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: key });
    for (const k of [["list", "students"], ["roster"], ["promotion"], ["dashboard"]]) qc.invalidateQueries({ queryKey: k });
  };

  const move = useMutation({
    mutationFn: async ({ s, to }) => (await api.post(`/students/${s.id}/section`, { section: to })).data,
    onSuccess: (r) => { push(`${r.full_name} moved to Section ${r.section} (roll ${r.roll_number})`, "success"); refresh(); },
    onError: (e) => push(apiError(e), "error"),
  });
  const leave = useMutation({
    mutationFn: async ({ s, status, reason }) => api.post(`/promotion/students/${s.id}/status`,
      { enrolment_status: status, reason, date: todayISO() }),
    onSuccess: (_, { s }) => { push(`${s.full_name} marked as leaving - the principal will issue the TC`, "success"); refresh(); },
    onError: (e) => push(apiError(e), "error"),
  });
  const remove = useMutation({
    mutationFn: async () => (await api.post("/students/sections/remove", {
      lab_id: lab.value, class_grade: classGrade, section,
    })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bootstrap"] });   // the lab's section lists live there
      push(`Section ${section} removed from Class ${classGrade}`, "success");
      onRemoved();
    },
    onError: (e) => push(apiError(e), "error"),
  });

  const students = list.data || [];
  const busy = move.isPending || leave.isPending || remove.isPending;
  const empty = list.isSuccess && students.length === 0;

  return (
    <div className="overlay center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal modal-wide" role="dialog" aria-label={`Class ${classGrade} Section ${section}`}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>Class {classGrade} · Section {section}</h3>
            <span className="drawer-sub">
              {list.isLoading ? "Loading students…" : `${students.length} student${students.length === 1 ? "" : "s"} in this section`}
            </span>
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          {!empty && (
            <p className="muted" style={{ marginTop: 0 }}>
              To remove Section {section}, first move each student to another section, or mark them as left
              (the principal then records their TC and the org admin confirms). Students are never deleted.
            </p>
          )}
          {empty && <div className="prefill-note">Section {section} is empty and can be removed.</div>}
          {list.isLoading && Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 34, marginBottom: 8, borderRadius: 8 }} />
          ))}
          {students.length > 0 && (
            <div className="table-wrap view-table-wrap">
              <table className="data view-table">
                <thead><tr><th>#</th><th>Roll no.</th><th>Name</th><th>Adm. no.</th><th>Action</th></tr></thead>
                <tbody>
                  {students.map((s, i) => (
                    <StudentRow key={s.id} s={s} n={i + 1} others={others} busy={busy}
                      onMove={(st, to) => move.mutate({ s: st, to })}
                      onLeave={(st, status, reason) => leave.mutate({ s: st, status, reason })} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Close</button>
          <button type="button" className="btn btn-danger" disabled={!empty || busy} onClick={() => remove.mutate()}
            title={empty ? "" : "Move every student or mark them as left first"}>
            {remove.isPending ? "Removing…" : `Remove Section ${section}`}
          </button>
        </footer>
      </div>
    </div>
  );
}
