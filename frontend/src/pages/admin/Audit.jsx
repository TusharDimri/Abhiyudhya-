import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import api from "../../lib/api";

const ACTION_BADGE = { create: "success", update: "info", delete: "danger", restore: "gold" };

export default function Audit() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [expanded, setExpanded] = useState(null);

  const q = useQuery({
    queryKey: ["audit", page, search, action],
    queryFn: async () => {
      const p = new URLSearchParams({ page });
      if (search) p.set("search", search);
      if (action) p.set("action", action);
      return (await api.get(`/admin/audit-logs?${p}`)).data;
    },
    placeholderData: keepPreviousData,
  });

  const rows = q.data?.data || [];
  const pg = q.data?.pagination || { page: 1, pages: 1, total: 0 };

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Administration</div>
          <h1>📜 Audit Log</h1>
          <div className="muted" style={{ fontSize: ".85rem" }}>Every create, update, delete and restore — who, when, and what changed.</div>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-ico">🔍</span>
          <input className="input search" placeholder="Search by entity or user…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>
        <select className="select filter-ctl" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">All actions</option>
          {["create", "update", "delete", "restore"].map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Changes</th></tr>
            </thead>
            <tbody>
              {q.isLoading
                ? Array.from({ length: 8 }).map((_, i) => <tr key={i}><td colSpan={5}><div className="skeleton" style={{ width: "70%" }} /></td></tr>)
                : rows.map((r) => (
                    <tr key={r.id}>
                      <td className="muted mono-sm">{r.created_at?.slice(0, 19).replace("T", " ")}</td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{r.actor_email || "—"}</div>
                        <div className="muted" style={{ fontSize: ".72rem" }}>{r.actor_role}</div>
                      </td>
                      <td><span className={`badge ${ACTION_BADGE[r.action] || ""}`}>{r.action}</span></td>
                      <td className="mono-sm">{r.entity}</td>
                      <td>
                        <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(expanded === r.id ? null : r.id)}>
                          {expanded === r.id ? "Hide" : "View"}
                        </button>
                        {expanded === r.id && (
                          <div className="audit-diff">
                            {r.before && <div><b>before:</b> {JSON.stringify(r.before, null, 1)}</div>}
                            {r.after && <div><b>after:</b> {JSON.stringify(r.after, null, 1)}</div>}
                            {r.ip && <div style={{ marginTop: 4 }}><b>ip:</b> {r.ip}</div>}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
        {!q.isLoading && rows.length === 0 && <div className="empty">No audit entries.</div>}
      </div>

      <div className="pager">
        <span className="info">{pg.total} entries</span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page <= 1} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
        <span className="page-num">Page {pg.page} / {pg.pages || 1}</span>
        <button className="btn btn-ghost btn-sm" disabled={pg.page >= (pg.pages || 1)} onClick={() => setPage((p) => p + 1)}>Next ›</button>
      </div>
    </div>
  );
}
