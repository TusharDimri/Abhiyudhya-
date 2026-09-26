// Maps status-ish strings to semantic badge colours.
const MAP = {
  active: "success", verified: "success", endorsed: "success", resolved: "success",
  completed: "success", pass: "success", working: "success", true: "success", paid: "gold",
  pending: "warning", "in-progress": "warning", submitted: "info", ongoing: "info",
  "partially working": "warning", substitute: "warning", online: "info",
  rejected: "danger", returned: "danger", fail: "danger", "not working": "danger",
  exited: "danger", deleted: "danger", open: "warning", false: "",
  // student enrolment
  studying: "info", "dropped out": "danger", "transferred out": "", "completed": "success",
  // maintenance log
  reported: "warning", "under inspection": "info", "awaiting spare parts": "warning",
  "sent for repair": "info", "under repair": "info", repaired: "success",
  "not repairable": "danger", replaced: "gold",
};

export default function Badge({ value, label }) {
  if (value === null || value === undefined || value === "") return <span className="muted">—</span>;
  let text = label ?? value;
  if (value === true) text = "Yes";
  if (value === false) text = "No";
  const cls = MAP[String(value).toLowerCase()] ?? "";
  return <span className={`badge ${cls}`}>{String(text)}</span>;
}
