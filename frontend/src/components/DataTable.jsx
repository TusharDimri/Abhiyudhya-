import { useEffect, useRef } from "react";
import Badge from "./Badge";
import { Plus } from "lucide-react";
import DistanceDot, { EndorsementDot } from "./DistanceDot";
import { isISODate, toDMY } from "../lib/dates";

// a student who has left for good - only their record is shown then
const isGone = (r) => r.leaving_stage === "left" || ["Dropped Out", "Transferred Out"].includes(r.enrolment_status);
// where a leaving student is, for those who aren't the next to act
const LEAVING_NOTE = { requested: "Leaving · TC pending", tc_issued: "Leaving · TC issued" };

// Presentational, server-driven table with sortable headers + skeleton loader.
/* `select` (optional) puts a tick box on each row it allows, and one in the
   header for every such row on this page: { can(row), ids: Set, toggle(id),
   setAll(ids) } - e.g. the Principal ticking attendance to verify at once. */
export default function DataTable({ columns, rows, loading, sort, order, onSort, onEdit, onDelete, onRowAction, rowActions, canWrite, emptyHint, emptyAction, onEmptyAction, flashId, select }) {
  const showActions = canWrite || (rowActions && rowActions.length);
  const pickable = select && !loading ? rows.filter((r) => select.can(r)).map((r) => String(r.id)) : [];
  const picked = pickable.filter((id) => select.ids.has(id)).length;
  const allBox = useRef(null);
  useEffect(() => {
    if (allBox.current) allBox.current.indeterminate = picked > 0 && picked < pickable.length;
  }, [picked, pickable.length]);
  // the row a notification pointed at: brought into view, then it flashes
  const flashRow = useRef(null);
  useEffect(() => {
    if (flashId && flashRow.current) flashRow.current.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [flashId, rows]);
  const statusShown = columns.some((c) => c.key === "status_label");
  return (
    <div className="card">
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {select && (
                <th className="no-sort select-col">
                  <input ref={allBox} type="checkbox" aria-label="Select all on this page"
                    disabled={!pickable.length} checked={pickable.length > 0 && picked === pickable.length}
                    onChange={(e) => select.setAll(e.target.checked ? pickable : [])} />
                </th>
              )}
              {columns.map((c) => {
                const active = sort === c.key;
                return (
                  <th
                    key={c.key}
                    className={c.sortable === false ? "no-sort" : ""}
                    onClick={() => c.sortable !== false && onSort(c.key)}
                  >
                    {c.label}
                    {active ? (order === "asc" ? " ▲" : " ▼") : ""}
                  </th>
                );
              })}
              {showActions ? <th className="no-sort">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {select && <td className="select-col" />}
                    {columns.map((c) => (
                      <td key={c.key}><div className="skeleton" style={{ width: `${50 + ((i * 7 + c.key.length) % 40)}%` }} /></td>
                    ))}
                    {showActions ? <td><div className="skeleton" style={{ width: 70 }} /></td> : null}
                  </tr>
                ))
              : rows.map((r) => (
                  <tr key={r.id} ref={flashId && String(r.id) === String(flashId) ? flashRow : null}
                    className={[flashId && String(r.id) === String(flashId) ? "row-flash" : "",
                      select?.ids.has(String(r.id)) ? "row-picked" : ""].filter(Boolean).join(" ") || undefined}>
                    {select && (
                      <td className="select-col">
                        {select.can(r) && (
                          <input type="checkbox" aria-label="Select this record"
                            checked={select.ids.has(String(r.id))} onChange={() => select.toggle(String(r.id))} />
                        )}
                      </td>
                    )}
                    {columns.map((c) => (
                      <td key={c.key}>
                        {c.dot === "distance" ? <DistanceDot metres={r[c.key]} />
                          : c.dot === "endorsement" ? <EndorsementDot value={r[c.key]} />
                          : c.badge ? <Badge value={r[c.key]} label={c.valueLabels?.[r[c.key]]} /> : format(r[c.key])}
                      </td>
                    ))}
                    {showActions ? (
                      <td>
                        {isGone(r) && rowActions?.includes("record") ? (
                        // a student who has left: their record and history, nothing more
                        <div className="cell-actions">
                          <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("record", r)}>View</button>
                        </div>
                        ) : (
                        <div className="cell-actions">
                          {rowActions?.includes("pdf") && (r.document_src
                            ? <a className="btn btn-ghost btn-sm" href={r.document_src} target="_blank" rel="noreferrer">View PDF</a>
                            : <span className="muted">PDF not available</span>)}
                          {rowActions?.includes("view") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("view", r)}>View</button>
                          )}
                          {rowActions?.includes("endorse") && r.endorsement_status !== "endorsed" && !r.past_year && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("endorse", r)}>Verify</button>
                          )}
                          {rowActions?.includes("transition") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("transition", r)}>Update status</button>
                          )}
                          {rowActions?.includes("resolve") && r.workflow_status !== "resolved" && r.maintenance_status !== "Resolved" && (
                            <button className="btn btn-primary btn-sm" onClick={() => onRowAction("resolve", r)}>Resolve</button>
                          )}
                          {rowActions?.includes("maintenance") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("maintenance", r)}>Update status</button>
                          )}
                          {rowActions?.includes("history") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("history", r)}>History</button>
                          )}
                          {rowActions?.includes("verify") && !r.past_year && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("verify", r)}>Verify</button>
                          )}
                          {/* leaving: trainer marks -> principal records the TC -> org admin confirms */}
                          {rowActions?.includes("status") && r.enrolment_status === "Studying" && !r.leaving_stage && !r.past_year && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("status", r)}>Mark as left</button>
                          )}
                          {rowActions?.includes("tc") && r.leaving_stage === "requested" && (
                            <button className="btn btn-primary btn-sm" onClick={() => onRowAction("tc", r)}>TC Issued</button>
                          )}
                          {rowActions?.includes("leftverify") && r.leaving_stage === "tc_issued" && (
                            <button className="btn btn-primary btn-sm" onClick={() => onRowAction("leftverify", r)}>Verify TC</button>
                          )}
                          {LEAVING_NOTE[r.leaving_stage] && !statusShown && !(rowActions?.includes("tc") && r.leaving_stage === "requested")
                            && !(rowActions?.includes("leftverify") && r.leaving_stage === "tc_issued") && (
                            <span className="leaving-note">{LEAVING_NOTE[r.leaving_stage]}</span>
                          )}
                          {/* a finished academic year is closed: nothing in it changes */}
                          {r.past_year && (canWrite || rowActions?.some((a) => ["endorse", "verify", "status"].includes(a))) && (
                            <span className="closed-note" title="From a previous academic year - it can't be changed">Closed year</span>
                          )}
                          {canWrite && !r.past_year && <button className="btn btn-ghost btn-sm" onClick={() => onEdit(r)}>Edit</button>}
                          {canWrite && onDelete && <button className="btn btn-danger btn-sm" onClick={() => onDelete(r)}>Delete</button>}
                        </div>
                        )}
                      </td>
                    ) : null}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
      {!loading && rows.length === 0 && (
        <div className="empty">
          {/* say what this screen means for the person looking at it, and
              offer the next step rather than a dead end */}
          <div className="empty-text">{emptyHint || "No records found."}</div>
          {emptyAction && (
            <button type="button" className="btn btn-accent btn-sm" onClick={onEmptyAction}>
              <Plus size={15} /> {emptyAction}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function format(v) {
  if (v === null || v === undefined || v === "") return <span className="muted">—</span>;
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (isISODate(v)) return toDMY(v);
  if (typeof v === "string" && /^\d{2}:\d{2}:\d{2}$/.test(v)) return v.slice(0, 5);
  return String(v);
}
