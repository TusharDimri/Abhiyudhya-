/* "View": everything the trainer filled in on a record (attendance, a class,
   a field visit, a guest lecture), read-only, in a window over the list.
   The fields come from the module's own form, so it always matches it. */
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import api from "../lib/api";
import { useBootstrap } from "../hooks/useBootstrap";
import { toDMY } from "../lib/dates";
import { optionText } from "../lib/fieldOptions";
import { VERIFICATION_LABELS } from "../lib/roleUi";
import Badge from "./Badge";
import DistanceDot from "./DistanceDot";

const EMPTY = <span className="muted">—</span>;

// the name behind an id: a name the server sent (trainer_name ...) or a list
// the page already has (labs, job roles ...)
function nameFor(field, value, data, boot) {
  const sent = data[field.name.replace(/_id$/, "_name")];
  if (sent) return sent;
  const hit = Object.values(boot?.options || {}).flat()
    .find((o) => o && String(o.value) === String(value));
  return hit?.label ?? String(value);
}

function Students({ marks }) {
  if (!marks?.length) return EMPTY;
  const came = marks.filter((m) => m.present).length;
  // present first, then by roll number
  const rows = [...marks].sort((a, b) => (b.present - a.present)
    || String(a.roll_number || "").localeCompare(String(b.roll_number || ""), undefined, { numeric: true }));
  return (
    <div className="view-students">
      <div><b>{came} of {marks.length}</b> attended</div>
      <div className="table-wrap view-table-wrap">
        <table className="data view-table">
          <thead><tr><th>#</th><th>Roll no.</th><th>Name</th><th>Section</th><th>Attended</th></tr></thead>
          <tbody>
            {rows.map((m, i) => (
              <tr key={m.student_id || i}>
                <td className="muted">{i + 1}</td>
                <td>{m.roll_number || "—"}</td>
                <td>{m.student_name || "Student"}</td>
                <td>{m.section || "—"}</td>
                <td><span className={`view-tag ${m.present ? "ok" : ""}`}>{m.present ? "Present" : "Absent"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function valueOf(f, data, boot) {
  const v = data[f.name];
  if (f.type === "studentmarks") return <Students marks={v} />;
  if (f.type === "pdf") {
    const src = data[f.name.replace(/_url$/, "_src")];
    if (src) return <a href={src} target="_blank" rel="noreferrer">Open {f.label.toLowerCase()} (PDF)</a>;
    return v ? <span className="muted">Attached (not available here)</span> : <span className="muted">None</span>;
  }
  if (f.type === "file" || f.type === "photo") {
    const src = data[f.name.replace(/_url$/, "_src")];
    if (src) return <a href={src} target="_blank" rel="noreferrer"><img className="view-photo" src={src} alt={f.label} /></a>;
    return v ? <span className="muted">Photo attached (not available here)</span> : <span className="muted">No photo</span>;
  }
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length)) return EMPTY;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (f.type === "date" || /(^|_)date$/.test(f.name)) return toDMY(v);
  if (f.type === "time") return String(v).slice(0, 5);
  if (f.name === "class_grade") return `Class ${v}`;
  if (f.type === "multiselect") return (Array.isArray(v) ? v : String(v).split(",")).map((x) => String(x).trim()).join(", ");
  if (f.type === "select") return f.optionsKey || f.name.endsWith("_id") ? nameFor(f, v, data, boot) : optionText(String(v));
  return <span className="view-text">{String(v)}</span>;
}

// the form's fields in its own sections ("Student", "Family" ...), in order
function sectionsOf(fields) {
  const out = [];
  for (const f of fields) {
    if (f.hidden) continue;
    const name = f.group || "";
    let sec = out.find((s) => s.name === name);
    if (!sec) out.push((sec = { name, fields: [] }));
    sec.fields.push(f);
  }
  return out;
}

/* `title` / `subtitle`: instead of "<record> · <date>" and who filled it in.
   `footer(rec)`: buttons of the caller's own (e.g. Verify) beside Close.
   `children(rec)`: more below the fields (a student's history, their TC). */
export default function RecordView({ mod, resource, row, onClose, title, subtitle, footer, children }) {
  const { data: boot } = useBootstrap();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["view", resource, row.id],
    queryFn: async () => (await api.get(`/${resource}/${row.id}`)).data,
  });
  const rec = data || row;
  const when = rec.date || rec.reporting_date;
  const sections = sectionsOf(mod.fields);

  return (
    <div className="overlay center" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label={`${mod.singular} details`}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>{title || `${mod.singular}${when ? ` · ${toDMY(when)}` : ""}`}</h3>
            <span className="drawer-sub">
              {subtitle || <>
                {rec.trainer_name ? `Filled in by ${rec.trainer_name}` : "Filled in by the trainer"}
                {rec.school_name ? ` · ${rec.school_name}` : ""}
              </>}
            </span>
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          {(rec.endorsement_status || rec.verification_status || rec.distance_from_school_m !== undefined) && (
            <div className="view-status">
              {rec.verification_status && (
                <span>Verification: <Badge value={rec.verification_status} label={optionText(rec.verification_status)} /></span>
              )}
              {rec.endorsement_status && (
                <span>Verification: <Badge value={rec.endorsement_status} label={VERIFICATION_LABELS[rec.endorsement_status]} /></span>
              )}
              {rec.distance_from_school_m !== undefined && (
                <span>Distance from school: <DistanceDot metres={rec.distance_from_school_m} /></span>
              )}
            </div>
          )}
          {isError && <div className="form-error">Couldn't load the full record - showing what the list has.</div>}
          {sections.map((sec) => (
            <section key={sec.name || "-"} className="view-section">
              {sections.length > 1 && sec.name && <h4 className="view-section-title">{sec.name}</h4>}
              <dl className="view-grid">
                {sec.fields.map((f) => (
                  <div key={f.name} className={`view-item ${["textarea", "studentmarks", "file"].includes(f.type) ? "wide" : ""}`}>
                    <dt>{f.label}</dt>
                    <dd>{isLoading && ["studentmarks", "file"].includes(f.type) ? <span className="muted">Loading…</span> : valueOf(f, rec, boot)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
          {children ? children(rec) : null}
        </div>
        <footer>
          {footer ? footer(rec) : <button type="button" className="btn btn-primary" onClick={onClose}>Close</button>}
        </footer>
      </div>
    </div>
  );
}
