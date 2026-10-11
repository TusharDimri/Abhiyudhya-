import { useRef, useState } from "react";
import Icon from "../../components/Icon";
import { Plus, Search, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../../lib/api";
import { useToast } from "../../lib/toast";
import { useBootstrap } from "../../hooks/useBootstrap";
import { useAuth } from "../../lib/auth";
import { optionText } from "../../lib/fieldOptions";
import { toDMY } from "../../lib/dates";
import { useReviewGate, ReviewNotice, reviewLabel } from "../../components/ReviewGate";
import LoginCreated from "../../components/LoginCreated";

const ROLE_LABELS = {
  SA: "Super Admin", OA: "Organisation Admin", DM: "District Manager", DEPT: "Department Login",
  PR: "Principal", VT: "Vocational Trainer",
};

export default function Users() {
  const qc = useQueryClient();
  const { push } = useToast();
  const { data: boot } = useBootstrap();
  const { user: me } = useAuth();
  // an org admin looks after their schools' principals and trainers only
  const isOA = me?.role === "OA";
  // the super admin looks after org admins' logins only - resetting passwords
  const isSA = me?.role === "SA";
  const roleChoices = isOA ? ["DM", "PR", "VT"] : isSA ? [] : Object.keys(ROLE_LABELS);
  const orgName = (id) => (boot?.options?.organisations || []).find((o) => String(o.value) === String(id))?.label;
  const schoolName = (id) => (boot?.options?.schools || []).find((s) => String(s.value) === String(id))?.label;
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [resetFor, setResetFor] = useState(null);

  const list = useQuery({
    queryKey: ["users", search, roleFilter],
    queryFn: async () => {
      const p = new URLSearchParams();
      if (search) p.set("search", search);
      if (roleFilter) p.set("role", roleFilter);
      return (await api.get(`/users?${p}`)).data;
    },
  });

  const users = list.data?.data || [];
  const canCreate = list.data?.can_create || [];

  const toggleStatus = useMutation({
    mutationFn: async (u) => api.patch(`/users/${u.id}`, { status: u.status === "active" ? "disabled" : "active" }),
    onSuccess: () => { push("Updated", "success"); qc.invalidateQueries({ queryKey: ["users"] }); },
    onError: (e) => push(apiError(e), "error"),
  });

  return (
    <div className="stack" style={{ gap: "1rem" }}>
      <div className="page-head">
        <div>
          <div className="crumb">Administration</div>
          <h1><span className="page-ico"><Icon name="users" size={20} /></span>Users & Access</h1>
        </div>
        {canCreate.length > 0 && <button className="btn btn-accent" onClick={() => setCreating(true)}><Plus size={16} /> New User</button>}
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <span className="search-ico"><Search size={15} /></span>
          <input className="input search" placeholder="Search users…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {roleChoices.length > 0 && (
          <select className="select filter-ctl" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">All roles</option>
            {roleChoices.map((k) => <option key={k} value={k}>{ROLE_LABELS[k]}</option>)}
          </select>
        )}
      </div>

      <div className="card">
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th>{isOA && <th>School</th>}{isSA && <th>Organisation</th>}<th>Status</th><th>Last login</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {list.isLoading
                ? Array.from({ length: 5 }).map((_, i) => <tr key={i}><td colSpan={isOA || isSA ? 7 : 6}><div className="skeleton" style={{ width: "60%" }} /></td></tr>)
                : users.map((u) => (
                    <tr key={u.id}>
                      <td>{u.full_name}</td>
                      <td className="mono-sm">{u.email}</td>
                      <td><span className="badge info">{u.role_label || ROLE_LABELS[u.role]}</span></td>
                      {isOA && <td>{schoolName(u.school_id) || "—"}</td>}
                      {isSA && <td>{orgName(u.organisation_id) || "—"}</td>}
                      <td><span className={`badge ${u.status === "active" ? "success" : "danger"}`}>{optionText(u.status)}</span></td>
                      <td className="muted">{u.last_login_at ? toDMY(u.last_login_at) : "—"}</td>
                      <td>
                        <div className="cell-actions">
                          <button className="btn btn-ghost btn-sm" onClick={() => setResetFor(u)}>Reset PW</button>
                          {!isSA && <button className="btn btn-ghost btn-sm" onClick={() => toggleStatus.mutate(u)}>
                            {u.status === "active" ? "Disable" : "Enable"}
                          </button>}
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
        {!list.isLoading && users.length === 0 && <div className="empty">No users found.</div>}
      </div>

      {creating && <CreateUser boot={boot} roles={canCreate} isSA={!!boot?.is_platform_admin} onClose={() => setCreating(false)}
        onDone={() => { setCreating(false); qc.invalidateQueries({ queryKey: ["users"] }); }} />}
      {resetFor && <ResetPassword user={resetFor} onClose={() => setResetFor(null)} />}
    </div>
  );
}

function CreateUser({ boot, roles, isSA, onClose, onDone }) {
  const { push } = useToast();
  const [f, setF] = useState({ role: roles[0] || "VT", full_name: "", email: "", password: "", organisation_id: "", school_id: "", lab_ids: [], district_ids: [] });
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const review = useReviewGate();
  const drawerRef = useRef(null);
  const [made, setMade] = useState(null);   // the login just created, to hand over
  const bootOpts = boot?.options || {};
  const orgOptions = bootOpts.organisations || [];

  // For SA, scope the school/lab/district pickers to the chosen organisation.
  const scoped = (resource) => useQuery({
    queryKey: ["user-opts", resource, f.organisation_id],
    queryFn: async () => (await api.get(`/${resource}?page_size=200&organisation_id=${f.organisation_id}`)).data.data
      .map((r) => ({ value: r.id, label: r.name })),
    enabled: isSA && !!f.organisation_id,
  });
  const saSchools = scoped("schools");
  const saLabs = scoped("labs");
  const saDistricts = scoped("districts");
  const opts = isSA
    ? { schools: saSchools.data || [], labs: saLabs.data || [], districts: saDistricts.data || [] }
    : bootOpts;

  const create = useMutation({
    mutationFn: async () => api.post("/users", { ...f, must_change_password: true }),
    onSuccess: () => { push("User created", "success"); setMade({ name: f.full_name, username: f.email.trim().toLowerCase(), password: f.password }); },
    onError: (e) => push(apiError(e), "error"),
  });

  const needsSchool = ["PR", "VT"].includes(f.role);
  const needsLab = f.role === "VT";
  const needsDistrict = ["DM", "DEPT"].includes(f.role);
  const orgLocked = isSA && f.role !== "SA" && !f.organisation_id;
  // every starred field has an answer (the server checks the same)
  const requiredFilled = f.full_name.trim() && f.email.trim()
    && (!needsSchool || f.school_id) && (!needsLab || f.lab_ids.length) && (!needsDistrict || f.district_ids.length);

  // saved: the same side form now shows what to hand over
  if (made) return <LoginCreated {...made} onDone={onDone} />;

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(480px,100%)" }} ref={drawerRef}>
        <header><h3 style={{ margin: 0 }}>New User</h3><button className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button></header>
        <div className="body">
          <ReviewNotice gate={review} />
          <div className="field"><label>Role <span className="req">*</span></label>
            <select className="select" value={f.role} onChange={(e) => set("role", e.target.value)}>
              {roles.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </div>
          {isSA && f.role !== "SA" && (
            <div className="field"><label>Organisation <span className="req">*</span></label>
              <select className="select" value={f.organisation_id} onChange={(e) => set("organisation_id", e.target.value)}>
                <option value="">— Select organisation —</option>
                {orgOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}
          <div className="field"><label>Full name <span className="req">*</span></label><input className="input" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></div>
          <div className="field"><label>Email <span className="req">*</span></label><input className="input" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} /></div>
          <div className="field"><label>Temporary password <span className="req">*</span></label>
            <input className="input" type="text" value={f.password} onChange={(e) => set("password", e.target.value)} placeholder="Min 8 chars, letters + number" />
            <span className="hint">User will be asked to change it on first login.</span>
          </div>
          {needsSchool && (
            <div className="field"><label>School <span className="req">*</span></label>
              <select className="select" value={f.school_id} disabled={orgLocked} onChange={(e) => set("school_id", e.target.value)}>
                <option value="">{orgLocked ? "Select organisation first" : "— Select —"}</option>
                {(opts.schools || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}
          {needsLab && (
            <div className="field"><label>Lab(s) <span className="req">*</span></label>
              <select className="select" multiple value={f.lab_ids} disabled={orgLocked} onChange={(e) => set("lab_ids", [...e.target.selectedOptions].map((o) => o.value))}>
                {(opts.labs || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <span className="hint">Hold Ctrl/Cmd to select multiple.</span>
            </div>
          )}
          {needsDistrict && (
            <div className="field"><label>District(s) <span className="req">*</span></label>
              <select className="select" multiple value={f.district_ids} disabled={orgLocked} onChange={(e) => set("district_ids", [...e.target.selectedOptions].map((o) => o.value))}>
                {(opts.districts || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}
        </div>
        <footer>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary"
            onClick={() => (review.reviewing ? create.mutate() : review.start(drawerRef.current))}
            disabled={create.isPending || orgLocked || !requiredFilled || f.password.length < 8 || (review.reviewing && !review.ready)}>
            {reviewLabel(review, { busy: create.isPending, busyText: "Creating…", submitText: "Create user" })}
          </button>
        </footer>
      </div>
    </div>
  );
}

function ResetPassword({ user, onClose }) {
  const { push } = useToast();
  const [pw, setPw] = useState("");
  const run = useMutation({
    mutationFn: async () => api.post(`/users/${user.id}/reset-password`, { new_password: pw }),
    onSuccess: () => { push("Password reset", "success"); onClose(); },
    onError: (e) => push(apiError(e), "error"),
  });
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer" style={{ width: "min(400px,100%)" }}>
        <header><h3 style={{ margin: 0 }}>Reset password</h3><button className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button></header>
        <div className="body">
          <p className="muted" style={{ marginTop: 0 }}>Set a temporary password for <b>{user.full_name}</b>. They'll be asked to change it on next login.</p>
          <div className="field"><label>New password</label>
            <input className="input" type="text" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Min 8 chars, letters + number" />
          </div>
        </div>
        <footer>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => run.mutate()} disabled={run.isPending || pw.length < 8}>Reset</button>
        </footer>
      </div>
    </div>
  );
}
