/* Single place that turns "what we already know about this user" (the
   backend's my_scope.profile) into UI decisions: which filters are redundant
   to ask for, and which table columns repeat a value that's already fixed.

   Nothing here is a security boundary - the backend's apply_scope already
   restricts every row regardless of what the frontend sends or shows. This is
   purely about not asking/showing what we already know (spec: tailored UX). */

// Filter column -> the profile key that makes it redundant. When the user's
// profile already pins this value (e.g. a Trainer has exactly one school),
// showing a "School" filter is a no-op - the list is already scoped to it.
// academic_year is deliberately NOT here: knowing the *current* year isn't
// the same as restricting to it - users legitimately browse past years, so
// that filter stays visible (just defaulted to the current year elsewhere).
const FILTER_PROFILE_ALIAS = {
  school_id: "school_id",
  linked_school_id: "school_id",
  lab_id: "lab_id",
  district_id: "district_id",
  job_role_id: "job_role_id",
  trainer_id: "trainer_id",
  class_grade: "class_grade",
  section: "section",
};

export function visibleFilters(filterCols, profile) {
  if (!profile) return filterCols;
  return filterCols.filter((col) => {
    const key = FILTER_PROFILE_ALIAS[col];
    const known = key && profile[key] != null && profile[key] !== "";
    return !known;
  });
}

// Table columns that repeat the same value down every row once the user's
// scope has narrowed the list to a single possible value (e.g. "School"
// column on the Attendance table, when this trainer only has one school),
// plus any column a module marks as irrelevant to this role.
export function visibleColumns(columns, options, profile, role) {
  const singleton = (arr) => (arr?.length ?? 0) <= 1;
  const hide = {
    school_name: singleton(options?.schools),
    lab_name: !!profile?.lab_id,
    trainer_name: !!profile?.trainer_id,
  };
  return columns
    .filter((c) => !hide[c.key] && (!c.hideFor || !(role && c.hideFor.includes(role))))
    .filter((c) => !c.onlyFor || c.onlyFor.includes(role))
    .map((c) => (role && c.forRole?.[role] ? { ...c, ...c.forRole[role] } : c));
}

// Compact "you are already scoped to this" chips for the persistent header
// indicator - the information that redundant filters/columns would have
// shown, surfaced once instead of repeated on every page/row.
export function scopeChips(profile, options) {
  if (!profile) return [];
  const find = (list, id) => (list || []).find((o) => String(o.value) === String(id))?.label;
  const chips = [];

  const school = find(options?.schools, profile.school_id);
  if (school) chips.push({ icon: "🏫", text: school });

  const lab = find(options?.labs, profile.lab_id);
  if (lab) chips.push({ icon: "🧪", text: lab });

  const jobRole = find(options?.job_roles, profile.job_role_id);
  if (jobRole) chips.push({ icon: "💼", text: jobRole });

  if (profile.class_grade) {
    chips.push({ icon: "🎓", text: `Class ${profile.class_grade}${profile.section ? "-" + profile.section : ""}` });
  }
  return chips;
}
