import Badge from "./Badge";
import DistanceDot, { EndorsementDot } from "./DistanceDot";
import { isISODate, toDMY } from "../lib/dates";

// Presentational, server-driven table with sortable headers + skeleton loader.
export default function DataTable({ columns, rows, loading, sort, order, onSort, onEdit, onDelete, onRowAction, rowActions, canWrite, emptyHint, emptyAction, onEmptyAction }) {
  const showActions = canWrite || (rowActions && rowActions.length);
  return (
    <div className="card">
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
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
                    {columns.map((c) => (
                      <td key={c.key}><div className="skeleton" style={{ width: `${50 + ((i * 7 + c.key.length) % 40)}%` }} /></td>
                    ))}
                    {showActions ? <td><div className="skeleton" style={{ width: 70 }} /></td> : null}
                  </tr>
                ))
              : rows.map((r) => (
                  <tr key={r.id}>
                    {columns.map((c) => (
                      <td key={c.key}>
                        {c.dot === "distance" ? <DistanceDot metres={r[c.key]} />
                          : c.dot === "endorsement" ? <EndorsementDot value={r[c.key]} />
                          : c.badge ? <Badge value={r[c.key]} label={c.valueLabels?.[r[c.key]]} /> : format(r[c.key])}
                      </td>
                    ))}
                    {showActions ? (
                      <td>
                        <div className="cell-actions">
                          {rowActions?.includes("endorse") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("endorse", r)}>Verify</button>
                          )}
                          {rowActions?.includes("transition") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("transition", r)}>Action</button>
                          )}
                          {rowActions?.includes("history") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("history", r)}>History</button>
                          )}
                          {rowActions?.includes("verify") && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("verify", r)}>Verify</button>
                          )}
                          {rowActions?.includes("status") && r.enrolment_status !== "Completed" && (
                            <button className="btn btn-ghost btn-sm" onClick={() => onRowAction("status", r)}>
                              {r.enrolment_status === "Studying" ? "Left?" : "Rejoin"}
                            </button>
                          )}
                          {canWrite && <button className="btn btn-ghost btn-sm" onClick={() => onEdit(r)}>Edit</button>}
                          {canWrite && <button className="btn btn-danger btn-sm" onClick={() => onDelete(r)}>Delete</button>}
                        </div>
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
              ＋ {emptyAction}
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
