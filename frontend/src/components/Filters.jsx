/* URL-driven filter bar. Filter columns come from the backend (per-resource
   whitelist via bootstrap); controls are derived from the module's own field
   config so we never duplicate option lists. */
import { useQueries } from "@tanstack/react-query";
import api from "../lib/api";
import DateInput from "./DateInput";
import { staticOptionsFor } from "../lib/fieldOptions";

// status-ish columns that have no matching form field get sensible options here
const FALLBACK = {
  endorsement_status: ["submitted", "endorsed", "returned"],
  workflow_status: ["open", "in-progress", "resolved"],
  status: ["active", "deleted"],
  is_read: "bool",
  is_current: "bool",
  is_active: "bool",
  cwsn: "bool",
  placement_placed: "bool",
  apprenticeship_placed: "bool",
};

// Filter columns backed by another resource (a foreign key, not a fixed
// enum). Without this they'd fall through to a free-text box expecting a raw
// UUID - instead we fetch the real records and label them properly, same as
// the equivalent field in a create/edit form.
// Filter columns whose matching form control is a cascade (its options depend
// on the record being edited) - the filter bar has no such context, so it
// offers the full fixed list instead.
const FILTER_ENUM = {
  class_grade: "class_grades",
  class_taught: "class_grades",
  assessor_class: "class_grades",
  activity_type: "activity_types",
  day_type: "day_types",
  main_issue: "issue_main",
  verification_status: "verification_status",
  equipment_status: "equipment_status",
  trainer_status: "trainer_status",
  assessment_type: "assessment_types",
  lecture_type: "guest_lecture_types",
};

const RESOURCE_FILTERS = {
  student_id: { resource: "students", label: (r) => r.full_name || "Student" },
  module_id: { resource: "modules", label: (r) => r.name || "Module" },
  unit_id: { resource: "units", label: (r) => r.name || "Unit" },
  trainer_id: { resource: "trainers", label: (r) => r.full_name || "Trainer" },
  employer_id: { resource: "employers", label: (r) => r.org_name || "Employer" },
  equipment_id: {
    resource: "equipment",
    label: (r) => [r.school_name, r.academic_year, r.equipment_status].filter(Boolean).join(" · ") || "Equipment",
  },
};

const humanize = (s) =>
  s.replace(/_id$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// Columns that hold a name, not an id - the filter offers the same list the
// form writes from, so "Pune" typed by hand and "Pune" picked from the list
// are never two different values.
const FILTER_NAME_LIST = { state: "states", district: "districts" };

function controlFor(col, fields, boot, asyncOptions) {
  const field = fields.find((f) => f.name === col);
  if (asyncOptions?.[col]) {
    return { type: "select", label: field?.label || humanize(col), options: asyncOptions[col] };
  }
  // fixed enum list, bootstrap reference list, or an inline array - resolved
  // exactly the way the create/edit form resolves it, so a filter never
  // offers a value the form cannot produce
  const stat = staticOptionsFor(field, boot);
  if (stat) return { type: "select", label: field.label, options: stat };
  if (FILTER_NAME_LIST[col]) {
    const list = boot?.options?.[FILTER_NAME_LIST[col]];
    if (list?.length) {
      return {
        type: "select",
        label: field?.label || humanize(col),
        options: list.map((o) => ({ value: o.label, label: o.label })),
      };
    }
  }
  // a column filtered by an enum the form reaches through a cascade
  if (FILTER_ENUM[col]) {
    const list = boot?.enums?.[FILTER_ENUM[col]];
    if (list) return { type: "select", label: field?.label || humanize(col), options: list };
  }
  if (field?.type === "checkbox" || FALLBACK[col] === "bool") {
    return { type: "select", label: field?.label || humanize(col), options: [
      { value: "true", label: "Yes" }, { value: "false", label: "No" },
    ] };
  }
  if (Array.isArray(FALLBACK[col])) {
    return { type: "select", label: humanize(col), options: FALLBACK[col].map((o) => ({ value: o, label: o })) };
  }
  if (field?.type === "date") return { type: "date", label: field.label };
  return { type: "text", label: field?.label || humanize(col), placeholder: `Filter ${humanize(col)}…` };
}

export default function Filters({ filters, fields, boot, values, onChange, onClear }) {
  const resourceCols = (filters || []).filter((c) => RESOURCE_FILTERS[c]);

  const results = useQueries({
    queries: resourceCols.map((col) => {
      const cfg = RESOURCE_FILTERS[col];
      return {
        queryKey: ["filter-options", cfg.resource],
        queryFn: async () => (await api.get(`/${cfg.resource}?page_size=200`)).data.data,
        staleTime: 60000,
      };
    }),
  });
  const asyncOptions = {};
  resourceCols.forEach((col, i) => {
    const cfg = RESOURCE_FILTERS[col];
    asyncOptions[col] = (results[i]?.data || []).map((r) => ({ value: r.id, label: cfg.label(r) }));
  });

  if (!filters?.length) return null;
  const active = Object.entries(values).filter(([, v]) => v !== "" && v != null);

  return (
    <div className="filterbar">
      <div className="filterbar-row">
        <span className="filterbar-label">Filters</span>
        {filters.map((col) => {
          const ctl = controlFor(col, fields, boot, asyncOptions);
          const val = values[col] ?? "";
          if (ctl.type === "select") {
            return (
              <select key={col} className={`select filter-ctl ${val ? "on" : ""}`} value={val} onChange={(e) => onChange(col, e.target.value)}>
                <option value="">{ctl.label}: All</option>
                {ctl.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                {/* a value set from elsewhere (e.g. a target tile) that the list doesn't offer */}
                {val && !ctl.options.some((o) => String(o.value) === String(val)) && <option value={val}>{val}</option>}
              </select>
            );
          }
          if (ctl.type === "date") {
            return (
              <DateInput key={col} className={`filter-ctl ${val ? "on" : ""}`} value={val}
                placeholder={ctl.label} onChange={(v) => onChange(col, v)} />
            );
          }
          return (
            <input key={col} className={`input filter-ctl ${val ? "on" : ""}`} type="text"
              placeholder={ctl.placeholder || ctl.label} value={val} onChange={(e) => onChange(col, e.target.value)} />
          );
        })}
        {active.length > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={onClear}>Clear all</button>
        )}
      </div>
      {active.length > 0 && (
        <div className="chips">
          {active.map(([col, v]) => {
            const ctl = controlFor(col, fields, boot, asyncOptions);
            const label = ctl.options?.find((o) => String(o.value) === String(v))?.label ?? v;
            return (
              <span className="chip" key={col}>
                <b>{ctl.label}:</b> {String(label)}
                <button onClick={() => onChange(col, "")} aria-label="remove">×</button>
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
