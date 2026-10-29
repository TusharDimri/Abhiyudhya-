/* The principal records a leaving student's Transfer Certificate: the
   student is already chosen; attach a photo of the TC (and its number and
   date). The org admin then checks it and confirms the student has left. */
import { useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { uploadFile } from "../lib/upload";
import { todayISO, toDMY } from "../lib/dates";
import DateInput from "./DateInput";
import { useReviewGate, ReviewNotice, reviewLabel } from "./ReviewGate";

export default function TcIssueDialog({ row, onClose, onDone }) {
  const { push } = useToast();
  // the review has no 30-second wait here (ReviewGate.jsx: TIMED_FORMS)
  const review = useReviewGate(false);
  const drawer = useRef(null);
  const [tcUrl, setTcUrl] = useState("");
  const [preview, setPreview] = useState("");
  const [uploading, setUploading] = useState(false);
  const [number, setNumber] = useState("");
  const [when, setWhen] = useState(todayISO());

  const pick = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      setTcUrl(await uploadFile(file));
      setPreview(URL.createObjectURL(file));
    } catch (e) {
      push(e.message || "Upload failed", "error");
    } finally {
      setUploading(false);
    }
  };

  const save = useMutation({
    mutationFn: async () => (await api.post(`/promotion/students/${row.id}/tc`, {
      tc_url: tcUrl, tc_number: number, tc_date: when,
    })).data,
    onSuccess: () => { push(`TC recorded for ${row.full_name} - the org admin will confirm`, "success"); onDone(); },
    onError: (e) => push(apiError(e), "error"),
  });

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(520px,100%)" }} ref={drawer}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>TC Issued</h3>
            <span className="drawer-sub">Record the Transfer Certificate this student was given.</span>
          </div>
          <button type="button" className="close" onClick={onClose}><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <ReviewNotice gate={review} locked />
          <div className="known-panel">
            <div className="known-title"><Check size={14} /> Student</div>
            <div className="known-grid">
              <div className="known-item"><span className="known-k">Name</span><span className="known-v">{row.full_name}</span></div>
              <div className="known-item"><span className="known-k">Class</span><span className="known-v">{row.class_grade} {row.section || ""}</span></div>
              <div className="known-item"><span className="known-k">Leaving as</span><span className="known-v">{row.leaving_type || "—"}</span></div>
              <div className="known-item"><span className="known-k">Marked on</span><span className="known-v">{toDMY(row.leave_requested_on) || "—"}</span></div>
            </div>
            {row.left_reason && <div className="muted" style={{ marginTop: ".4rem" }}>Reason: {row.left_reason}</div>}
          </div>
          <div className="field">
            <label>Photo of the TC <span className="req">*</span></label>
            <input type="file" accept="image/*" onChange={(e) => pick(e.target.files?.[0])} disabled={uploading} />
            {uploading && <span className="hint">Uploading…</span>}
            {preview && <img src={preview} alt="TC" className="view-photo" style={{ marginTop: ".5rem" }} />}
          </div>
          <div className="fgrid">
            <div className="field">
              <label>TC number</label>
              <input className="input" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="e.g. TC/2026/112" />
            </div>
            <div className="field">
              <label>TC date <span className="req">*</span></label>
              <DateInput value={when} onChange={setWhen} max={todayISO()} />
            </div>
          </div>
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary"
            disabled={!tcUrl || !when || uploading || save.isPending || (review.reviewing && !review.ready)}
            onClick={() => (review.reviewing ? save.mutate() : review.start(drawer.current))}>
            {reviewLabel(review, { busy: save.isPending, submitText: "Record TC" })}
          </button>
        </footer>
      </div>
    </div>
  );
}
