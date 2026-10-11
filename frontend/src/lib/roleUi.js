/* Per-role UI intent, in one place.

   RBAC decides what a role *may* touch. This file decides what the app should
   feel like for them: where a headline number leads when you click it, what
   they most likely came here to do, and what an empty screen should offer
   instead of a shrug. Nothing here grants access - the API is still the
   authority, and every destination below is a screen the role can already
   open. */

// A KPI card is a question ("how many are waiting?"). Clicking it should land
// on the list that answers it, already filtered - not on an unfiltered screen
// the user then has to narrow by hand.
export const CARD_LINKS = {
  schools: { to: "/app/schools" },
  labs: { to: "/app/labs" },
  trainers: { to: "/app/trainers" },
  students: { to: "/app/students" },
  pending_verification: { to: "/app/students", params: { verification_status: "pending" } },
  attendance: { to: "/app/attendance" },
  guest_lectures: { to: "/app/guest-lectures" },
  field_visits: { to: "/app/field-visits" },
  open_issues: { to: "/app/issues", params: { workflow_status: "open" } },
  pending_issues_action: { to: "/app/issues", params: { workflow_status: "open" } },
  issues_resolved: { to: "/app/issues", params: { workflow_status: "resolved" } },
  pending_endorsement: { to: "/app/attendance", params: { endorsement_status: "submitted" } },
  my_open_issues: { to: "/app/principal-issues", params: { workflow_status: "open" } },
  pr_issues_action: { to: "/app/principal-issues", params: { workflow_status: "open" } },
  pr_issues_resolved: { to: "/app/principal-issues", params: { workflow_status: "resolved" } },
  class_pending_endorsement: { to: "/app/class-attendance", params: { endorsement_status: "submitted" } },
  endorsed: { to: "/app/attendance", params: { endorsement_status: "endorsed" } },
  diaries: { to: "/app/diaries" },
  placements: { to: "/app/ojt-placements", params: { placement_placed: "true" } },
  ojt_hours: { to: "/app/ojt-placements" },
  my_employer: { to: "/app/employer-student-maps" },
  assessments: { to: "/app/assessments" },
  class_attendance: { to: "/app/class-attendance" },
  equipment: { to: "/app/equipment" },
  equipment_under_repair: { to: "/app/equipment" },
};

export function cardHref(key) {
  const link = CARD_LINKS[key];
  if (!link) return null;
  const qs = new URLSearchParams(link.params || {}).toString();
  return qs ? `${link.to}?${qs}` : link.to;
}

// `?new=1` on a list screen opens its create drawer, so a shortcut can drop
// someone straight into the form rather than onto the list in front of it.
const create = (path) => `${path}?new=1`;

// Attendance is "verified" by the Principal; the stored values keep their
// original names (endorsed / submitted).
export const ISSUE_STATUS_LABELS = { open: "Open", "in-progress": "In progress", resolved: "Resolved" };

export const VERIFICATION_LABELS = {
  endorsed: "Verified",
  submitted: "Pending verification",
};

// What each role most likely opened the app to do.
export const QUICK_ACTIONS = {
  SA: [
    { label: "New organisation", icon: "organisations", to: create("/app/organisations") },
    { label: "Users & access", icon: "users", to: "/app/admin/users" },
    { label: "Audit log", icon: "audit", to: "/app/admin/audit" },
  ],
  OA: [
    { label: "Add a school", icon: "schools", to: create("/app/schools") },
    { label: "Add a lab", icon: "labs", to: create("/app/labs") },
    { label: "Students awaiting verification", icon: "students", to: "/app/students?verification_status=pending" },
    { label: "Users & access", icon: "users", to: "/app/admin/users" },
  ],
  DM: [
    { label: "VT issues needing action", icon: "issues", to: "/app/issues?workflow_status=open" },
    { label: "Principal issues needing action", icon: "principal-issues", to: "/app/principal-issues?workflow_status=open" },
    { label: "Maintenance needing action", icon: "equipment-maintenance", to: "/app/equipment-maintenance?maintenance_status=Reported" },
    { label: "Schools in my district", icon: "schools", to: "/app/schools" },
  ],
  DEPT: [
    { label: "Students", icon: "students", to: "/app/students" },
    { label: "Daily attendance", icon: "attendance", to: "/app/attendance" },
    { label: "Class attendance", icon: "class-attendance", to: "/app/class-attendance" },
    { label: "Lab equipment", icon: "equipment", to: "/app/equipment" },
  ],
  PR: [
    { label: "Verify daily attendance", icon: "attendance", to: "/app/attendance?endorsement_status=submitted" },
    { label: "Verify class attendance", icon: "class-attendance", to: "/app/class-attendance?endorsement_status=submitted" },
    { label: "Raise an issue", icon: "principal-issues", to: "/app/principal-issues?new=1" },
    { label: "My school's students", icon: "students", to: "/app/students" },
    { label: "Trainers at my school", icon: "trainers", to: "/app/trainers" },
  ],
  VT: [
    { label: "Mark today's attendance", icon: "attendance", to: create("/app/attendance") },
    { label: "Mark class attendance", icon: "class-attendance", to: create("/app/class-attendance") },
    { label: "Add students", icon: "students", to: "/app/students?tab=manage&manage=add" },
    { label: "Report an issue", icon: "issues", to: create("/app/issues") },
    { label: "Record a field visit", icon: "field-visits", to: create("/app/field-visits") },
  ],
};

// One line under the greeting saying what this role is looking at.
export const DASHBOARD_SUBTITLE = {
  SA: "Every organisation on the platform",
  OA: "Your organisation at a glance",
  DM: "The schools and labs in your district",
  DEPT: "Students, attendance and labs in your district",
  PR: "Your school at a glance",
  VT: "Your lab, your classes, your day",
};

// What an empty list should say - and offer - for the role looking at it.
export const EMPTY_HINTS = {
  attendance: { VT: "No attendance yet. Mark today's and it will appear here.", PR: "Nothing waiting for verification yet." },
  "class-attendance": { VT: "No classes marked yet." },
  "dept-issues": { DEPT: "You haven't raised any issues.", OA: "No issues raised by department logins." },
  students: { VT: "No students registered for your lab yet.", PR: "No students registered at your school yet.",
    DEPT: "No students registered at this school yet." },
  issues: { VT: "You haven't reported any issues.", DM: "No issues reported in your district." },
  "field-visits": { VT: "No field visits recorded yet." },
  "guest-lectures": { VT: "No guest lectures recorded yet." },
  "ojt-placements": { VT: "No OJT records for your students yet." },
};
