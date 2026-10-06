import { useState } from "react";
import Icon from "../components/Icon";
import { Camera, Lock, PencilLine, Plus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api, { apiError } from "../lib/api";
import { useToast } from "../lib/toast";
import { useBootstrap } from "../hooks/useBootstrap";
import { toDMY } from "../lib/dates";
import { uploadFile } from "../lib/upload";
import { useAuth } from "../lib/auth";
import {
  GENERAL, ADDRESS, BANK, TABLES, PR_GENERAL, PR_SERVICE, PR_POSTING, PR_PRABHARI, PR_TABLES, Control,
} from "../components/ProfileFields";

/* The trainer's own service record, section by section. Each section is
   read first and edited on its own ("Edit" -> change -> "Save"). Identity
   details that are already on record are locked (the server enforces it);
   Aadhaar, account number and PAN only ever come back masked. */

// a label/value section, edited in place
function InfoSection({ title, fields, data, section, boot, save, saving, note }) {
  const [draft, setDraft] = useState(null);
  const required = new Set(data.required?.[section] || []);
  const locked = new Set(data.locked || []);
  const readOnly = (data.read_only_sections || []).includes(section);   // kept by their admin
  const editing = draft !== null;
  const display = (f) => {
    const v = f.show ? f.show(data) : data[f.name];
    if (v == null || v === "") return <span className="muted">—</span>;
    return f.type === "date" ? toDMY(v) : String(v);
  };

  const start = () => setDraft(Object.fromEntries(fields.filter((f) => !f.computed).map((f) => [f.name, data[f.name] ?? ""])));
  const submit = () => {
    const body = {};
    for (const [k, v] of Object.entries(draft)) if (!locked.has(k)) body[k] = v === "" ? null : v;
    save(body, () => setDraft(null));
  };

  return (
    <section className="card profile-card">
      <div className="profile-card-head">
        <h3>{title}</h3>
        {section && !editing && !readOnly && <button className="btn btn-ghost btn-sm" onClick={start}><PencilLine size={14} /> Edit</button>}
      </div>
      {note && <p className="muted profile-note">{note}</p>}
      {readOnly && <p className="muted profile-note">Kept by your admin - ask them if anything here needs changing.</p>}
      <dl className="profile-grid">
        {fields.map((f) => (
          <div key={f.name} className={`profile-item ${f.wide ? "wide" : ""}`}>
            <dt>{f.label}{editing && required.has(f.name) && <span className="req"> *</span>}</dt>
            <dd>
              {editing && !f.computed && !locked.has(f.name) ? (
                <Control f={f} boot={boot} value={draft[f.name]} onChange={(v) => setDraft((d) => ({ ...d, [f.name]: v }))} />
              ) : (
                <>
                  {display(f)}
                  {editing && locked.has(f.name) && <span className="lock-note" title="On record - ask your admin to change it"> <Lock size={13} /></span>}
                </>
              )}
              {editing && f.sensitive && !locked.has(f.name) && data[f.name] && (
                <span className="hint">Shown masked. Leave it as it is to keep it, or type the full number to change it.</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {editing && (
        <div className="profile-actions">
          {locked.size > 0 && fields.some((f) => locked.has(f.name)) && (
            <span className="muted"><Lock size={13} /> On record - ask your admin to change these.</span>
          )}
          <button className="btn btn-ghost" onClick={() => setDraft(null)} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
        </div>
      )}
    </section>
  );
}

// a list section (qualifications, jobs, trainings, postings), edited as rows
function TableSection({ listKey, tables = TABLES, data, boot, save, saving }) {
  const cfg = tables[listKey];
  const rows = data[listKey] || [];
  const [draft, setDraft] = useState(null);
  const editing = draft !== null;
  const blank = () => Object.fromEntries(cfg.columns.map((c) => [c.name, c.type === "yesno" ? null : ""]));
  const cell = (c, r) => {
    const v = c.show ? c.show(r) : r[c.name];
    if (v == null || v === "") return <span className="muted">—</span>;
    return c.type === "date" ? toDMY(v) : String(v);
  };
  const put = (i, name, v) => setDraft((d) => d.map((r, j) => (j === i ? { ...r, [name]: v } : r)));

  return (
    <section className="card profile-card">
      <div className="profile-card-head">
        <h3>{cfg.title}</h3>
        {!editing && <button className="btn btn-ghost btn-sm" onClick={() => setDraft(rows.length ? rows.map((r) => ({ ...r })) : [blank()])}>✎ Edit</button>}
      </div>
      <div className="table-wrap">
        <table className="data profile-table">
          <thead>
            <tr><th>Sr</th>{cfg.columns.map((c) => <th key={c.name}>{c.label}</th>)}{editing && <th />}</tr>
          </thead>
          <tbody>
            {(editing ? draft : rows).map((r, i) => (
              <tr key={r.id || `new-${i}`}>
                <td>{i + 1}</td>
                {cfg.columns.map((c) => (
                  <td key={c.name}>
                    {editing ? <Control f={c} boot={boot} value={r[c.name]} onChange={(v) => put(i, c.name, v)} /> : cell(c, r)}
                  </td>
                ))}
                {editing && (
                  <td><button className="btn btn-ghost btn-sm" title="Remove this row" onClick={() => setDraft((d) => d.filter((_, j) => j !== i))}>✕</button></td>
                )}
              </tr>
            ))}
            {!editing && rows.length === 0 && (
              <tr><td colSpan={cfg.columns.length + 1} className="muted" style={{ textAlign: "center" }}>Nothing added yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {editing && (
        <div className="profile-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => setDraft((d) => [...d, blank()])}><Plus size={15} /> Add row</button>
          <span className="grow" />
          <button className="btn btn-ghost" onClick={() => setDraft(null)} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" disabled={saving}
            onClick={() => save({ [listKey]: draft.map(({ id, ...r }) => r) }, () => setDraft(null))}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </section>
  );
}

// a picture held on the profile (photo, signatures)
function PictureSlot({ label, field, src, save, saving }) {
  const [busy, setBusy] = useState(false);
  const { push } = useToast();
  const pick = async (file) => {
    if (!file) return;
    setBusy(true);
    try { save({ [field]: await uploadFile(file) }); } catch (e) { push(e.message || "Upload failed", "error"); } finally { setBusy(false); }
  };
  return (
    <div className="picture-slot">
      <div className="picture-box">{src ? <img src={src} alt={label} /> : <span className="muted">No {label.toLowerCase()} yet</span>}</div>
      <label className="btn btn-ghost btn-sm">
        {busy || saving ? "Uploading…" : src ? "Replace" : "Upload"} {label}
        <input type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files[0])} />
      </label>
    </div>
  );
}

// ------------------------------------------------------------ page parts
function Hero({ d, subtitle, chips, save }) {
  const { push } = useToast();
  const initials = (d.full_name || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <section className="card profile-hero">
      <div className="profile-photo">
        {d.photo_src ? <img src={d.photo_src} alt="" /> : <span>{initials}</span>}
        <label className="profile-photo-edit" title="Change photo">
          <Camera size={16} /><input type="file" accept="image/*" hidden onChange={async (e) => {
            const f = e.target.files[0]; if (!f) return;
            try { save({ photo_url: await uploadFile(f) }); } catch (err) { push(err.message || "Upload failed", "error"); }
          }} />
        </label>
      </div>
      <div>
        <h1 style={{ margin: 0 }}>{d.full_name}</h1>
        <div className="muted">{subtitle}</div>
        <div className="profile-chips">
          {chips.filter((c) => c.text).map((c) => <span key={c.key} className="scope-chip">{c.icon} {c.text}</span>)}
        </div>
      </div>
    </section>
  );
}

function Pictures({ title, slots, d, save, saving }) {
  return (
    <section className="card profile-card">
      <div className="profile-card-head"><h3>{title}</h3></div>
      <div className="signatures">
        {slots.map(([label, field]) => (
          <PictureSlot key={field} label={label} field={field} src={d[field.replace("_url", "_src")]} save={save} saving={saving} />
        ))}
      </div>
    </section>
  );
}

const withSchool = (p) => p.school_name && `${p.school_name}${p.udise_code ? ` (${p.udise_code})` : ""}`;
const withBlock = (p) => p.district && `${p.district}${p.block ? ` (${p.block})` : ""}`;

function TrainerProfile({ d, common }) {
  const p = d.posting || {};
  return (
    <>
      <Hero d={d} save={common.save} subtitle={`Vocational Trainer${d.vtp_name ? ` · ${d.vtp_name}` : ""}`}
        chips={[{ icon: <Icon name="schools" size={14} />, key: "s", text: p.school_name }, { icon: <Icon name="labs" size={14} />, key: "l", text: p.lab_name }, { icon: <Icon name="job-roles" size={14} />, key: "j", text: p.job_role }]} />
      <InfoSection title="General Information" section="general" fields={GENERAL} {...common} />
      <InfoSection title="Address Details" section="address" fields={ADDRESS} {...common} />
      <InfoSection
        title="School Information" fields={[
          { name: "s_school", label: "School name", computed: true, show: () => withSchool(p) },
          { name: "s_district", label: "District (Block)", computed: true, show: () => withBlock(p) },
          { name: "s_year", label: "School year", computed: true, show: () => p.school_year },
          { name: "s_type", label: "School type", computed: true, show: () => p.school_type },
          { name: "s_lab", label: "Lab", computed: true, show: () => p.lab_name },
          { name: "s_role", label: "Job role", computed: true, show: () => p.job_role },
          { name: "s_doj", label: "Date of joining", computed: true, type: "date", show: () => p.date_of_joining },
          { name: "s_nature", label: "Nature of appointment", computed: true, show: () => p.appointment_nature },
        ]}
        note="Your current posting, as your admin has it on record."
        {...common}
      />
      <TableSection listKey="qualifications" {...common} />
      <TableSection listKey="experiences" {...common} />
      <TableSection listKey="trainings" {...common} />
      <TableSection listKey="postings" {...common} />
      <InfoSection title="Bank & Salary Details" section="bank" fields={BANK} {...common} />
      <Pictures title="Signatures" d={d} save={common.save} saving={common.saving}
        slots={[["VT signature", "vt_signature_url"], ["VTP signature", "vtp_signature_url"]]} />
    </>
  );
}

function PrincipalProfile({ d, common }) {
  const p = d.posting || {};
  const list = (xs) => (xs?.length ? xs.join(", ") : null);
  return (
    <>
      <Hero d={d} save={common.save} subtitle={[d.designation || "Principal", d.employee_id && `Employee ID ${d.employee_id}`].filter(Boolean).join(" · ")}
        chips={[{ icon: <Icon name="schools" size={14} />, key: "s", text: p.school_name }, { icon: <Icon name="districts" size={14} />, key: "d", text: withBlock(p) }]} />
      <InfoSection title="General Information" section="general" fields={PR_GENERAL} {...common} />
      <InfoSection title="Service Details" section="service" fields={PR_SERVICE} {...common} />
      <InfoSection title="Posting Details" section="posting" fields={PR_POSTING} {...common} />
      <InfoSection title="Address Details" section="address" fields={ADDRESS} {...common} />
      <InfoSection
        title="School Information" fields={[
          { name: "s_school", label: "School name", computed: true, show: () => withSchool(p) },
          { name: "s_district", label: "District (Block)", computed: true, show: () => withBlock(p) },
          { name: "s_type", label: "School type", computed: true, show: () => p.school_type },
          { name: "s_address", label: "School address", computed: true, show: () => p.school_address },
          { name: "s_contact", label: "School contact", computed: true, show: () => [p.school_phone, p.school_email].filter(Boolean).join(" · ") },
          { name: "s_years", label: "Years at this school", computed: true, show: () => d.years_at_school != null && `${d.years_at_school} years` },
          { name: "s_labs", label: "Vocational labs", computed: true, show: () => list(p.labs) },
          { name: "s_trainers", label: "Vocational trainers", computed: true, show: () => list(p.trainers) },
        ]}
        note="Your school, as your admin has it on record."
        {...common}
      />
      <InfoSection title="Vocational Prabhari" section="prabhari" fields={PR_PRABHARI}
        note="Your school's Vocational Prabhari, if there is one." {...common} />
      <TableSection listKey="qualifications" tables={PR_TABLES} {...common} />
      <TableSection listKey="postings" tables={PR_TABLES} {...common} />
      <TableSection listKey="trainings" tables={PR_TABLES} {...common} />
      <Pictures title="Signature & School Seal" d={d} save={common.save} saving={common.saving}
        slots={[["Signature", "signature_url"], ["School seal", "school_seal_url"]]} />
    </>
  );
}

export default function Profile() {
  const qc = useQueryClient();
  const { push } = useToast();
  const { user } = useAuth();
  const { data: boot } = useBootstrap();
  const q = useQuery({ queryKey: ["profile"], queryFn: async () => (await api.get("/profile")).data });
  const m = useMutation({
    mutationFn: async ({ body }) => (await api.patch("/profile", body)).data,
    onSuccess: (data, { done }) => {
      qc.setQueryData(["profile"], data);
      push("Profile saved", "success");
      done?.();
    },
    onError: (e) => push(apiError(e), "error"),
  });
  const save = (body, done) => m.mutate({ body, done });

  if (q.isLoading) return <div className="skeleton" style={{ height: 240, borderRadius: 12 }} />;
  if (q.isError) return <div className="card" style={{ padding: "1.2rem" }}>{apiError(q.error)}</div>;
  const common = { data: q.data, boot, save, saving: m.isPending };

  return (
    <div className="stack profile" style={{ gap: "1rem" }}>
      {user?.role === "PR"
        ? <PrincipalProfile d={q.data} common={common} />
        : <TrainerProfile d={q.data} common={common} />}
    </div>
  );
}
