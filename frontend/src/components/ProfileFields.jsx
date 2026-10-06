/* What a trainer's and a principal's profile hold - the fields, the tables
   (qualifications, experience ...) and one input for either. The Profile page
   and the admin's "New Trainer" / "New Principal" form both use these, so the
   two always ask for the same things. */
import DateInput from "./DateInput";
import { Plus, X } from "lucide-react";
import { todayISO } from "../lib/dates";
import { optionText } from "../lib/fieldOptions";

export const money = (n) => (n == null || n === "" ? null : `₹ ${Number(n).toLocaleString("en-IN")}`);
export const yesNo = (v) => (v == null ? null : v ? "Yes" : "No");

// ------------------------------------------------------------ sections
export const GENERAL = [
  { name: "full_name", label: "Name" },
  { name: "father_name", label: "Father's name" },
  { name: "mother_name", label: "Mother's name" },
  { name: "dob", label: "Date of birth", type: "date" },
  { name: "domicile_state", label: "Domicile state" },
  { name: "gender", label: "Gender", type: "select", enumKey: "genders" },
  { name: "social_category_id", label: "Category", type: "select", optionsKey: "social_categories", show: (d) => d.category_name },
  { name: "phone", label: "Mobile no.", type: "tel", placeholder: "10 digits" },
  { name: "email", label: "Email ID", type: "email" },
  { name: "marital_status", label: "Marital status", type: "select", enumKey: "marital_status" },
  { name: "nationality", label: "Nationality", placeholder: "e.g. Indian" },
  { name: "aadhaar_number", label: "Aadhaar no.", placeholder: "12 digits", sensitive: true },
  { name: "blood_group", label: "Blood group", type: "select", enumKey: "blood_groups" },
  { name: "total_experience_years", label: "Total experience", computed: true, show: (d) => `${d.total_experience_years ?? 0} years` },
  { name: "vtp_name", label: "VTP name" },
  { name: "skill_name", label: "Skill name", computed: true, show: (d) => d.posting?.skill_name },
];
export const ADDRESS = [
  { name: "correspondence_address", label: "Correspondence address", type: "textarea", wide: true },
  { name: "permanent_address", label: "Permanent address", type: "textarea", wide: true },
];
export const BANK = [
  { name: "beneficiary_name", label: "Beneficiary name" },
  { name: "bank_name", label: "Bank name" },
  { name: "branch_address", label: "Branch address" },
  { name: "account_number", label: "Account no.", sensitive: true },
  { name: "ifsc_code", label: "IFSC code", placeholder: "e.g. PUNB0797200" },
  { name: "gross_salary", label: "Gross salary", type: "number", show: (d) => money(d.gross_salary) },
  { name: "deduction_esi", label: "ESI deduction", type: "number", show: (d) => money(d.deduction_esi) },
  { name: "deduction_epf", label: "EPF deduction", type: "number", show: (d) => money(d.deduction_epf) },
  { name: "deduction_tds", label: "TDS deduction", type: "number", show: (d) => money(d.deduction_tds) },
  { name: "deduction_other", label: "Other deduction", type: "number", show: (d) => money(d.deduction_other) },
  { name: "net_salary", label: "Net salary", computed: true, show: (d) => money(d.net_salary) },
  { name: "pan_number", label: "PAN", placeholder: "e.g. ABCDE1234F", sensitive: true },
  { name: "esi_number", label: "ESI number" },
  { name: "uan_number", label: "UAN number" },
];

export const TABLES = {
  qualifications: {
    title: "Qualification Details",
    columns: [
      { name: "qualification", label: "Qualification", type: "select", enumKey: "qualification_levels" },
      { name: "course", label: "Course" },
      { name: "institution", label: "University / College" },
      { name: "course_type", label: "Course type", type: "select", enumKey: "course_types" },
      { name: "passing_year", label: "Passing year", type: "number" },
      { name: "marksheet_date", label: "Final marksheet", type: "date" },
    ],
  },
  experiences: {
    title: "Experience Details",
    columns: [
      { name: "organisation_name", label: "Organisation" },
      { name: "address", label: "Address" },
      { name: "date_of_joining", label: "Date of joining", type: "date" },
      { name: "date_of_resignation", label: "Date of resignation", type: "date" },
      { name: "last_designation", label: "Last designation" },
      { name: "last_salary", label: "Last salary", type: "number", show: (r) => money(r.last_salary) },
      { name: "job_type", label: "Job type", type: "select", enumKey: "job_types" },
      { name: "job_nature", label: "Job nature", type: "select", enumKey: "job_nature" },
      { name: "reason_for_resignation", label: "Reason for resignation" },
    ],
  },
  trainings: {
    title: "Training Information",
    columns: [
      { name: "training_type", label: "Training type" },
      { name: "training_level", label: "Training level" },
      { name: "venue", label: "Venue" },
      { name: "from_date", label: "From", type: "date" },
      { name: "to_date", label: "To", type: "date" },
    ],
  },
  postings: {
    title: "NSQF History",
    columns: [
      { name: "vtp_name", label: "VTP name" },
      { name: "district", label: "District" },
      { name: "block", label: "Block" },
      { name: "school_name", label: "School name" },
      { name: "school_year", label: "School year", placeholder: "e.g. 2016-17" },
      { name: "school_type", label: "School type", type: "select", enumKey: "school_types" },
      { name: "date_of_joining", label: "DOJ", type: "date" },
      { name: "date_of_relieving", label: "DOR", type: "date" },
      { name: "appointment_nature", label: "Appointment", type: "select", enumKey: "appointment_nature" },
      { name: "appointment_letter", label: "Appointment letter", type: "yesno", show: (r) => yesNo(r.appointment_letter) },
      { name: "experience_certificate", label: "Experience certificate", type: "yesno", show: (r) => yesNo(r.experience_certificate) },
    ],
  },
};

// ---------------------------------------------------------- a principal's
export const PR_GENERAL = [
  { name: "full_name", label: "Name" },
  { name: "designation", label: "Designation", type: "select", enumKey: "principal_designations" },
  { name: "employee_id", label: "Employee ID" },
  { name: "father_name", label: "Father's name" },
  { name: "dob", label: "Date of birth", type: "date" },
  { name: "gender", label: "Gender", type: "select", enumKey: "genders" },
  { name: "social_category_id", label: "Category", type: "select", optionsKey: "social_categories", show: (d) => d.category_name },
  { name: "mobile", label: "Mobile no.", type: "tel", placeholder: "10 digits" },
  { name: "alternate_mobile", label: "Alternate mobile", type: "tel", placeholder: "10 digits" },
  { name: "email", label: "Email ID", type: "email" },
];
export const PR_SERVICE = [
  { name: "service_joining_date", label: "Joined government service", type: "date" },
  { name: "total_service_years", label: "Total service", computed: true, show: (d) => d.total_service_years != null && `${d.total_service_years} years` },
  { name: "substantive_post", label: "Substantive post", placeholder: "e.g. Lecturer (PGT) Physics" },
  { name: "highest_qualification", label: "Highest qualification", type: "select", enumKey: "qualification_levels" },
  { name: "professional_qualification", label: "Professional qualification", placeholder: "e.g. B.Ed, M.Ed" },
  { name: "subject_specialisation", label: "Subject specialisation" },
  { name: "superannuation_date", label: "Superannuation (at 60)", computed: true, type: "date", show: (d) => d.superannuation_date },
];
// at this school - no longer asked when the admin adds them
export const PR_POSTING = [
  { name: "date_of_joining", label: "In charge since", type: "date" },
  { name: "appointment_nature", label: "Nature of appointment", type: "select", enumKey: "appointment_nature" },
];
export const PR_PRABHARI = [
  { name: "vocational_prabhari_name", label: "Name" },
  { name: "vocational_prabhari_mobile", label: "Mobile no.", type: "tel", placeholder: "10 digits" },
  { name: "vocational_prabhari_email", label: "Email ID", type: "email" },
];
export const PR_TABLES = {
  qualifications: TABLES.qualifications,
  postings: {
    title: "Service History",
    columns: [
      { name: "school_name", label: "School" },
      { name: "district", label: "District" },
      { name: "block", label: "Block" },
      { name: "designation", label: "Designation" },
      { name: "from_date", label: "From", type: "date" },
      { name: "to_date", label: "To", type: "date" },
    ],
  },
  trainings: { ...TABLES.trainings, title: "Trainings Attended" },
};

// one input for a field or table cell
export function Control({ f, value, onChange, boot, disabled }) {
  const opts = f.enumKey ? boot?.enums?.[f.enumKey] : f.optionsKey ? boot?.options?.[f.optionsKey] : null;
  if (f.type === "date") return <DateInput value={value || ""} onChange={onChange} max={todayISO()} />;
  if (f.type === "textarea")
    return <textarea className="input" rows={2} value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  if (f.type === "yesno")
    return (
      <select className="select" value={value == null ? "" : value ? "true" : "false"} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "true")}>
        <option value="">—</option><option value="true">Yes</option><option value="false">No</option>
      </select>
    );
  if (opts)
    return (
      <select className="select" value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">— Select —</option>
        {opts.map((o) => <option key={o.value} value={o.value}>{optionText(o.label)}</option>)}
      </select>
    );
  return (
    <input className="input" type={["number", "tel", "email"].includes(f.type) ? f.type : "text"} placeholder={f.placeholder || ""}
      value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
  );
}

// pictures held on each profile: [label, field]
export const VT_PICTURES = [["Photo", "photo_url"], ["VT signature", "vt_signature_url"], ["VTP signature", "vtp_signature_url"]];
export const PR_PICTURES = [["Photo", "photo_url"], ["Signature", "signature_url"], ["School seal", "school_seal_url"]];

/* A profile table as a form field: rows to add, fill in and remove. */
export function RowsInput({ table, value, onChange, boot }) {
  const rows = Array.isArray(value) ? value : [];
  const blank = () => Object.fromEntries(table.columns.map((c) => [c.name, c.type === "yesno" ? null : ""]));
  const put = (i, name, v) => onChange(rows.map((r, j) => (j === i ? { ...r, [name]: v } : r)));
  return (
    <div className="rows-input">
      <div className="table-wrap">
        <table className="data profile-table">
          <thead>
            <tr><th>Sr</th>{table.columns.map((c) => <th key={c.name}>{c.label}</th>)}<th /></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id || `new-${i}`}>
                <td>{i + 1}</td>
                {table.columns.map((c) => (
                  <td key={c.name}><Control f={c} boot={boot} value={r[c.name]} onChange={(v) => put(i, c.name, v)} /></td>
                ))}
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" title="Remove this row"
                    onClick={() => onChange(rows.filter((_, j) => j !== i))}><X size={15} /></button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={table.columns.length + 2} className="muted" style={{ textAlign: "center" }}>Nothing added yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange([...rows, blank()])}><Plus size={15} /> Add row</button>
    </div>
  );
}

/* The profile as fields of the admin's add / edit form, section by section.
   `skip`: fields the form already asks for elsewhere (name, contact ...). */
function asFormFields(sections, tables, pictures, skip) {
  const out = [];
  for (const [group, fields] of sections) {
    for (const f of fields) {
      if (f.computed || skip.includes(f.name)) continue;
      const { show, computed, sensitive, ...rest } = f;
      out.push({
        ...rest, group,
        ...(f.type === "date" ? { max: todayISO } : {}),
        ...(sensitive ? { hint: "Shown masked when editing - leave it as it is to keep it." } : {}),
      });
    }
  }
  for (const [label, name] of pictures) out.push({ name, label, type: "file", accept: "image/*", group: "Photo & signatures" });
  for (const [name, table] of Object.entries(tables)) out.push({ name, label: table.title, type: "rows", table, group: table.title });
  return out;
}

export const trainerProfileFields = (skip = []) => asFormFields(
  [["Personal details", GENERAL], ["Address", ADDRESS], ["Bank & salary", BANK]], TABLES, VT_PICTURES, skip);
export const principalProfileFields = (skip = []) => asFormFields(
  [["Personal details", PR_GENERAL], ["Service details", PR_SERVICE], ["Address", ADDRESS]], PR_TABLES, PR_PICTURES, skip);
