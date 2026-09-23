/* One place that answers "what are the choices for this field?".

   A field can get its options from four places: a fixed list the backend
   serves (`enumKey`, so the dropdown and the server's validation are the same
   list), a scoped reference list from bootstrap (`optionsKey`), an inline
   array (`options`), or a function of the other answers so far
   (`dynamicOptions`). Forms and the filter bar both read this, so a filter
   chip always spells a value the same way the form that wrote it did. */

const normalise = (o) => (typeof o === "string" ? { value: o, label: o } : o);

export function enumList(boot, key) {
  const e = boot?.enums?.[key];
  return Array.isArray(e) ? e.map(normalise) : null;
}

// Options that don't depend on the other values in the form - the only kind
// the filter bar can use.
export function staticOptionsFor(field, boot) {
  if (!field) return null;
  if (field.enumKey) {
    const list = enumList(boot, field.enumKey);
    if (list) return list;
  }
  if (field.options) return field.options.map(normalise);
  if (field.optionsKey && boot?.options?.[field.optionsKey]) {
    return boot.options[field.optionsKey].map((o) => ({
      value: field.valueKey ? o[field.valueKey] ?? o.value : o.value,
      label: field.labelKey ? o[field.labelKey] ?? o.label : o.label,
    }));
  }
  return null;
}

// --- helpers the module catalog uses to derive answers from other answers ---

export const labById = (boot, id) =>
  (boot?.options?.labs || []).find((l) => String(l.value) === String(id));

export const schoolById = (boot, id) =>
  (boot?.options?.schools || []).find((s) => String(s.value) === String(id));

// Which job-role slot covers a class: 9-10 vs 11-12 (spec 1.3).
export const jobRoleForClass = (lab, classGrade) => {
  if (!lab) return null;
  return ["9", "10"].includes(String(classGrade))
    ? lab.job_role_9_10_id
    : lab.job_role_11_12_id;
};

// The distinct job roles a lab teaches at all.
export const labJobRoleIds = (lab) =>
  [...new Set([lab?.job_role_9_10_id, lab?.job_role_11_12_id].filter(Boolean))];

// Sections configured on the lab for one class grade (spec 1.3).
export const labSections = (lab, classGrade) =>
  (lab?.sections?.[String(classGrade)] || []).filter(Boolean);

export const splitList = (v) =>
  typeof v === "string" ? v.split(",").map((s) => s.trim()).filter(Boolean) : Array.isArray(v) ? v : [];

export const joinList = (arr) => (arr || []).join(",");
