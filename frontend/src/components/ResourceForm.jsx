import { useState, useMemo, useEffect, useRef } from "react";
import { Check, Crosshair, MapPin, X } from "lucide-react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useAuth } from "../lib/auth";
import api from "../lib/api";
import StudentRoster from "./StudentRoster";
import { RowsInput } from "./ProfileFields";
import DateInput from "./DateInput";
import { toDMY } from "../lib/dates";
import { useLocationFix, locationPayload, locationErrorMessage } from "../lib/location";
import { staticOptionsFor, enumList, splitList, joinList, optionText } from "../lib/fieldOptions";
import { useReviewGate, ReviewNotice, reviewLabel } from "./ReviewGate";

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
const WIDE = new Set(["textarea", "file", "multiselect", "studentmarks", "geopoint", "rows"]);

// A field may cascade off more than one answer (a curriculum module list is
// narrowed by job role *and* by Employability/Vocational). The first parent
// gates the fetch; the rest refine it once they have a value.
const depsOf = (f) => (f.dependsOn ? (Array.isArray(f.dependsOn) ? f.dependsOn : [f.dependsOn]) : []);

// Last answers a user gave on a form, per field marked `remember` - kept in
// this browser only, as a convenience (nothing depends on it being there).
const memoryKey = (userId, resource, field) => `rnaf.remember.${userId}.${resource}.${field}`;
const recall = (key) => {
  try { const v = localStorage.getItem(key); return v == null ? undefined : JSON.parse(v); } catch { return undefined; }
};
const keep = (key, value) => {
  try {
    if (value === "" || value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch { /* private mode / storage full: just don't remember */ }
};

export default function ResourceForm({
  mod, resource, initial, boot, context, onClose, onSubmit, saving,
  isSA, orgScoped, orgOptions, role,
}) {
  const { user } = useAuth();
  const fromMemory = useRef(new Set());
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
      else if (f.type === "rows") val = Array.isArray(val) ? val.map(({ id, ...r }) => r) : [];
      else if (val === null || val === undefined) val = "";
      else if (typeof val === "string" && /^\d{4}-\d{2}-\d{2}T/.test(val)) val = val.slice(0, 10);
      // prefill from what we already know about this user (new records only,
      // and not for SA who chooses an org first)
      if (isNew && !isSA && (val === "" || val === false)) {
        if (ctx[f.name] != null) val = ctx[f.name];
        else if (f.defaults && role && f.defaults[role] != null) val = f.defaults[role];
        else if (f.defaultValue != null)
          val = typeof f.defaultValue === "function"
            ? f.defaultValue({ options, profile: ctx, role })
            : f.defaultValue;
        if ((val === "" || val == null) && f.remember && user?.id) {
          const mem = recall(memoryKey(user.id, resource, f.name));
          if (mem !== undefined) { val = mem; fromMemory.current.add(f.name); }
        }
      }
      v[f.name] = val;
    }
    return v;
  });
  // what was already filled in when the form opened
  const [prefilled] = useState(() => new Set(fields.filter((f) => {
    const v = values[f.name];
    return v !== "" && v != null && v !== false && !fromMemory.current.has(f.name);
  }).map((f) => f.name)));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [locating, setLocating] = useState(false);
  const review = useReviewGate();
  const drawerRef = useRef(null);
  const loc = useLocationFix();
  // a trainer's new record is stamped with where they were (never shown here)
  const needsLocation = !!mod.captureLocation && isNew && role === "VT";
  const [uploading, setUploading] = useState("");
  const [custom, setCustom] = useState({});

  // `lookup`: typing a name that was used before fills in what went with it
  // (a returning guest lecturer's details, a visited organisation's address).
  const lookupField = fields.find((f) => f.lookup);
  const pastRows = useQuery({
    queryKey: ["lookup", resource],
    queryFn: async () => (await api.get(`/${resource}?page_size=100&sort=created_at&order=desc`)).data.data,
    enabled: !!lookupField && isNew && !!resource,
    staleTime: 60000,
  });
  const pastByName = useMemo(() => {
    const m = new Map();
    if (!lookupField) return m;
    for (const r of pastRows.data || []) {
      const name = String(r[lookupField.name] || "").trim();
      if (name && !m.has(name.toLowerCase())) m.set(name.toLowerCase(), r);
    }
    return m;
  }, [pastRows.data, lookupField]);
  const [filledFrom, setFilledFrom] = useState("");

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

  const setLooked = (f, val) => {
    const past = pastByName.get(String(val).trim().toLowerCase());
    if (!past) { set(f.name, val); return; }
    setValues((v) => {
      const next = { ...v, [f.name]: val };
      // fill what is still empty; never overwrite what they typed
      for (const k of f.lookup.fill) if ((next[k] === "" || next[k] == null) && past[k] != null) next[k] = past[k];
      return next;
    });
    setFilledFrom(String(past[f.name]));
  };

  // createOnly: asked when adding a record, not when editing it (e.g. an org's first admin)
  const visible = (f) => (f.createOnly && !isNew ? false : f.showIf ? !!f.showIf(values, role) : true);

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
  // the "known" panel) rather than asked for. A field that is readOnlyFor the
  // role is always shown there once it has a value, new or existing.
  const isKnown = (f) =>
    (isNew && !isSA && Array.isArray(f.autoFor) && role && f.autoFor.includes(role) &&
      knownValue(f) !== undefined) ||
    (Array.isArray(f.readOnlyFor) && role && f.readOnlyFor.includes(role) &&
      values[f.name] !== "" && values[f.name] != null && (!isNew || prefilled.has(f.name)));

  const isDerived = (f) => derived[f.name] !== undefined && !isKnown(f);

  // human label for a known/derived read-only value (resolves ids via options)
  const knownLabel = (f) => {
    const val = values[f.name];
    if (f.type === "date") return toDMY(val);
    if (f.type === "time") return String(val ?? "").slice(0, 5);
    const opt = optionsFor(f).find((o) => String(o.value) === String(val));
    const isMe = f.name === "trainer_id" && String(val) === String(ctx.trainer_id);
    if (opt) return isMe ? `${opt.label} (you)` : opt.label;
    if (isMe) return "You (this account)";
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

  const submit = async (e) => {
    e.preventDefault();
    setFormError("");
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
    // first press: back to the top to look it all over; Submit unlocks after 30s
    if (!review.reviewing) { review.start(drawerRef.current); return; }
    if (!review.ready) return;
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
    if (isNew && user?.id) {
      for (const f of fields) if (f.remember) keep(memoryKey(user.id, resource, f.name), values[f.name]);
    }
    if (needsLocation && loc) {
      setLocating(true);
      try {
        Object.assign(payload, locationPayload(await loc.getFresh()));
      } catch (err) {
        setFormError(locationErrorMessage(err));
        return;
      } finally {
        setLocating(false);
      }
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

  const shown = fields.filter((f) => visible(f) && !f.hidden);
  // Known from the start (their profile, a default they can't change): the
  // panel at the top. Worked out from other answers (job role from class):
  // stays in its place, read-only - it never jumps away when the answer
  // arrives. `quiet` fields are filled in and saved but not shown at all.
  const autoFields = shown.filter((f) => isKnown(f) && !f.quiet);
  const bodyFields = shown.filter((f) => !isKnown(f) && !(isDerived(f) && f.quiet));

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
                {optionText(o.label)}
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

    if (f.type === "rows")
      return <RowsInput table={f.table} boot={boot} value={val} onChange={(v) => set(f.name, v)} />;

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
          {[...keep, ...opts].map((o) => <option key={o.value} value={o.value}>{optionText(o.label)}</option>)}
        </select>
      );
    }

    if (f.type === "date")
      return (
        <DateInput
          value={val ?? ""}
          min={typeof f.min === "function" ? f.min() : f.min}
          max={typeof f.max === "function" ? f.max() : f.max}
          onChange={(v) => set(f.name, v)}
        />
      );

    if (f.type === "geopoint") return <GeoPointInput f={f} values={values} setValues={setValues} />;

    if (f.type === "file")
      return (
        <>
          <input type="file" className="input" accept={f.accept || "image/*,application/pdf"} onChange={(e) => upload(f, e.target.files[0])} />
          {uploading === f.name && <span className="hint">Uploading…</span>}
          {uploading !== f.name && val && !/^https?:/.test(val) && <span className="hint">Uploaded</span>}
          <input className="input" placeholder="…or paste file URL" value={val ?? ""} onChange={(e) => set(f.name, e.target.value)} style={{ marginTop: 4 }} />
        </>
      );

    if (f.lookup) {
      const listId = `past-${f.name}`;
      return (
        <>
          <input className="input" list={listId} placeholder={f.placeholder || ""} value={val ?? ""}
            onChange={(e) => setLooked(f, e.target.value)} autoComplete="off" />
          <datalist id={listId}>
            {[...pastByName.values()].map((r) => <option key={r.id} value={r[f.name]} />)}
          </datalist>
          {filledFrom && filledFrom.toLowerCase() === String(val ?? "").trim().toLowerCase() && (
            <span className="hint">Details filled in from an earlier entry - check they're still right.</span>
          )}
        </>
      );
    }

    return (
      <input
        className="input"
        type={["number", "email", "tel", "time"].includes(f.type) ? f.type : "text"}
        placeholder={f.placeholder || ""}
        min={typeof f.min === "function" ? f.min() : f.min}
        max={typeof f.max === "function" ? f.max() : f.max}
        value={val ?? ""}
        onChange={(e) => set(f.name, e.target.value)}
      />
    );
  };

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="drawer" onSubmit={submit} ref={drawerRef}>
        <header>
          <div>
            <h3 style={{ margin: 0 }}>{initial ? "Edit" : "New"} {mod.singular}</h3>
            {mod.formHint && <span className="drawer-sub">{mod.formHint}</span>}
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close"><X size={18} strokeWidth={2} /></button>
        </header>
        <div className="body">
          <ReviewNotice gate={review} locked={boot?.resources?.[resource]?.can_edit === false} />
          {isSA && orgScoped && (
            <div className="prefill-note">Select the organisation first — dependent lists load for that organisation.</div>
          )}

          {autoFields.length > 0 && (
            <div className="known-panel">
              <div className="known-title"><Check size={14} /> Already filled in — you don't need to enter these</div>
              <div className="known-grid">
                {autoFields.map((f) => (
                  <div className="known-item" key={f.name}>
                    <span className="known-k">{f.label}</span>
                    <span className="known-v">{knownLabel(f)}</span>
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
                    {isDerived(f) ? (
                      <>
                        <div className="input derived-value" aria-readonly="true">{knownLabel(f)}</div>
                        {f.deriveNote && <span className="hint">{f.deriveNote}</span>}
                      </>
                    ) : renderControl(f)}
                    {f.hint && !isDerived(f) && <span className="hint">{f.hint}</span>}
                    {errors[f.name] && <span className="field-error">{errors[f.name]}</span>}
                  </div>
                ))}
              </div>
            </fieldset>
          ))}
        </div>
        {formError && <div className="form-error" role="alert"><MapPin size={15} /> {formError}</div>}
        <footer>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving || locating || (review.reviewing && !review.ready)}>
            {locating ? "Getting your location…" : reviewLabel(review, { busy: saving })}
          </button>
        </footer>
      </form>
    </div>
  );
}

/* A place as latitude + longitude (e.g. where a school is): typed in, or taken
   from this device's current position. Writes `f.name` (latitude) and
   `f.lngField` (longitude). */
function GeoPointInput({ f, values, setValues }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const lat = values[f.name] ?? "";
  const lng = values[f.lngField] ?? "";
  const put = (patch) => setValues((v) => ({ ...v, ...patch }));
  const useHere = () => {
    if (!("geolocation" in navigator)) { setErr("This browser can't share its location."); return; }
    setBusy(true); setErr("");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        put({
          [f.name]: Number(pos.coords.latitude.toFixed(6)),
          [f.lngField]: Number(pos.coords.longitude.toFixed(6)),
        });
        setBusy(false);
      },
      (e) => { setErr(e.code === 1 ? "Location access is blocked for this site." : "Couldn't get a location - try again."); setBusy(false); },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    );
  };
  return (
    <div className="geopoint">
      <div className="geopoint-row">
        <input className="input" type="number" step="any" placeholder="Latitude e.g. 18.5204" value={lat}
          onChange={(e) => put({ [f.name]: e.target.value })} aria-label="Latitude" />
        <input className="input" type="number" step="any" placeholder="Longitude e.g. 73.8567" value={lng}
          onChange={(e) => put({ [f.lngField]: e.target.value })} aria-label="Longitude" />
      </div>
      <button type="button" className="btn btn-ghost btn-sm" onClick={useHere} disabled={busy}>
        {busy ? "Getting location…" : <><Crosshair size={15} /> Use my current location</>}
      </button>
      {err && <span className="field-error">{err}</span>}
    </div>
  );
}
