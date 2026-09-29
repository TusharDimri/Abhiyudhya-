/* Class 11 takes this lab's earlier Class 10 students too - ones who finished
   Class 10, left during it, or were never moved up. Pick them here: they join
   the chosen Class 11 section with new roll numbers and are verified again
   (students are verified at Class 9 and again at Class 11). */
import { useState } from "react";
import { X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { useReviewGate, ReviewNotice, reviewLabel } from "./ReviewGate";

const STATUS_TEXT = { Completed: "Finished Class 10", "Dropped Out": "Left in Class 10", Studying: "Not moved up" };

export default function PreviousStudents({ lab, section, onClose }) {
  const qc = useQueryClient();
  const { push } = useToast();
  const review = useReviewGate();
  const [picked, setPicked] = useState(() => new Set());
  const list = useQuery({
    queryKey: ["previous-students", lab.value],
    queryFn: async () => (await api.get(`/students/previous?lab_id=${lab.value}`)).data.data,
  });
  const add = useMutation({
    mutationFn: async () => (await api.post("/students/previous", {
      lab_id: lab.value, section, student_ids: [...picked],
    })).data,
    onSuccess: (r) => {
      push(`${r.added} student${r.added === 1 ? "" : "s"} joined Class 11 ${r.section} - waiting for verification`, "success");
      for (const k of [["previous-students"], ["list", "students"], ["roster"], ["promotion"], ["dashboard"]]) qc.invalidateQueries({ queryKey: k });
      onClose();
    },
    onError: (e) => push(apiError(e), "error"),
  });

  const students = list.data || [];
  const all = students.length > 0 && picked.size === students.length;
  const toggle = (id) => setPicked((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <div className="overlay center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal modal-wide" role="dialog" aria-label="Add previous students to Class 11">
        <header>
          <div>
            <h3 style={{ margin: 0 }}>Add previous students · Class 11 {section}</h3>
            <span className="drawer-sub">This lab's earlier Class 10 students. They'll be verified again, as at Class 9.</span>
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <ReviewNotice gate={review} />
          {list.isLoading && <div className="skeleton" style={{ height: 120, borderRadius: 10 }} />}
          {list.isSuccess && students.length === 0 && (
            <div className="prefill-note">No earlier Class 10 students are waiting to join Class 11.</div>
          )}
          {students.length > 0 && (
            <div className="table-wrap view-table-wrap">
              <table className="data view-table">
                <thead>
                  <tr>
                    <th><input type="checkbox" checked={all} aria-label="Pick all"
                      onChange={() => setPicked(all ? new Set() : new Set(students.map((s) => s.id)))} /></th>
                    <th>Name</th><th>Adm. no.</th><th>Class 10</th><th>Year</th><th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.id} onClick={() => toggle(s.id)} style={{ cursor: "pointer" }}>
                      <td><input type="checkbox" checked={picked.has(s.id)} onChange={() => toggle(s.id)} onClick={(e) => e.stopPropagation()} /></td>
                      <td>{s.full_name}</td>
                      <td>{s.admission_number || "—"}</td>
                      <td>{s.section ? `Section ${s.section}` : "—"}{s.roll_number ? ` · ${s.roll_number}` : ""}</td>
                      <td>{s.academic_year || "—"}</td>
                      <td>{STATUS_TEXT[s.enrolment_status] || s.enrolment_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary"
            disabled={!picked.size || add.isPending || (review.reviewing && !review.ready)}
            onClick={() => (review.reviewing ? add.mutate() : review.start(document.querySelector(".modal .body")))}>
            {reviewLabel(review, { busy: add.isPending, submitText: `Add ${picked.size || ""} to Class 11 ${section}` })}
          </button>
        </footer>
      </div>
    </div>
  );
}
