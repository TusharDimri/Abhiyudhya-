/* District managers - below the org admin, each looking after one or more
   districts. The org admin adds them here (a login is made, and its username
   and password shown once); the super admin reads the list for the
   organisation they pick. Passwords and access: Users & Access. */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useBootstrap } from "../hooks/useBootstrap";
import { useToast } from "../lib/toast";
import { useOrgScope } from "../lib/orgScope";
import { toDMY } from "../lib/dates";
import Icon from "./Icon";
import Badge from "./Badge";
import ScopePicker, { ScopeEmpty } from "./ScopePicker";
import LoginCreated from "./LoginCreated";
import { useReviewGate, ReviewNotice, reviewLabel } from "./ReviewGate";

function NewDistrictManager({ districts, onClose, onDone }) {
  const { push } = useToast();
  const review = useReviewGate();
  const box = useRef(null);
  const [f, setF] = useState({ full_name: "", email: "", phone: "", district_ids: [] });
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const toggle = (id) => set("district_ids", f.district_ids.includes(id) ? f.district_ids.filter((d) => d !== id) : [...f.district_ids, id]);
  const filled = f.full_name.trim() && f.email.trim() && /^[6-9]\d{9}$/.test(f.phone.trim()) && f.district_ids.length;

  const save = useMutation({
    mutationFn: async () => (await api.post("/users/district-managers", f)).data,
    onSuccess: (r) => { push("District manager added", "success"); onDone(r.login); },
    onError: (e) => push(apiError(e), "error"),
  });

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(680px,100%)" }} ref={box} role="dialog" aria-label="New District Manager">
        <header>
          <div>
            <h3 style={{ margin: 0 }}>New District Manager</h3>
            <span className="drawer-sub">Their login is made when you save - you'll see the username and password.</span>
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <ReviewNotice gate={review} />
          <div className="fgrid">
            <div className="field"><label>Full name <span className="req">*</span></label>
              <input className="input" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} />
            </div>
            <div className="field"><label>Email <span className="req">*</span></label>
              <input className="input" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} />
              <span className="hint">Their username for logging in.</span>
            </div>
            <div className="field"><label>Mobile <span className="req">*</span></label>
              <input className="input" type="tel" placeholder="10 digits" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>District(s) they look after <span className="req">*</span></label>
            <div className="chip-picker">
              {districts.length === 0 && <span className="hint">Add districts first (Master Data → Districts).</span>}
              {districts.map((d) => (
                <button key={d.value} type="button" className={`pick ${f.district_ids.includes(String(d.value)) ? "on" : ""}`}
                  onClick={() => toggle(String(d.value))}>{d.label}</button>
              ))}
            </div>
          </div>
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary"
            disabled={!filled || save.isPending || (review.reviewing && !review.ready)}
            onClick={() => (review.reviewing ? save.mutate() : review.start(box.current))}>
            {reviewLabel(review, { busy: save.isPending, submitText: "Add District Manager" })}
          </button>
        </footer>
      </div>
    </div>
  );
}

export default function DistrictManagers() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { data: boot } = useBootstrap();
  const isSA = user?.role === "SA";
  const [scope, setScope] = useOrgScope("district-managers");
  const [district, setDistrict] = useState("");
  const [adding, setAdding] = useState(false);
  const [login, setLogin] = useState(null);
  const orgId = isSA ? scope.organisation_id : user?.organisation_id;

  const districtsOfOrg = useQuery({
    queryKey: ["scope-options", "districts", orgId, "dm"],
    queryFn: async () => (await api.get(`/districts?page_size=200${isSA ? `&organisation_id=${orgId}` : ""}`)).data.data
      .map((d) => ({ value: d.id, label: d.name })),
    enabled: !!orgId,
  });
  const districts = districtsOfOrg.data || [];

  const list = useQuery({
    queryKey: ["district-managers", orgId, district],
    queryFn: async () => {
      const p = new URLSearchParams();
      if (isSA) p.set("organisation_id", orgId);
      if (district) p.set("district_id", district);
      return (await api.get(`/users/district-managers?${p}`)).data.data;
    },
    enabled: !!orgId,
  });
  const rows = list.data || [];

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Master Data</div>
          <h1><span className="page-ico"><Icon name="district-managers" size={20} /></span>District Managers</h1>
        </div>
        {!isSA && (
          <div className="page-actions">
            <button className="btn btn-accent" onClick={() => setAdding(true)}><Plus size={16} /> New District Manager</button>
          </div>
        )}
      </div>

      {isSA && <ScopePicker needs="org" scope={scope} setScope={setScope} boot={boot} isSA />}
      {isSA && !orgId ? <ScopeEmpty needs="org" label="District Managers" isSA /> : (
        <>
          <div className="filterbar">
            <div className="filterbar-row">
              <span className="filterbar-label">Filters</span>
              <select className={`select filter-ctl ${district ? "on" : ""}`} value={district} onChange={(e) => setDistrict(e.target.value)}>
                <option value="">District: All</option>
                {districts.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
          </div>
          <div className="card">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Mobile</th><th>Districts</th><th>Status</th><th>Last login</th></tr>
                </thead>
                <tbody>
                  {list.isLoading
                    ? Array.from({ length: 4 }).map((_, i) => <tr key={i}><td colSpan={6}><div className="skeleton" style={{ width: "60%" }} /></td></tr>)
                    : rows.map((u) => (
                        <tr key={u.id}>
                          <td>{u.full_name}</td>
                          <td className="mono-sm">{u.email}</td>
                          <td>{u.phone || "—"}</td>
                          <td>{u.districts.map((d) => d.name).join(", ") || "—"}</td>
                          <td><Badge value={u.status} /></td>
                          <td className="muted">{u.last_login_at ? toDMY(u.last_login_at) : "—"}</td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>
            {!list.isLoading && rows.length === 0 && (
              <div className="empty">No district managers yet{district ? " for this district" : ""}.</div>
            )}
          </div>
          {!isSA && <p className="muted" style={{ margin: 0, fontSize: ".8125rem" }}>Reset a district manager's password or disable their login from Users &amp; Access.</p>}
        </>
      )}

      {adding && (
        <NewDistrictManager districts={districts} onClose={() => setAdding(false)}
          onDone={(l) => { setAdding(false); setLogin(l); qc.invalidateQueries({ queryKey: ["district-managers"] }); qc.invalidateQueries({ queryKey: ["users"] }); }} />
      )}
      {login && <LoginCreated {...login} onDone={() => setLogin(null)} />}
    </div>
  );
}
