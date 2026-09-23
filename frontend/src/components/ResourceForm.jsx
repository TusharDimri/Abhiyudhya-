import { useState, useMemo, useEffect } from "react";
import { useQueries } from "@tanstack/react-query";
import api from "../lib/api";
import StudentRoster from "./StudentRoster";
import { staticOptionsFor, enumList, splitList, joinList } from "../lib/fieldOptions";

// display label for an async-loaded option row
const displayFor = (row) =>
  row.full_name || row.name || row.org_name || row.label || row.topic || row.id;

// option-list key (used in bootstrap + forms) -> API resource route.
// For Super Admin these lists must be re-fetched filtered by the chosen org,
// so we need the real route (some differ by hyphen).
const OPTIONKEY_RESOURCE = {
  schools: "schools", labs: "labs", districts: "districts", states: "states",
  sectors: "sectors", job_roles: "job-roles", social_categories: "social-categories",
  academic_years: "academic-years", modules: "modules", units: "units",
  sessions: "sessions", students: "students", employers: "employers", equipment: "equipment",
  principals: "principals", trainers: "trainers",
};

// Field types that need the full width of the drawer.
const WIDE = new Set(["textarea", "file", "multiselect", "studentmarks"]);

// A field may cascade off more than one answer (a curriculum module list is
// narrowed by job role *and* by Employability/Vocational). The first parent
// gates the fetch; the rest refine it once they have a value.
const depsOf = (f) => (f.dependsOn ? (Array.isArray(f.dependsOn) ? f.dependsOn : [f.dependsOn]) : []);

export default function ResourceForm({
  mod, initial, boot, context, onClose, onSubmit, saving,
  isSA, orgScoped, orgOptions, role,
}) {
  const isNew = !initial;
  const ctx = context || {};
  const options = boot?.options;
  const myScope = boot?.my_scope;

  // Build the working field list:
  //  1. drop fields that don't apply to this role (onlyFor / hideFor)
  //  2. for Super Admin on a tenant resource, inject the Organisation selector
  //     and make org-scoped dropdowns cascade off it.
  const fields = useMemo(() => {
    let base = (mod.fields || []).filter(
      (f) =>
        (!f.onlyFor || (role && f.onlyFor.includes(role))) &&
        (!f.hideFor || !(role && f.hideFor.includes(role)))
    );
    if (!isSA || !orgScoped) return base;
    const orgField = { name: "organisation_id", label: "Organisation", type: "select", required: true, options: orgOptions || [], group: "Organisation" };
    const mapped = base.map((f) => {
      if (f.optionsKey && OPTIONKEY_RESOURCE[f.optionsKey] && !f.dependsOn) {
        return { ...f, async: true, _resource: OPTIONKEY_RESOURCE[f.optionsKey], dependsOn: { field: "organisation_id", param: "organisation_id" } };
      }
      return f;
    });
    return [orgField, ...mapped];
  }, [mod, isSA, orgScoped, orgOptions, role]);

  const [values, setValues] = useState(() => {
    const v = {};
    for (const f of fields) {
      let val = initial?.[f.name];
      if (f.type === "checkbox") val = !!val;
      else if (f.type === "studentmarks") val = Array.isArray(val) ? val : undefined;
      else if (val === null || val === undefined) val = "";
      else if (typeof val === "string" && /^\d{4}-\d{2}-\d{2}T/.test(val)) val = val.slice(0, 10);
      // prefill from what we already know about this user (new records only,
      // and not for SA who chooses an org first)
      if (isNew && !isSA && (val === "" || val === false)) {
        if (ctx[f.name] != null) val = ctx[f.name];
        else if (f.defaults && role && f.defaults[role] != null) val = f.defaults[role];
        else if (f.defaultValue != null)
          val = typeof f.defaultValue === "function" ? f.defaultValue() : f.defaultValue;
      }
      v[f.name] = val;
    }
    return v;
  });
  const [errors, setErrors] = useState({});
  const [uploading, setUploading] = useState("");
  const [custom, setCustom] = useState({});

  const asyncFields = useMemo(
    () => fields.filter((f) =>
      (f.type === "select" || f.type === "multiselect") &&
      !f.dynamicOptions && !f.enumKey &&
      (f.async || (f.optionsKey && !(options && options[f.optionsKey])))
    ),
    [fields, options]
  );

  const childrenOf = useMemo(() => {
    const m = {};
    for (const f of fields) for (const d of depsOf(f)) (m[d.field] ||= []).push(f.name);
    return m;
  }, [fields]);

  const asyncResults = useQueries({
    queries: asyncFields.map((f) => {
      const deps = depsOf(f);
      const routeName = f._resource || f.optionsKey;
      const params = new URLSearchParams({ page_size: "200" });
      for (const d of deps) if (values[d.field]) params.set(d.param, values[d.field]);
      for (const [k, val] of Object.entries(f.staticParams || {})) params.set(k, val);
      return {
        queryKey: ["options", routeName, params.toString()],
        queryFn: async () => (await api.get(`/${routeName}?${params}`)).data.data,
        enabled: !deps.length || !!values[deps[0].field],
        staleTime: 60000,
      };
    }),
  });
  const asyncMap = {};
  asyncFields.forEach((f, i) => { asyncMap[f.name] = asyncResults[i]?.data || []; });

  // Context handed to every derive/dynamicOptions function: the reference
  // lists, the fixed enums, this user's own scope, and the rows already
  // fetched for the selects above (so a field can be filled from the record
  // the user just chose - an assessment knows the student's class).
  // rebuilt each render on purpose: it carries `rows`, which changes as the
  // selects above finish loading
  const dctx = { boot, options, enums: boot?.enums, myScope, role, profile: ctx, rows: asyncMap, isNew };

  // --- derived answers -------------------------------------------------
  // A field with `derive` is not asked for while its inputs give an
  // unambiguous answer (e.g. lab + class fixes the job role). It falls back
  // to a normal control the moment the answer stops being unambiguous.
  const derived = {};
  for (const f of fields) {
    if (!f.derive) continue;
    let d;
    try { d = f.derive(values, dctx); } catch { d = undefined; }
    if (d !== undefined && d !== null && d !== "") derived[f.name] = d;
  }

  // a changed answer invalidates everything that cascades from it, recursively
  const clearDescendants = (next, ...names) => {
    const stack = [...names];
    while (stack.length) {
      const cur = stack.pop();
      for (const child of childrenOf[cur] || []) {
        if (next[child] === "") continue;
        next[child] = "";
        stack.push(child);
      }
    }
    return next;
  };

  const derivedKey = JSON.stringify(derived);
  useEffect(() => {
    const changes = Object.entries(derived).filter(([k, v]) => String(values[k] ?? "") !== String(v));
    if (!changes.length) return;
    // a derived job role is still a changed job role: the module/unit/session
    // chosen under the old one no longer applies
    setValues((v) => clearDescendants({ ...v, ...Object.fromEntries(changes) }, ...changes.map(([k]) => k)));
  }, [derivedKey]); // eslint-disable-line

  const set = (name, val) => setValues((v) => clearDescendants({ ...v, [name]: val }, name));

  const visible = (f) => (f.showIf ? !!f.showIf(values, role) : true);

  const optionsFor = (f) => {
    if (f.dynamicOptions) {
      const list = f.dynamicOptions(values, dctx) || [];
      return list.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
    }
    if (f.enumKey) {
      const list = enumList(boot, f.enumKey);
      if (list) return list;
    }
    if (f.options) return f.options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
    // A list fetched for this form wins over the bootstrap one: it is the
    // narrowed one (by parent, or by the organisation a Super Admin picked).
    if (asyncFields.includes(f)) {
      return (asyncMap[f.name] || []).map((r) => ({ value: f.valueKey ? r[f.valueKey] : r.id, label: displayFor(r) }));
    }
    return staticOptionsFor(f, boot) || [];
  };

  // A value we already know for a field: from the profile context, or a
  // per-role default declared on the field (e.g. feedback source = "student").
  const knownValue = (f) => {
    if (ctx[f.name] != null && ctx[f.name] !== "") return ctx[f.name];
    if (f.defaults && role && f.defaults[role] != null) return f.defaults[role];
    return undefined;
  };

  // A field is auto-known when: we're creating, the role is listed in autoFor,
  // and we already have a value for it. It is filled and shown read-only (in
  // the "known" panel) rather than asked for.
  const isKnown = (f) =>
    isNew && !isSA && Array.isArray(f.autoFor) && role && f.autoFor.includes(role) &&
    knownValue(f) !== undefined;

  const isDerived = (f) => derived[f.name] !== undefined && !isKnown(f);

  // human label for a known/derived read-only value (resolves ids via options)
  const knownLabel = (f) => {
    const val = values[f.name];
    if (f.name === "student_id" || f.name === "trainer_id") return "You (this account)";
    const opt = optionsFor(f).find((o) => String(o.value) === String(val));
    if (opt) return opt.label;
    const fromBoot = Object.values(options || {})
      .flat()
      .find((o) => o && String(o.value) === String(val));
    return fromBoot?.label ?? String(val ?? "");
  };

  const upload = async (f, file) => {
    if (!file) return;
    setUploading(f.name);
    try {
      const { data } = await api.post("/uploads/presign", {
        filename: file.name, content_type: file.type || "application/octet-stream",
      });
      await fetch(data.upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
      set(f.name, data.public_path);
    } catch {
      setErrors((e) => ({ ...e, [f.name]: "Upload unavailable — paste a URL below." }));
    } finally {
      setUploading("");
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const errs = {};
    for (const f of fields) {
      if (!visible(f) || isKnown(f) || isDerived(f)) continue;
      const v = values[f.name];
      const empty = v === "" || v == null || (Array.isArray(v) && !v.length);
      if (f.required && empty && v !== false) errs[f.name] = "Required";
      if (!empty && f.validate) {
        const msg = f.validate(v, values);
        if (msg) errs[f.name] = msg;
      }
    }
    setErrors(errs);
    if (Object.keys(errs).length) {
      const first = document.querySelector(".field-error");
      first?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const payload = {};
    for (const f of fields) {
      // A branch that isn't on screen isn't part of this record: clear it, so
      // switching a day from "Teaching" to "Parent Teachers Meeting" doesn't
      // leave the old class details behind.
      if (!visible(f)) {
        if (f.type === "studentmarks") payload[f.name] = [];
        else if (f.type !== "checkbox") payload[f.name] = null;
        continue;
      }
      if (f.type === "studentmarks") {
        if (Array.isArray(values[f.name])) payload[f.name] = values[f.name];
        continue;
      }
      payload[f.name] = values[f.name] === "" ? null : values[f.name];
    }
    onSubmit(payload);
  };

  // Only hard-disable a dependent select when it needs its parent to fetch
  // options. A field with dynamicOptions has a safe fallback list.
  const fieldDisabled = (f) => {
    if (f.disabledWhen) return !!f.disabledWhen(values);
    const deps = depsOf(f);
    if (!deps.length || f.dynamicOptions || f.allowCustom) return false;
    return !values[deps[0].field];
  };

  const shown = fields.filter(visible);
  const autoFields = shown.filter((f) => isKnown(f) || isDerived(f));
  const bodyFields = shown.filter((f) => !isKnown(f) && !isDerived(f));

  // group the remaining questions into labelled sections, in the order the
  // groups first appear in the catalog
  const groups = [];
  for (const f of bodyFields) {
    const name = f.group || mod.defaultGroup || "Details";
    let g = groups.find((x) => x.name === name);
    if (!g) groups.push((g = { name, fields: [] }));
    g.fields.push(f);
  }

  const renderControl = (f) => {
    const val = values[f.name];
    if (f.type === "textarea")
      return <textarea className="input" rows={f.rows || 3} value={val ?? ""} placeholder={f.placeholder || ""} onChange={(e) => set(f.name, e.target.value)} />;

    if (f.type === "checkbox")
      return (
        <label className="switch-row">
          <input type="checkbox" checked={!!val} onChange={(e) => set(f.name, e.target.checked)} />
          <span className="hint">{val ? "Yes" : "No"}</span>
        </label>
      );

    if (f.type === "multiselect") {
      const selected = splitList(val);
      const opts = optionsFor(f);
      const toggle = (v) =>
        set(f.name, joinList(selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]));
      return (
        <>
          <div className="chip-picker">
            {opts.length === 0 && <span className="hint">{f.emptyHint || "No options yet."}</span>}
            {opts.map((o) => (
              <button
                type="button"
                key={o.value}
                className={`pick ${selected.includes(String(o.value)) ? "on" : ""}`}
                onClick={() => toggle(String(o.value))}
              >
                {o.label}
              </button>
            ))}
            {selected.filter((s) => !opts.some((o) => String(o.value) === s)).map((s) => (
              <button type="button" key={s} className="pick on" onClick={() => toggle(s)}>{s}</button>
            ))}
          </div>
          {f.allowCustom && (
            <div className="chip-add">
              <input
                className="input"
                placeholder={f.customPlaceholder || "Add another…"}
                value={custom[f.name] ?? ""}
                onChange={(e) => setCustom((c) => ({ ...c, [f.name]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key !== "Enter") return;
                  e.preventDefault();
                  const v = (custom[f.name] || "").trim();
                  if (v && !selected.includes(v)) set(f.name, joinList([...selected, v]));
                  setCustom((c) => ({ ...c, [f.name]: "" }));
                }}
              />
              <span className="hint">Press Enter to add.</span>
            </div>
          )}
        </>
      );
    }

    if (f.type === "studentmarks")
      return <StudentRoster field={f} values={values} value={val} onChange={(v) => set(f.name, v)} />;

    if (f.type === "select") {
      const opts = optionsFor(f);
      const keep =
        val && !opts.some((o) => String(o.value) === String(val))
          ? [{ value: val, label: `${knownLabel(f)} (current)` }]
          : [];
      return (
        <select className="select" value={val ?? ""} disabled={fieldDisabled(f)} onChange={(e) => set(f.name, e.target.value)}>
          <option value="">
            {fieldDisabled(f)
              ? `Select ${(f.dependsLabel || depsOf(f)[0]?.field || "").replace(/_id$/, "").replace(/_/g, " ")} first`
              : "— Select —"}
          </option>
          {[...keep, ...opts].map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      );
    }

    if (f.type === "file")
      return (
        <>
          <input type="file" className="input" accept={f.accept || "image/*,application/pdf"} onChange={(e) => upload(f, e.target.files[0])} />
          {uploading === f.name && <span className="hint">Uploading…</span>}
          <input className="input" placeholder="…or paste file URL" value={val ?? ""} onChange={(e) => set(f.name, e.target.value)} style={{ marginTop: 4 }} />
        </>
      );

    return (
      <input
        className="input"
        type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "email" ? "email" : f.type === "tel" ? "tel" : "text"}
        placeholder={f.placeholder || ""}
        min={f.min}
        max={f.max}
        value={val ?? ""}
        onChange={(e) => set(f.name, e.target.value)}
      />
    );
  };

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="drawer" onSubmit={submit}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>{initial ? "Edit" : "New"} {mod.singular}</h3>
            {mod.formHint && <span className="drawer-sub">{mod.formHint}</span>}
          </div>
          <button type="button" className="close" onClick={onClose}>×</button>
        </header>
        <div className="body">
          {isSA && orgScoped && (
            <div className="prefill-note">🏢 Select the organisation first — dependent lists load for that organisation.</div>
          )}

          {autoFields.length > 0 && (
            <div className="known-panel">
              <div className="known-title">✓ Already filled in — you don't need to enter these</div>
              <div className="known-grid">
                {autoFields.map((f) => (
                  <div className="known-item" key={f.name}>
                    <span className="known-k">{f.label}</span>
                    <span className="known-v">{knownLabel(f)}</span>
                    {isDerived(f) && f.deriveNote && <span className="known-why">{f.deriveNote}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {groups.map((g) => (
            <fieldset className="fgroup" key={g.name}>
              {groups.length > 1 && <legend>{g.name}</legend>}
              <div className="fgrid">
                {g.fields.map((f) => (
                  <div className={`field ${WIDE.has(f.type) || f.wide ? "wide" : ""}`} key={f.name}>
                    <label>{f.label} {f.required && <span className="req">*</span>}</label>
                    {renderControl(f)}
                    {f.hint && <span className="hint">{f.hint}</span>}
                    {errors[f.name] && <span className="field-error">{errors[f.name]}</span>}
                  </div>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Saving…" : initial ? "Save changes" : `Create ${mod.singular}`}
          </button>
        </footer>
      </form>
    </div>
  );
}
