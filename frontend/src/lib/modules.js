/* Config-driven module catalog. Every screen (list columns + create/edit form)
   is described here, mirroring the backend registry. Adding a module = adding
   an entry, no new component.

   A field says where its answer comes from:
     optionsKey     a scoped reference list from /meta/bootstrap
     enumKey        a fixed list the backend also validates against (enums.py)
     dynamicOptions computed from the answers so far
     derive         the answer itself, when it is already implied - the field
                    is then shown as filled in rather than asked for
     autoFor        roles whose own profile already answers it
     onlyFor/hideFor  roles the field exists / does not exist for
     group          which titled section of the form it belongs in
*/
import {
  labById, jobRoleForClass, labJobRoleIds, labSections,
} from "./fieldOptions";

// shared option-key shortcuts
const SECTOR = { optionsKey: "sectors" };
const JOBROLE = { optionsKey: "job_roles" };
const SCHOOL = { optionsKey: "schools" };
const LAB = { optionsKey: "labs" };
const DISTRICT = { optionsKey: "districts" };
const AY = { optionsKey: "academic_years", labelKey: "label" };
const SOCIAL = { optionsKey: "social_categories" };

const YESNO = [
  { value: "true", label: "Yes" },
  { value: "false", label: "No" },
];

const today = () => new Date().toISOString().slice(0, 10);

// --- conditional visibility -------------------------------------------
const WORKING = (v) => !v.day_type || v.day_type === "Working day";
// one branch of the daily-attendance activity list (spec 3.11 a-o)
const ACT = (...names) => (v) => WORKING(v) && names.includes(v.activity_type);
const TEACHING = ACT("Teaching Vocational Education");

// --- cascading reference selects ---------------------------------------
// Picking the parent narrows the child list. Lab list filtered to the chosen
// school; job-role slots filtered to the chosen sector + the correct band.
const LAB_BY_SCHOOL = { optionsKey: "labs", async: true, dependsOn: { field: "school_id", param: "school_id" } };
const JOBROLE_9_10 = { optionsKey: "job_roles", async: true, dependsOn: { field: "sector_id", param: "sector_id" }, staticParams: { class_band: "9-10" } };
const JOBROLE_11_12 = { optionsKey: "job_roles", async: true, dependsOn: { field: "sector_id", param: "sector_id" }, staticParams: { class_band: "11-12" } };

// Classes this lab actually runs: a lab with only a 9-10 job-role slot never
// teaches Class 11. Narrowed further to a trainer's own band (the server
// enforces the same rule; this keeps the dropdown honest).
const CLASS_BY_LAB = (values, c) => {
  const lab = labById(c.boot, values.lab_id);
  let grades = ["9", "10", "11", "12"];
  if (lab) {
    const fromLab = [];
    if (lab.job_role_9_10_id) fromLab.push("9", "10");
    if (lab.job_role_11_12_id) fromLab.push("11", "12");
    if (fromLab.length) grades = fromLab;
  }
  const mine = c.myScope?.class_grades_by_job_role;
  if (mine && Object.keys(mine).length) {
    const allowed = new Set(Object.values(mine).flat());
    if (allowed.size) grades = grades.filter((g) => allowed.has(g));
  }
  return grades.map((g) => ({ value: g, label: `Class ${g}` }));
};

// Registration only ever happens in Class 9 or Class 11 (spec 2.6) - but a
// student already in Class 10 or 12 got there by being promoted, so editing
// one must still offer their real class.
const REGISTRATION_CLASS = (values, c) => {
  const all = CLASS_BY_LAB(values, c);
  return c.isNew ? all.filter((o) => ["9", "11"].includes(o.value)) : all;
};

// The job role is not a free choice: a lab holds one role for 9-10 and one
// for 11-12 (spec 1.3), so lab + class already decides it.
const DERIVE_JOB_ROLE = (classField) => (values, c) => {
  const lab = labById(c.boot, values.lab_id);
  if (!lab) return undefined;
  const cls = values[classField];
  if (cls) return jobRoleForClass(lab, cls) || undefined;
  const ids = labJobRoleIds(lab);
  return ids.length === 1 ? ids[0] : undefined;   // same role in both slots
};
const JOB_ROLE_NOTE = "Taken from this lab's job-role slot for that class";

// When the lab does teach two different roles and no class is chosen yet, at
// least keep the list to the two this lab offers.
const JOBROLE_BY_LAB = (values, c) => {
  const all = c.boot?.options?.job_roles || [];
  const lab = labById(c.boot, values.lab_id);
  if (!lab) return all;
  const ids = labJobRoleIds(lab).map(String);
  const narrowed = all.filter((o) => ids.includes(String(o.value)));
  return narrowed.length ? narrowed : all;
};

// Sections come from the lab's own per-class configuration (spec 1.3), so a
// trainer picks "B" rather than typing it and creating a second "b".
const SECTIONS_FOR = (classField) => (values, c) => {
  const configured = labSections(labById(c.boot, values.lab_id), values[classField]);
  // Before a lab has been set up there is nothing to offer, and an empty
  // dropdown is a dead end - fall back to plain letters in that case only.
  const list = configured.length ? configured : ["A", "B", "C", "D"];
  return list.map((s) => ({ value: s, label: s }));
};

const SECTION_HINT = "Sections come from this lab's setup. Add more in Master Data → Labs.";

// Curriculum cascade: Job role (+ Employability/Vocational) -> Module -> Unit
// -> Session. `module_type` is a filter on the module list, not a stored
// column - it is how the spec asks the question.
const MODULE_TYPE_F = (showIf, group) => ({
  name: "module_type", label: "Module covered", type: "select", enumKey: "module_types",
  showIf, group, hint: "Narrows the module list below.",
});
const MODULE_F = (showIf, group) => ({
  name: "module_id", label: "Module", type: "select", optionsKey: "modules", async: true,
  dependsOn: [
    { field: "job_role_id", param: "job_role_id" },
    { field: "module_type", param: "module_type" },
  ],
  dependsLabel: "job role", showIf, group,
});
const UNIT_F = (showIf, group) => ({
  name: "unit_id", label: "Unit covered", type: "select", optionsKey: "units", async: true,
  dependsOn: { field: "module_id", param: "module_id" }, showIf, group,
});
const SESSION_F = (showIf, group) => ({
  name: "session_id", label: "Session covered", type: "select", optionsKey: "sessions", async: true,
  dependsOn: { field: "unit_id", param: "unit_id" }, showIf, group,
});
// Visits and lectures cover several units/sessions at once; those columns hold
// the chosen names so a report reads without a join.
const UNITS_MULTI = (name, group) => ({
  name, label: "Units covered", type: "multiselect", optionsKey: "units", async: true,
  valueKey: "name", dependsOn: { field: "module_id", param: "module_id" }, group,
  emptyHint: "Pick a module first.",
});
const SESSIONS_MULTI = (name, group) => ({
  name, label: "Sessions covered", type: "multiselect", optionsKey: "sessions", async: true,
  valueKey: "name", dependsOn: { field: "module_id", param: "module_id" }, group,
  emptyHint: "Pick a module first.",
});

// Reference lists that are stored by name rather than by id (the columns are
// plain text), so the dropdown offers the org's real states/districts.
const NAME_OPTS = (key) => (values, c) =>
  (c.boot?.options?.[key] || []).map((o) => ({ value: o.label, label: o.label }));

// Once a student is chosen, the record already knows their school, lab, class,
// section, job role and year - so the form stops asking. `rows` holds the
// student list the select above has already fetched.
const FROM_STUDENT = (attr, from = "student_id") => (values, c) => {
  const row = (c.rows?.[from] || []).find((r) => String(r.id) === String(values[from]));
  const v = row?.[attr];
  return v === null || v === undefined || v === "" ? undefined : String(v);
};
const STUDENT_NOTE = "From the student's record";

export const MODULES = {
  // ---------------- MASTER DATA ----------------
  organisations: {
    label: "Organisations", singular: "Organisation", icon: "🏢", group: "Administration",
    roles: ["SA"],
    columns: [
      { key: "name", label: "Name" },
      { key: "org_code", label: "Code" },
      { key: "primary_contact_email", label: "Contact" },
      { key: "status", label: "Status", badge: true },
    ],
    fields: [
      { name: "name", label: "Organisation name", required: true, group: "Identity" },
      { name: "legal_name", label: "Legal name", group: "Identity" },
      { name: "org_code", label: "Org code", required: true, group: "Identity" },
      { name: "logo_url", label: "Logo", type: "file", accept: "image/*", group: "Identity" },
      { name: "primary_contact_name", label: "Contact name", group: "Contact" },
      { name: "primary_contact_email", label: "Contact email", type: "email", group: "Contact" },
      { name: "primary_contact_phone", label: "Contact phone", type: "tel", group: "Contact" },
      { name: "registered_address", label: "Registered address", type: "textarea", group: "Contact" },
      { name: "affiliation_cert_number", label: "Affiliation cert #", group: "Affiliation" },
      { name: "affiliation_valid_till", label: "Affiliation valid till", type: "date", group: "Affiliation" },
    ],
  },
  states: {
    label: "States", singular: "State", icon: "🗺️", group: "Master Data",
    columns: [{ key: "name", label: "Name" }, { key: "code", label: "Code" }],
    fields: [
      { name: "name", label: "State name", required: true },
      { name: "code", label: "Code" },
    ],
  },
  districts: {
    label: "Districts", singular: "District", icon: "📍", group: "Master Data",
    columns: [{ key: "name", label: "Name" }, { key: "code", label: "Code" }],
    fields: [
      { name: "name", label: "District name", required: true },
      { name: "state_id", label: "State", type: "select", optionsKey: "states" },
      { name: "code", label: "Code" },
    ],
  },
  schools: {
    label: "Schools", singular: "School", icon: "🏫", group: "Master Data",
    columns: [
      { key: "name", label: "School" },
      { key: "udise_code", label: "UDISE" },
      { key: "district_name", label: "District" },
      { key: "block", label: "Block" },
      { key: "status", label: "Status", badge: true },
    ],
    formHint: "Labs are attached to a school from Master Data → Labs.",
    fields: [
      { name: "name", label: "School name", required: true, group: "School" },
      { name: "udise_code", label: "UDISE code", required: true, group: "School" },
      { name: "district_id", label: "District", type: "select", ...DISTRICT, autoFor: ["DM"], group: "School" },
      { name: "block", label: "Block", group: "School" },
      {
        name: "principal_id", label: "Headmaster / Principal", type: "select",
        optionsKey: "principals", group: "School",
        hint: "Add them in Master Data → Principals first if they are not listed.",
      },
      { name: "address", label: "Full address", type: "textarea", group: "Contact" },
      { name: "email", label: "Email", type: "email", group: "Contact" },
      { name: "phone", label: "Phone", type: "tel", group: "Contact" },
    ],
  },
  principals: {
    label: "Principals", singular: "Principal", icon: "🎓", group: "Master Data",
    columns: [
      { key: "full_name", label: "Name" },
      { key: "email", label: "Email" },
      { key: "mobile", label: "Mobile" },
      { key: "status", label: "Status", badge: true },
    ],
    fields: [
      { name: "full_name", label: "Full name", required: true, group: "Person" },
      { name: "gender", label: "Gender", type: "select", enumKey: "genders", group: "Person" },
      { name: "mobile", label: "Mobile", type: "tel", group: "Person" },
      { name: "email", label: "Email", type: "email", group: "Person" },
      { name: "linked_school_id", label: "School", type: "select", ...SCHOOL, group: "Posting" },
      { name: "years_in_school", label: "Years in school", type: "number", min: 0, group: "Posting" },
      { name: "date_of_joining", label: "Date of joining", type: "date", group: "Posting" },
      { name: "date_of_resignation", label: "Date of resignation", type: "date", group: "Posting", hint: "Leave blank while they are still in post." },
    ],
  },
  labs: {
    label: "Labs", singular: "Lab", icon: "🧪", group: "Master Data",
    columns: [
      { key: "name", label: "Lab" },
      { key: "school_name", label: "School" },
      { key: "curriculum_level", label: "Level" },
      { key: "status", label: "Status", badge: true },
    ],
    formHint: "What you set here drives the job-role and section dropdowns everywhere else.",
    fields: [
      { name: "name", label: "Lab name", required: true, placeholder: "e.g. Computer Lab 1", group: "Lab" },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, required: true, group: "Lab" },
      { name: "sector_id", label: "Trade / Sector", type: "select", ...SECTOR, group: "Lab", hint: "The industry taught here, e.g. IT/ITeS." },
      { name: "academic_year_of_setup", label: "AY of setup", type: "select", ...AY, valueKey: "label", group: "Lab" },
      { name: "job_role_9_10_id", label: "Job Role (Class 9-10)", type: "select", ...JOBROLE_9_10, group: "Job roles", hint: "Entry-level title, e.g. Data Entry Operator. Pick a sector first." },
      { name: "job_role_11_12_id", label: "Job Role (Class 11-12)", type: "select", ...JOBROLE_11_12, group: "Job roles", hint: "Advanced title, e.g. Junior Software Developer. Use the same role in both slots if the lab runs one role across all four years." },
      { name: "curriculum_level", label: "Curriculum levels", placeholder: "e.g. 1-4", group: "Job roles", hint: "Level 1 in Class 9 through Level 4 in Class 12." },
      { name: "sections_9", label: "Class 9 sections", type: "multiselect", allowCustom: true, options: ["A", "B", "C", "D"], customPlaceholder: "Another section…", group: "Sections", emptyHint: "Add the sections this class runs." },
      { name: "sections_10", label: "Class 10 sections", type: "multiselect", allowCustom: true, options: ["A", "B", "C", "D"], customPlaceholder: "Another section…", group: "Sections" },
      { name: "sections_11", label: "Class 11 sections", type: "multiselect", allowCustom: true, options: ["A", "B", "C", "D"], customPlaceholder: "Another section…", group: "Sections" },
      { name: "sections_12", label: "Class 12 sections", type: "multiselect", allowCustom: true, options: ["A", "B", "C", "D"], customPlaceholder: "Another section…", group: "Sections" },
      { name: "sections_per_class", label: "Sections per class (total)", type: "number", min: 0, group: "Sections", hint: "Optional summary count kept for older reports." },
    ],
  },
  trainers: {
    label: "Trainers", singular: "Vocational Trainer", icon: "👨‍🏫", group: "People & Students",
    columns: [
      { key: "full_name", label: "Name" },
      { key: "school_name", label: "School" },
      { key: "email", label: "Email" },
      { key: "trainer_status", label: "Status", badge: true },
    ],
    formHint: "One trainer per job role in a lab — the 9-10 role and the 11-12 role each get their own.",
    fields: [
      { name: "full_name", label: "Full name", required: true, group: "Person" },
      { name: "gender", label: "Gender", type: "select", enumKey: "genders", group: "Person" },
      { name: "email", label: "Email", type: "email", group: "Person" },
      { name: "phone", label: "Phone", type: "tel", group: "Person" },
      { name: "qualification", label: "Qualification", group: "Person" },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, group: "Posting" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, group: "Posting" },
      { name: "job_role_id", label: "Job role", type: "select", dynamicOptions: JOBROLE_BY_LAB, group: "Posting", hint: "Only the roles this lab teaches." },
      { name: "date_of_joining", label: "Date of joining", type: "date", group: "Posting" },
      { name: "date_of_exit", label: "Date of exit", type: "date", group: "Posting" },
      { name: "trainer_status", label: "Status", type: "select", enumKey: "trainer_status", defaultValue: "active", group: "Posting" },
    ],
  },
  "academic-years": {
    label: "Academic Years", singular: "Academic Year", icon: "📅", group: "Master Data",
    columns: [
      { key: "label", label: "Label" },
      { key: "start_date", label: "Start" },
      { key: "end_date", label: "End" },
      { key: "is_current", label: "Current", badge: true },
    ],
    fields: [
      { name: "label", label: "Label", required: true, placeholder: "2025-26" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "is_current", label: "Is current?", type: "checkbox" },
    ],
  },
  sectors: {
    label: "Sectors / Trades", singular: "Sector", icon: "🏭", group: "Master Data",
    columns: [{ key: "name", label: "Sector" }, { key: "code", label: "Code" }],
    fields: [
      { name: "name", label: "Sector name", required: true, placeholder: "e.g. IT/ITeS" },
      { name: "code", label: "Code" },
    ],
  },
  "job-roles": {
    label: "Job Roles", singular: "Job Role", icon: "💼", group: "Master Data",
    columns: [
      { key: "name", label: "Job Role" },
      { key: "sector_name", label: "Sector" },
      { key: "qp_code", label: "QP Code" },
      { key: "nsqf_level", label: "NSQF" },
      { key: "class_band", label: "Band" },
    ],
    fields: [
      { name: "name", label: "Job role name", required: true },
      { name: "sector_id", label: "Sector", type: "select", ...SECTOR, required: true },
      { name: "qp_code", label: "QP Code" },
      { name: "nsqf_level", label: "NSQF level (1-4)", type: "number", min: 1, max: 4 },
      { name: "class_band", label: "Class band", type: "select", options: ["9-10", "11-12"], hint: "9-10 carries Levels 1-2; 11-12 carries Levels 3-4." },
    ],
  },
  "social-categories": {
    label: "Social Categories", singular: "Social Category", icon: "🏷️", group: "Master Data",
    columns: [{ key: "name", label: "Category" }],
    fields: [{ name: "name", label: "Category name", required: true }],
  },
  modules: {
    label: "Curriculum Modules", singular: "Module", icon: "📚", group: "Master Data",
    columns: [
      { key: "name", label: "Module" },
      { key: "module_type", label: "Type" },
      { key: "nsqf_level", label: "NSQF" },
      { key: "sort_order", label: "Order" },
    ],
    formHint: "Sector → Job Role → Level → Module → Unit → Session. Curriculum and Syllabus are two views of this one tree.",
    fields: [
      { name: "name", label: "Module name", required: true },
      { name: "job_role_id", label: "Job role", type: "select", ...JOBROLE, required: true },
      { name: "nsqf_level", label: "NSQF level (grade)", type: "number", min: 1, max: 4, hint: "Level 1 ≈ Class 9 … Level 4 ≈ Class 12." },
      { name: "module_type", label: "Module type", type: "select", enumKey: "module_types" },
      { name: "sort_order", label: "Sort order", type: "number" },
    ],
  },
  units: {
    label: "Curriculum Units", singular: "Unit", icon: "📖", group: "Master Data",
    columns: [{ key: "name", label: "Unit" }, { key: "sort_order", label: "Order" }],
    fields: [
      { name: "name", label: "Unit name", required: true },
      { name: "module_id", label: "Module", type: "select", optionsKey: "modules", async: true, required: true },
      { name: "sort_order", label: "Sort order", type: "number" },
    ],
  },
  sessions: {
    label: "Curriculum Sessions", singular: "Session", icon: "📝", group: "Master Data",
    columns: [{ key: "name", label: "Session" }, { key: "sort_order", label: "Order" }],
    fields: [
      { name: "name", label: "Session name", required: true },
      { name: "unit_id", label: "Unit", type: "select", optionsKey: "units", async: true, required: true },
      { name: "sort_order", label: "Sort order", type: "number" },
    ],
  },

  // ---------------- STUDENTS ----------------
  students: {
    label: "Students", singular: "Student", icon: "🧑‍🎓", group: "People & Students",
    columns: [
      { key: "full_name", label: "Name" },
      { key: "roll_number", label: "Roll" },
      { key: "class_grade", label: "Class" },
      { key: "section", label: "Sec" },
      { key: "school_name", label: "School" },
      { key: "verification_status", label: "Verification", badge: true },
    ],
    formHint: "Students are registered in Class 9 and Class 11; Class 10 and 12 come from verification.",
    fields: [
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["VT", "PR"], required: true, group: "Placement" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT"], group: "Placement" },
      {
        name: "class_grade", label: "Class", type: "select", required: true,
        dynamicOptions: REGISTRATION_CLASS, group: "Placement",
        hint: "Registration happens in Class 9 and Class 11.",
      },
      {
        name: "section", label: "Section", type: "select", allowCustom: false,
        dynamicOptions: SECTIONS_FOR("class_grade"),
        dependsOn: { field: "class_grade" }, group: "Placement", hint: SECTION_HINT,
      },
      {
        name: "job_role_id", label: "Job role", type: "select",
        derive: DERIVE_JOB_ROLE("class_grade"), deriveNote: JOB_ROLE_NOTE,
        dynamicOptions: JOBROLE_BY_LAB, group: "Placement",
      },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Placement" },
      { name: "roll_number", label: "Roll number", group: "Placement" },
      { name: "stream", label: "Stream", group: "Placement", hint: "e.g. Science, Commerce, Arts (Class 11-12)." },

      { name: "first_name", label: "First name", required: true, group: "Student" },
      { name: "middle_name", label: "Middle name", group: "Student" },
      { name: "last_name", label: "Last name", group: "Student" },
      { name: "gender", label: "Gender", type: "select", enumKey: "genders", group: "Student" },
      { name: "dob", label: "Date of birth", type: "date", group: "Student" },
      { name: "email", label: "Email ID", type: "email", group: "Student" },
      { name: "photo_url", label: "Student photo (optional)", type: "file", accept: "image/*", group: "Student" },

      { name: "father_name", label: "Father's name", group: "Family & contact" },
      { name: "mother_name", label: "Mother's name", group: "Family & contact" },
      { name: "guardian_name", label: "Guardian's name", group: "Family & contact" },
      { name: "mobile_primary", label: "First mobile number", type: "tel", group: "Family & contact" },
      { name: "mobile_secondary", label: "Second mobile number", type: "tel", group: "Family & contact" },
      { name: "whatsapp_number", label: "WhatsApp number", type: "tel", group: "Family & contact" },

      { name: "social_category_id", label: "Social category", type: "select", ...SOCIAL, group: "Category & enrolment" },
      { name: "cwsn", label: "CWSN (Child With Special Needs)?", type: "checkbox", group: "Category & enrolment" },
      { name: "date_of_enrolment", label: "Date of enrolment", type: "date", defaultValue: today, group: "Category & enrolment" },
      {
        name: "had_vocational_9_10", label: "Had a vocational stream in Class 9/10?",
        type: "checkbox", showIf: (v) => String(v.class_grade) === "11",
        group: "Category & enrolment",
      },
      {
        name: "continuing_same_trade", label: "Continuing the same trade?",
        type: "checkbox",
        showIf: (v) => String(v.class_grade) === "11" && !!v.had_vocational_9_10,
        group: "Category & enrolment",
      },

      { name: "verification_status", label: "Verification status", type: "select", enumKey: "verification_status", defaultValue: "pending", group: "Verification" },
      { name: "verification_remarks", label: "Verification remarks", type: "textarea", group: "Verification" },
    ],
    rowActions: [{ action: "verify", roles: ["VT", "DM", "OA", "SA"] }],
  },
  assessments: {
    label: "Assessments", singular: "Assessment", icon: "🎯", group: "People & Students",
    columns: [
      { key: "student_name", label: "Student" },
      { key: "name", label: "Assessment" },
      { key: "assessment_type", label: "Type" },
      { key: "marks_obtained", label: "Marks" },
      { key: "result", label: "Result", badge: true },
    ],
    fields: [
      { name: "student_id", label: "Student", type: "select", optionsKey: "students", async: true, required: true, autoFor: ["ST"], group: "Who" },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", derive: FROM_STUDENT("academic_year"), deriveNote: STUDENT_NOTE, autoFor: ["VT", "PR", "DM", "ST"], group: "Who" },
      { name: "class_grade", label: "Class", type: "select", enumKey: "class_grades", derive: FROM_STUDENT("class_grade"), deriveNote: STUDENT_NOTE, group: "Who" },
      { name: "job_role_id", label: "Job role", type: "select", ...JOBROLE, derive: FROM_STUDENT("job_role_id"), deriveNote: STUDENT_NOTE, autoFor: ["VT", "ST"], group: "Who" },
      { name: "nsqf_level", label: "NSQF level", type: "number", min: 1, max: 4, group: "Who" },
      { name: "assessment_type", label: "Type", type: "select", enumKey: "assessment_types", group: "Result" },
      { name: "name", label: "Assessment name", group: "Result" },
      { name: "date", label: "Date", type: "date", defaultValue: today, group: "Result" },
      { name: "max_marks", label: "Max marks", type: "number", min: 0, group: "Result" },
      { name: "marks_obtained", label: "Marks obtained", type: "number", min: 0, group: "Result" },
      { name: "result", label: "Result", type: "select", options: ["pass", "fail"], group: "Result" },
      { name: "level_certification_status", label: "Level certification", type: "select", options: ["L1", "L2", "L3", "L4"], group: "Certification" },
      { name: "certificate_number", label: "Certificate number", group: "Certification" },
      { name: "evidence_url", label: "Evidence", type: "file", group: "Certification" },
      { name: "remarks", label: "Remarks", type: "textarea", group: "Certification" },
    ],
  },

  // ---------------- DAILY OPERATIONS ----------------
  attendance: {
    label: "Daily Attendance", singular: "Attendance", icon: "🗓️", group: "Daily Operations",
    columns: [
      { key: "date", label: "Date" },
      { key: "day_type", label: "Day" },
      { key: "activity_type", label: "Activity" },
      { key: "class_taught", label: "Class" },
      { key: "school_name", label: "School" },
      { key: "endorsement_status", label: "Endorsement", badge: true },
    ],
    formHint: "Pick the activity and only that activity's questions appear.",
    fields: [
      // --- the day ---
      { name: "date", label: "Date", type: "date", required: true, defaultValue: today, group: "The day" },
      { name: "day_type", label: "Day type", type: "select", enumKey: "day_types", defaultValue: "Working day", required: true, group: "The day" },
      { name: "leave_reason", label: "Reason for leave", required: true, showIf: (v) => v.day_type === "On leave", group: "The day", wide: true },

      // --- who and where (a trainer's own posting answers all of this) ---
      { name: "trainer_id", label: "Trainer", type: "select", optionsKey: "trainers", autoFor: ["VT"], group: "Who & where" },
      // School and lab are asked for on every day type, leave included: they
      // are what puts the record inside this trainer's scope.
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["VT", "PR"], group: "Who & where" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT"], group: "Who & where" },
      {
        name: "job_role_id", label: "Job role", type: "select",
        autoFor: ["VT"], derive: DERIVE_JOB_ROLE("class_taught"), deriveNote: JOB_ROLE_NOTE,
        dynamicOptions: JOBROLE_BY_LAB, group: "Who & where",
      },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Who & where" },

      { name: "activity_type", label: "Activity type", type: "select", enumKey: "activity_types", required: true, showIf: WORKING, group: "Activity" },

      // --- a. Teaching Vocational Education ---
      { name: "class_taught", label: "Class taught", type: "select", required: true, showIf: TEACHING, dynamicOptions: CLASS_BY_LAB, group: "Class taught" },
      {
        name: "section_taught", label: "Section(s) taught", type: "multiselect", showIf: TEACHING,
        dynamicOptions: SECTIONS_FOR("class_taught"), dependsOn: { field: "class_taught" },
        allowCustom: true, customPlaceholder: "Another section…", hint: SECTION_HINT, group: "Class taught",
      },
      { name: "theory_or_practical", label: "Theory / Practical", type: "select", enumKey: "theory_practical", showIf: TEACHING, group: "Class taught" },
      { name: "class_type", label: "Class type", type: "select", enumKey: "class_types", showIf: TEACHING, group: "Class taught" },
      { name: "duration_mins", label: "Class duration (minutes)", type: "number", min: 0, showIf: TEACHING, group: "Class taught" },
      MODULE_TYPE_F(TEACHING, "Curriculum covered"),
      MODULE_F(TEACHING, "Curriculum covered"),
      UNIT_F(TEACHING, "Curriculum covered"),
      SESSION_F(TEACHING, "Curriculum covered"),
      { name: "class_picture_url", label: "Class picture", type: "file", accept: "image/*", showIf: TEACHING, group: "Evidence" },
      { name: "lesson_plan_picture_url", label: "Lesson-plan picture", type: "file", accept: "image/*", showIf: TEACHING, group: "Evidence" },
      { name: "student_marks", label: "Student attendance", type: "studentmarks", showIf: TEACHING, group: "Student attendance", classField: "class_taught", sectionField: "section_taught" },

      // --- b. Visit to Industry ---
      { name: "industry_name", label: "Industry name", showIf: ACT("Visit to Industry"), group: "Industry visit" },
      { name: "industry_contact_person", label: "Contact person name", showIf: ACT("Visit to Industry"), group: "Industry visit" },
      { name: "industry_contact_phone", label: "Contact person phone", type: "tel", showIf: ACT("Visit to Industry"), group: "Industry visit" },

      // --- c. Visit to Educational Institution ---
      { name: "institute_name", label: "Institute name", showIf: ACT("Visit to Educational Institution"), group: "Institution visit" },
      { name: "institute_contact_person", label: "Contact person name", showIf: ACT("Visit to Educational Institution"), group: "Institution visit" },
      { name: "institute_contact_phone", label: "Contact person phone", type: "tel", showIf: ACT("Visit to Educational Institution"), group: "Institution visit" },

      // --- d. On-Job Training Coordination ---
      { name: "ojt_activity_type", label: "Coordination activity", type: "select", enumKey: "ojt_coordination_activities", showIf: ACT("On-Job Training Coordination"), group: "OJT coordination" },

      // --- e. Parent Teachers Meeting / f. Community Home Visit ---
      { name: "parents_count", label: "Parents count", type: "number", min: 0, showIf: ACT("Parent Teachers Meeting", "Community Home Visit"), group: "Parents" },

      // --- h. Teaching Non-Vocational Subject ---
      { name: "other_class_details", label: "Other class details", type: "textarea", showIf: ACT("Teaching Non-Vocational Subject"), group: "Non-vocational class" },
      { name: "other_class_duration_mins", label: "Other class duration (minutes)", type: "number", min: 0, showIf: ACT("Teaching Non-Vocational Subject"), group: "Non-vocational class" },

      // --- j. Assignment from Vocational Department ---
      { name: "assignment_number", label: "Assignment number", showIf: ACT("Assignment from Vocational Department"), group: "Assignment" },
      { name: "assignment_photo_url", label: "Assignment photo", type: "file", accept: "image/*", showIf: ACT("Assignment from Vocational Department"), group: "Assignment" },

      // --- l. Assessor in Other School for Exam ---
      { name: "assessor_school_name", label: "School name", showIf: ACT("Assessor in Other School"), group: "Assessor duty" },
      { name: "assessor_udise", label: "UDISE code", showIf: ACT("Assessor in Other School"), group: "Assessor duty" },
      { name: "assessor_class", label: "Class", type: "select", enumKey: "class_grades", showIf: ACT("Assessor in Other School"), group: "Assessor duty" },
      { name: "boys_present", label: "Boys present", type: "number", min: 0, showIf: ACT("Assessor in Other School"), group: "Assessor duty" },
      { name: "girls_present", label: "Girls present", type: "number", min: 0, showIf: ACT("Assessor in Other School"), group: "Assessor duty" },

      // --- m. Training of Teacher/Trainer ---
      { name: "training_type", label: "Training programme", type: "select", enumKey: "training_types", showIf: ACT("Training of Teacher/Trainer"), group: "Training" },

      // --- o. Guidance & Counselling ---
      { name: "students_count", label: "Students count", type: "number", min: 0, showIf: ACT("Guidance & Counselling"), group: "Guidance & counselling" },

      // --- g, i, k, n and the narrative every other branch asks for ---
      {
        name: "details", label: "Details", type: "textarea", rows: 4, group: "Details",
        hint: "Describe the activity carried out.",
        showIf: (v) => WORKING(v) && !!v.activity_type && v.activity_type !== "Teaching Vocational Education",
      },
    ],
    rowActions: [{ action: "endorse", roles: ["PR", "OA", "SA"] }],
  },
  issues: {
    label: "VT Issues", singular: "Issue", icon: "⚠️", group: "Daily Operations",
    columns: [
      { key: "reporting_date", label: "Date" },
      { key: "main_issue", label: "Main issue" },
      { key: "sub_issue", label: "Sub issue" },
      { key: "students_affected", label: "Affected" },
      { key: "workflow_status", label: "Status", badge: true },
    ],
    fields: [
      { name: "trainer_id", label: "Trainer", type: "select", optionsKey: "trainers", autoFor: ["VT"], group: "Who & where" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB, autoFor: ["VT"], group: "Who & where" },
      {
        name: "job_role_id", label: "Job role", type: "select", autoFor: ["VT"],
        derive: DERIVE_JOB_ROLE("__none"), deriveNote: "Taken from your lab",
        dynamicOptions: JOBROLE_BY_LAB, group: "Who & where",
      },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Who & where" },
      { name: "reporting_date", label: "Reporting date", type: "date", required: true, defaultValue: today, group: "Who & where" },

      { name: "main_issue", label: "Main issue", type: "select", enumKey: "issue_main", required: true, group: "The issue" },
      {
        name: "sub_issue", label: "Sub issue", type: "select", required: true,
        dependsOn: { field: "main_issue" }, dependsLabel: "main issue",
        disabledWhen: (v) => !v.main_issue,
        dynamicOptions: (v, c) => c.enums?.issue_sub?.[v.main_issue] || [],
        group: "The issue",
      },
      { name: "students_affected", label: "Students affected", type: "select", enumKey: "students_affected", group: "The issue" },
      {
        name: "number_affected", label: "Number of students affected", type: "number", min: 1,
        required: true, showIf: (v) => v.students_affected === "some", group: "The issue",
      },
      { name: "details", label: "Issue details", type: "textarea", rows: 4, required: true, group: "The issue" },
    ],
    rowActions: [{ action: "transition", roles: ["DM", "OA", "SA"] }],
  },
  "field-visits": {
    label: "Field / Industry Visits", singular: "Field Visit", icon: "🚌", group: "Daily Operations",
    columns: [
      { key: "reporting_date", label: "Date" },
      { key: "organisation_name", label: "Organisation" },
      { key: "school_name", label: "School" },
      { key: "class_grade", label: "Class" },
      { key: "sections", label: "Sections" },
    ],
    fields: [
      { name: "reporting_date", label: "Reporting date", type: "date", required: true, defaultValue: today, group: "Who & where" },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["VT", "PR"], group: "Who & where" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT"], group: "Who & where" },
      { name: "class_grade", label: "Class", type: "select", dynamicOptions: CLASS_BY_LAB, required: true, group: "Who & where" },
      {
        name: "sections", label: "Section(s)", type: "multiselect",
        dynamicOptions: SECTIONS_FOR("class_grade"), dependsOn: { field: "class_grade" },
        allowCustom: true, customPlaceholder: "Another section…", hint: SECTION_HINT, group: "Who & where",
      },
      {
        name: "job_role_id", label: "Job role", type: "select",
        derive: DERIVE_JOB_ROLE("class_grade"), deriveNote: JOB_ROLE_NOTE,
        dynamicOptions: JOBROLE_BY_LAB, group: "Who & where",
      },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Who & where" },

      { name: "purpose", label: "Purpose of the visit", type: "textarea", group: "The visit" },
      { name: "activities", label: "Field visit activities", type: "textarea", group: "The visit" },
      MODULE_TYPE_F(undefined, "Curriculum covered"),
      MODULE_F(undefined, "Curriculum covered"),
      UNITS_MULTI("units_covered", "Curriculum covered"),
      SESSIONS_MULTI("sessions_covered", "Curriculum covered"),

      { name: "organisation_name", label: "Field visit organisation", group: "Organisation" },
      { name: "address", label: "Organisation address", type: "textarea", group: "Organisation" },
      { name: "distance_km", label: "Distance (km)", type: "number", min: 0, group: "Organisation" },
      { name: "contact_person", label: "Contact person", group: "Organisation" },
      { name: "contact_mobile", label: "Contact mobile", type: "tel", group: "Organisation" },
      { name: "contact_email", label: "Contact email", type: "email", group: "Organisation" },
      { name: "contact_designation", label: "Contact designation", group: "Organisation" },
      { name: "more_visits_interest", label: "Interested in more field visits?", type: "checkbox", group: "Organisation" },
      { name: "ojt_internship_interest", label: "Interested in OJT / internship?", type: "checkbox", group: "Organisation" },

      { name: "picture_url", label: "Field visit picture", type: "file", accept: "image/*", group: "Feedback & evidence" },
      { name: "organisation_feedback", label: "Feedback from the organisation", type: "textarea", group: "Feedback & evidence" },
      { name: "student_feedback", label: "Remarks / student feedback", type: "textarea", group: "Feedback & evidence" },

      { name: "student_marks", label: "Students present", type: "studentmarks", classField: "class_grade", sectionField: "sections", group: "Students present" },
    ],
  },
  "guest-lectures": {
    label: "Guest Lectures", singular: "Guest Lecture", icon: "🎤", group: "Daily Operations",
    columns: [
      { key: "reporting_date", label: "Date" },
      { key: "topic", label: "Topic" },
      { key: "lecturer_name", label: "Lecturer" },
      { key: "lecture_type", label: "Type", badge: true },
    ],
    fields: [
      { name: "reporting_date", label: "Reporting date", type: "date", required: true, defaultValue: today, group: "Who & where" },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["VT", "PR"], group: "Who & where" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT"], group: "Who & where" },
      { name: "class_grade", label: "Class", type: "select", dynamicOptions: CLASS_BY_LAB, required: true, group: "Who & where" },
      {
        name: "sections", label: "Section(s)", type: "multiselect",
        dynamicOptions: SECTIONS_FOR("class_grade"), dependsOn: { field: "class_grade" },
        allowCustom: true, customPlaceholder: "Another section…", hint: SECTION_HINT, group: "Who & where",
      },
      {
        name: "job_role_id", label: "Job role", type: "select",
        derive: DERIVE_JOB_ROLE("class_grade"), deriveNote: JOB_ROLE_NOTE,
        dynamicOptions: JOBROLE_BY_LAB, group: "Who & where",
      },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Who & where" },

      { name: "lecture_type", label: "Guest lecture type", type: "select", enumKey: "guest_lecture_types", group: "The lecture" },
      { name: "topic", label: "Guest lecture topic", required: true, group: "The lecture" },
      { name: "duration_mins", label: "Class duration (minutes)", type: "number", min: 0, group: "The lecture" },
      { name: "methodology", label: "Methodology", type: "select", enumKey: "guest_lecture_methodology", group: "The lecture" },
      MODULE_TYPE_F(undefined, "Curriculum covered"),
      MODULE_F(undefined, "Curriculum covered"),
      UNITS_MULTI("units", "Curriculum covered"),
      SESSIONS_MULTI("sessions", "Curriculum covered"),

      { name: "lecturer_name", label: "Lecturer name", group: "The lecturer" },
      { name: "lecturer_qualification", label: "Qualification", group: "The lecturer" },
      { name: "lecturer_phone", label: "Phone", type: "tel", group: "The lecturer" },
      { name: "lecturer_email", label: "Email", type: "email", group: "The lecturer" },
      { name: "lecturer_experience", label: "Work experience", group: "The lecturer" },
      { name: "lecturer_work_status", label: "Work status", type: "select", enumKey: "lecturer_work_status", group: "The lecturer" },
      { name: "lecturer_address", label: "Address", type: "textarea", group: "The lecturer" },
      { name: "lecturer_photo_url", label: "Lecturer photo", type: "file", accept: "image/*", group: "The lecturer" },

      { name: "photo_url", label: "Guest lecture photo", type: "file", accept: "image/*", group: "Feedback & evidence" },
      { name: "student_feedback", label: "Remarks / student feedback", type: "textarea", group: "Feedback & evidence" },
    ],
  },
  equipment: {
    label: "Lab Equipment", singular: "Equipment", icon: "🖥️", group: "Daily Operations",
    columns: [
      { key: "school_name", label: "School" },
      { key: "equipment_status", label: "Status", badge: true },
      { key: "academic_year", label: "AY" },
    ],
    fields: [
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["VT", "PR"], group: "Lab" },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT"], group: "Lab" },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", autoFor: ["VT", "PR", "DM"], group: "Lab" },
      { name: "receiving_status", label: "Tool / equipment received?", type: "checkbox", group: "Equipment" },
      { name: "receipt_date", label: "Receipt date", type: "date", showIf: (v) => !!v.receiving_status, group: "Equipment" },
      { name: "equipment_status", label: "Tool / equipment status", type: "select", enumKey: "equipment_status", group: "Equipment" },
      { name: "raw_material_availability", label: "Raw material availability", type: "select", enumKey: "raw_material_availability", group: "Raw material" },
      { name: "raw_material_fund_status", label: "Raw material fund received?", type: "checkbox", group: "Raw material" },
      { name: "details", label: "Details", type: "textarea", group: "Raw material" },
    ],
  },
  "equipment-maintenance": {
    label: "Maintenance Log", singular: "Maintenance", icon: "🔧", group: "Daily Operations",
    columns: [
      { key: "date", label: "Date" },
      { key: "issue", label: "Issue" },
      { key: "cost_incurred", label: "Cost" },
      { key: "resolved_by", label: "By" },
    ],
    fields: [
      { name: "equipment_id", label: "Equipment", type: "select", optionsKey: "equipment", async: true, required: true },
      { name: "date", label: "Date", type: "date", defaultValue: today },
      { name: "issue", label: "Issue", type: "textarea" },
      { name: "action", label: "Action taken", type: "textarea" },
      { name: "cost_incurred", label: "Cost incurred", type: "number", min: 0 },
      { name: "downtime_hours", label: "Downtime (hours)", type: "number", min: 0 },
      { name: "resolved_by", label: "Resolved by" },
    ],
  },

  // ---------------- INTERNSHIP ----------------
  employers: {
    label: "Employers", singular: "Employer", icon: "🏢", group: "Internship & Placement",
    columns: [
      { key: "org_name", label: "Organisation" },
      { key: "poc_email", label: "Contact" },
      { key: "district", label: "District" },
      { key: "is_active", label: "Active", badge: true },
    ],
    fields: [
      { name: "org_name", label: "School / organisation name", required: true, group: "Business" },
      { name: "business_description", label: "Business description", type: "textarea", group: "Business" },
      { name: "employee_count", label: "Number of employees", type: "select", enumKey: "employee_count", group: "Business" },
      { name: "year_of_foundation", label: "Year of foundation", type: "number", min: 1800, max: 2100, group: "Business" },
      { name: "sector_id", label: "Lab / sector", type: "select", ...SECTOR, group: "Business", hint: "One of the sectors your organisation runs labs in." },
      { name: "is_active", label: "Active?", type: "checkbox", defaultValue: true, group: "Business" },

      { name: "first_name", label: "First name", group: "Contact person" },
      { name: "last_name", label: "Last name", group: "Contact person" },
      { name: "gender", label: "Gender", type: "select", enumKey: "genders", group: "Contact person" },

      { name: "branch_name", label: "Branch name", group: "Office address" },
      { name: "branch_address", label: "Branch address", type: "textarea", group: "Office address" },
      { name: "poc_mobile", label: "POC mobile number", type: "tel", group: "Office address" },
      { name: "poc_email", label: "POC email ID", type: "email", group: "Office address" },
      { name: "state", label: "State", type: "select", dynamicOptions: NAME_OPTS("states"), group: "Office address" },
      { name: "district", label: "District", type: "select", dynamicOptions: NAME_OPTS("districts"), group: "Office address" },
      { name: "pincode", label: "Pincode", group: "Office address" },
    ],
  },
  "employer-student-maps": {
    label: "Employer-Student Maps", singular: "Mapping", icon: "🔗", group: "Internship & Placement",
    columns: [
      { key: "student_name", label: "Student" },
      { key: "academic_year", label: "AY" },
      { key: "status", label: "Status", badge: true },
      { key: "ojt_hours_logged", label: "OJT hrs" },
    ],
    formHint: "Map a student to the employer they are interning with.",
    fields: [
      { name: "student_id", label: "Student", type: "select", optionsKey: "students", async: true, required: true, group: "Mapping" },
      { name: "employer_id", label: "Employer", type: "select", optionsKey: "employers", async: true, required: true, group: "Mapping" },
      { name: "job_role_id", label: "Job role", type: "select", ...JOBROLE, derive: FROM_STUDENT("job_role_id"), deriveNote: STUDENT_NOTE, autoFor: ["VT"], group: "Mapping" },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", derive: FROM_STUDENT("academic_year"), deriveNote: STUDENT_NOTE, autoFor: ["VT", "PR", "DM"], group: "Mapping" },
      { name: "start_date", label: "Start date", type: "date", group: "Internship" },
      { name: "end_date", label: "End date", type: "date", group: "Internship" },
      { name: "status", label: "Status", type: "select", options: ["ongoing", "completed"], defaultValue: "ongoing", group: "Internship" },
      { name: "ojt_hours_target", label: "OJT hours target", type: "number", min: 0, defaultValue: 50, group: "Internship" },
      { name: "ojt_hours_logged", label: "OJT hours logged", type: "number", min: 0, group: "Internship" },
    ],
  },
  diaries: {
    label: "Daily Diaries", singular: "Diary", icon: "📔", group: "Internship & Placement",
    columns: [
      { key: "date", label: "Date" },
      { key: "student_name", label: "Student" },
      { key: "hours_spent", label: "Hours" },
    ],
    fields: [
      // A student's diary is about themselves - identity, school, lab, class
      // and the employer they are placed with all come from their record.
      { name: "student_id", label: "Student", type: "select", optionsKey: "students", async: true, autoFor: ["ST"], required: true },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, derive: FROM_STUDENT("school_id"), deriveNote: STUDENT_NOTE, autoFor: ["ST", "VT"] },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, derive: FROM_STUDENT("lab_id"), deriveNote: STUDENT_NOTE, autoFor: ["ST", "VT"] },
      { name: "class_grade", label: "Class", type: "select", enumKey: "class_grades", derive: FROM_STUDENT("class_grade"), deriveNote: STUDENT_NOTE, autoFor: ["ST"] },
      { name: "section", label: "Section", derive: FROM_STUDENT("section"), deriveNote: STUDENT_NOTE, autoFor: ["ST"] },
      { name: "date", label: "Date", type: "date", required: true, defaultValue: today },
      { name: "employer_id", label: "Employer", type: "select", optionsKey: "employers", async: true, autoFor: ["ST"], hint: "Your current internship placement." },
      { name: "learning", label: "What did you learn today?", type: "textarea", rows: 5, required: true },
      { name: "hours_spent", label: "Hours spent", type: "number", min: 0, max: 24 },
      { name: "photo_url", label: "Photo (optional)", type: "file", accept: "image/*" },
    ],
  },
  "ojt-placements": {
    label: "OJT / Placement", singular: "OJT / Placement", icon: "🎓", group: "Internship & Placement",
    columns: [
      { key: "student_name", label: "Student" },
      { key: "ojt_hours_logged", label: "OJT hrs" },
      { key: "placement_placed", label: "Placed", badge: true },
    ],
    fields: [
      { name: "student_id", label: "Student", type: "select", optionsKey: "students", async: true, required: true, autoFor: ["ST"], group: "Student" },
      { name: "academic_year", label: "Academic year", type: "select", ...AY, valueKey: "label", derive: FROM_STUDENT("academic_year"), deriveNote: STUDENT_NOTE, autoFor: ["VT", "PR", "DM", "ST"], group: "Student" },
      { name: "job_role_id", label: "Job role", type: "select", ...JOBROLE, derive: FROM_STUDENT("job_role_id"), deriveNote: STUDENT_NOTE, autoFor: ["VT", "ST"], group: "Student" },
      { name: "ojt_establishment", label: "OJT establishment", group: "OJT" },
      { name: "ojt_hours_required", label: "OJT hours required", type: "number", min: 0, defaultValue: 50, group: "OJT" },
      { name: "ojt_hours_logged", label: "OJT hours logged", type: "number", min: 0, group: "OJT" },
      { name: "ojt_start", label: "OJT start", type: "date", group: "OJT" },
      { name: "ojt_end", label: "OJT end", type: "date", group: "OJT" },
      { name: "apprenticeship_interested", label: "Interested in apprenticeship?", type: "checkbox", group: "Apprenticeship" },
      { name: "apprenticeship_placed", label: "Apprenticeship placed?", type: "checkbox", group: "Apprenticeship" },
      { name: "apprenticeship_employer_id", label: "Apprenticeship employer", type: "select", optionsKey: "employers", async: true, showIf: (v) => !!v.apprenticeship_placed, group: "Apprenticeship" },
      { name: "placement_interested", label: "Interested in placement?", type: "checkbox", group: "Placement" },
      { name: "placement_placed", label: "Placed?", type: "checkbox", group: "Placement" },
      { name: "placement_employer_id", label: "Placement employer", type: "select", optionsKey: "employers", async: true, showIf: (v) => !!v.placement_placed, group: "Placement" },
      { name: "placement_letter_date", label: "Placement letter date", type: "date", showIf: (v) => !!v.placement_placed, group: "Placement" },
      { name: "placement_letter_url", label: "Placement letter", type: "file", showIf: (v) => !!v.placement_placed, group: "Placement" },
    ],
  },

  // ---------------- CROSS-CUTTING ----------------
  feedback: {
    label: "Feedback", singular: "Feedback", icon: "💬", group: "Cross-cutting",
    columns: [
      { key: "date", label: "Date" },
      { key: "source", label: "Source" },
      { key: "subject", label: "Subject" },
      { key: "rating", label: "Rating" },
    ],
    fields: [
      { name: "date", label: "Date", type: "date", defaultValue: today },
      {
        name: "source", label: "Source", type: "select",
        options: ["student", "teacher", "inspection team"],
        defaults: { ST: "student", VT: "teacher", PR: "teacher" }, autoFor: ["ST"],
      },
      { name: "subject", label: "Subject" },
      { name: "rating", label: "Rating (1-5)", type: "number", min: 1, max: 5 },
      { name: "comments", label: "Comments", type: "textarea" },
      { name: "school_id", label: "School", type: "select", ...SCHOOL, autoFor: ["PR", "VT", "ST"] },
      { name: "lab_id", label: "Lab", type: "select", ...LAB_BY_SCHOOL, autoFor: ["VT", "ST"] },
    ],
  },
  notifications: {
    label: "Notifications", singular: "Notification", icon: "🔔", group: "Administration",
    roles: ["SA", "OA"],
    columns: [
      { key: "title", label: "Title" },
      { key: "category", label: "Category" },
      { key: "is_read", label: "Read", badge: true },
    ],
    fields: [
      { name: "title", label: "Title", required: true },
      { name: "body", label: "Body", type: "textarea" },
      { name: "category", label: "Category", type: "select", options: ["issue", "verification", "endorsement", "sla"] },
      { name: "link", label: "Link", placeholder: "/app/issues?workflow_status=open" },
    ],
  },
};

export const NAV_GROUPS = [
  "Master Data",
  "People & Students",
  "Daily Operations",
  "Internship & Placement",
  "Cross-cutting",
  "Administration",
];

// Each role opens the app on the work it actually does: a trainer's day is
// daily entries, an admin's is the master data behind them.
export const NAV_GROUP_ORDER = {
  SA: NAV_GROUPS,
  OA: NAV_GROUPS,
  DM: ["People & Students", "Daily Operations", "Master Data", "Internship & Placement", "Cross-cutting", "Administration"],
  PR: ["Daily Operations", "People & Students", "Internship & Placement", "Master Data", "Cross-cutting", "Administration"],
  VT: ["Daily Operations", "People & Students", "Internship & Placement", "Master Data", "Cross-cutting", "Administration"],
  ST: ["Internship & Placement", "Master Data", "Cross-cutting"],
};

export { YESNO };
