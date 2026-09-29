import { useState, useMemo } from "react";
import Icon from "../../components/Icon";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../../lib/api";
import { useBootstrap } from "../../hooks/useBootstrap";
import { useToast } from "../../lib/toast";
import { MODULES } from "../../lib/modules";
import { isISODate, toDMY } from "../../lib/dates";

export default function Trash() {
  const { data: boot } = useBootstrap();
  const qc = useQueryClient();
  const { push } = useToast();

  // resources this user can write (and therefore restore)
  const writable = useMemo(
    () => Object.entries(boot?.resources || {}).filter(([, r]) => r.can_write).map(([k]) => k).filter((k) => MODULES[k]),
    [boot]
  );
  const [resource, setResource] = useState("");
  const active = resource || writable[0] || "";
  const mod = MODULES[active];

  const trash = useQuery({
    queryKey: ["trash", active],
    queryFn: async () => (await api.get(`/${active}/trash`)).data,
    enabled: !!active,
  });

  const restore = useMutation({
    mutationFn: async (row) => api.post(`/${active}/${row.id}/restore`),
    onSuccess: () => { push("Restored", "success"); qc.invalidateQueries({ queryKey: ["trash", active] }); },
    onError: (e) => push(apiError(e), "error"),
  });

  const rows = trash.data?.data || [];
  const cols = mod?.columns?.slice(0, 4) || [];

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Administration</div>
          <h1><span className="page-ico"><Icon name="trash" size={20} /></span>Recycle Bin</h1>
          <div className="muted" style={{ fontSize: ".85rem" }}>Soft-deleted records. Restore anything deleted by mistake.</div>
        </div>
      </div>

      <div className="toolbar">
        <label className="filterbar-label">Section</label>
        <select className="select filter-ctl" value={active} onChange={(e) => setResource(e.target.value)}>
          {writable.map((k) => <option key={k} value={k}>{MODULES[k]?.label || k}</option>)}
        </select>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}<th>Deleted</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {trash.isLoading
                ? Array.from({ length: 4 }).map((_, i) => <tr key={i}><td colSpan={cols.length + 2}><div className="skeleton" style={{ width: "60%" }} /></td></tr>)
                : rows.map((r) => (
                    <tr key={r.id}>
                      {cols.map((c) => <td key={c.key}>{fmt(r[c.key])}</td>)}
                      <td className="muted mono-sm">{toDMY(r.updated_at)}</td>
                      <td><button className="btn btn-accent btn-sm" onClick={() => restore.mutate(r)}>Restore</button></td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
        {!trash.isLoading && rows.length === 0 && <div className="empty">Recycle bin is empty for this section.</div>}
      </div>
    </div>
  );
}

function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (isISODate(v)) return toDMY(v);
  return String(v);
}
