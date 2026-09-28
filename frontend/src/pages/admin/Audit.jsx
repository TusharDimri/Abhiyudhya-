import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import api from "../../lib/api";

/* Who did what, and when - each entry in plain words: "Org Admin changed
   student Aarav Nair", then what changed (Enrolment: Studying → Transferred
   Out). */
const ACTION_BADGE = { create: "success", update: "info", delete: "danger", restore: "gold" };
const ACTIONS = [["create", "Added"], ["update", "Changed"], ["delete", "Deleted"], ["restore", "Restored"]];
const ROLE_NAMES = { SA: "Super Admin", OA: "Org Admin", DM: "District Manager", PR: "Principal", VT: "Trainer" };

function when(iso) {
  if (!iso) return ["—", ""];
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return [d.toLocaleDateString("en-GB"), d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })];
}

function Changes({ list }) {
  const [all, setAll] = useState(false);
  if (!list?.length) return <span className="muted">—</span>;
  const shown = all ? list : list.slice(0, 3);
  return (
    <ul className="audit-changes">
      {shown.map((c, i) => (
        <li key={i}>
          <b>{c.field}:</b>{" "}
          {c.from != null ? <><span className="audit-old">{c.from}</span> <span aria-hidden="true">→</span> </> : null}
          <span className="audit-new">{c.to}</span>
        </li>
      ))}
      {list.length > 3 && (
        <li><button type="button" className="link-btn plain" onClick={() => setAll((a) => !a)}>
          {all ? "Show less" : `Show ${list.length - 3} more`}
        </button></li>
      )}
    </ul>
  );
}

export default function Audit() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");

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
          <div className="muted" style={{ fontSize: ".85rem" }}>Who added or changed what, and when.</div>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-ico">🔍</span>
          <input className="input search" placeholder="Search by person's email or record type…" value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>
        <select className="select filter-ctl" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">What happened: All</option>
          {ACTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>When</th><th>Who</th><th>What happened</th><th>What changed</th></tr>
            </thead>
            <tbody>
              {q.isLoading
                ? Array.from({ length: 8 }).map((_, i) => <tr key={i}><td colSpan={4}><div className="skeleton" style={{ width: "70%" }} /></td></tr>)
                : rows.map((r) => {
                    const [day, time] = when(r.created_at);
                    return (
                      <tr key={r.id}>
                        <td>
                          <div>{day}</div>
                          <div className="muted" style={{ fontSize: ".75rem" }}>{time}</div>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{r.actor_name || "—"}</div>
                          <div className="muted" style={{ fontSize: ".75rem" }}>{ROLE_NAMES[r.actor_role] || r.actor_role}</div>
                        </td>
                        <td>
                          <span className={`badge ${ACTION_BADGE[r.action] || ""}`}>{r.verb}</span>{" "}
                          <span>{r.what}</span>
                          {r.record && <div className="audit-record">{r.record}</div>}
                        </td>
                        <td><Changes list={r.changes} /></td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>
        {!q.isLoading && rows.length === 0 && <div className="empty">Nothing recorded yet.</div>}
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
