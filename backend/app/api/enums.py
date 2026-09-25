"""Fixed option lists, defined once and served to the frontend.

These are the lists the spec fixes (activity types, issue sub-issues, ...) as
opposed to the editable masters in Part 0.4, which live in their own tables.
Keeping them here means the dropdown a trainer sees and the rule the API
enforces can never drift apart: /meta/bootstrap ships `enums` to the client,
and the validators below read the same dictionaries.

Entries are {value, label}. `value` is what is stored - never change an
existing one or historic rows stop matching their label.
"""


def _opts(*labels):
    """Plain list where the stored value is the label."""
    return [{"value": l, "label": l} for l in labels]


# --- Daily attendance (spec 3.11) ---------------------------------------
DAY_TYPES = _opts("Working day", "On leave", "Holiday-Off")

ACTIVITY_TYPES = _opts(
    "Teaching Vocational Education",
    "Visit to Industry",
    "Visit to Educational Institution",
    "On-Job Training Coordination",
    "Parent Teachers Meeting",
    "Community Home Visit",
    "School / Event Celebration",
    "Teaching Non-Vocational Subject",
    "Work Assigned by Headmaster",
    "Assignment from Vocational Department",
    "School Exam Duty",
    "Assessor in Other School",
    "Training of Teacher/Trainer",
    "Guidance & Counselling",
    "Other Work",
)

OJT_COORDINATION_ACTIVITIES = _opts(
    "Exploration Industry Visit",
    "Industry Visit For Supporting Students Placed",
    "Orientation of Students",
    "Other Coordination Work",
)

TRAINING_TYPES = _opts(
    "VTP Training Programme",
    "Samagra Shiksha Training Programme",
    "Other Training Programme",
)

CLASS_TYPES = _opts("regular", "revision", "online", "community")
THEORY_PRACTICAL = _opts("Theory", "Practical")
# stored values stay as they are in existing rows; only the label spells out
# the full spec wording.
MODULE_TYPES = [
    {"value": "Employability", "label": "Employability Skills"},
    {"value": "Vocational", "label": "Vocational Skills"},
]

# --- VT issue reporting (spec 3.12) -------------------------------------
# main issue -> its own sub-issue list. The stored main-issue values are kept
# exactly as they already are in the database.
ISSUE_MAIN = _opts(
    "Guest Lecture/Field Visit",
    "Lab-Room/Infrastructure",
    "Payment-Expense-Reimbursement",
    "Syllabus/Text Book & Lesson Plan",
    "Other",
)

ISSUE_SUB = {
    "Guest Lecture/Field Visit": _opts(
        "Field Visit Approval Pending - Higher Authority",
        "Field Visit Not Organised",
        "FV approval pending by HM",
        "FV not organised",
        "GL approval pending by HM",
        "GL not organised",
        "GL/FV other issues",
        "Guest Lecture Approval Pending - Higher Authority",
        "Guest Lecture Not Conducted",
        "Guest Lecture or Field Visit - Other issue",
        "Guest Lecturer Not Available",
    ),
    "Lab-Room/Infrastructure": _opts(
        "Maintenance Required",
        "Only Single Room Allotted - MSFC",
        "Room Condition Repair Needed",
        "Room Not Allotted",
    ),
    "Payment-Expense-Reimbursement": _opts(
        "Course material and book amount",
        "Daily allowance (School event/meetings)",
        "Field Visit Expenses",
        "Guest Lecture Expenses",
        "Honorarium - Vocational Trainer",
        "Office Expenses",
        "Raw Material Expenses",
        "Travel Allowances (Workshop and Training)",
        "VT Salary",
    ),
    "Syllabus/Text Book & Lesson Plan": _opts(
        "Book Not Received",
        "Syllabus Not Received",
        "Text Books Not Received",
        "Syllabus & Session Plan - Other issue",
        "Other",
    ),
    "Other": _opts("Other"),
}

STUDENTS_AFFECTED = [
    {"value": "all", "label": "All students"},
    {"value": "some", "label": "Some students"},
    {"value": "not applicable", "label": "Not applicable"},
]

# --- Other fixed lists ---------------------------------------------------
GUEST_LECTURE_TYPES = [
    {"value": "paid", "label": "Paid guest lecture"},
    {"value": "unpaid", "label": "Unpaid guest lecture"},
]
GUEST_LECTURE_METHODOLOGY = _opts(
    "Presentation", "Interactive", "Role-play", "Demonstration",
    "Video screening & discussion", "Online lecture", "Other",
)
LECTURER_WORK_STATUS = [
    {"value": "job", "label": "Working in a job"},
    {"value": "self-employed", "label": "Self employed"},
]
EQUIPMENT_STATUS = _opts("working", "partially working", "not working")
# the life of a repair: reported -> diagnosed -> being fixed -> an outcome
MAINTENANCE_STATUS = _opts(
    "Reported", "Under Inspection", "Awaiting Spare Parts", "Sent for Repair",
    "Under Repair", "Repaired", "Not Repairable", "Replaced",
)
RAW_MATERIAL_AVAILABILITY = [
    {"value": "available", "label": "Available"},
    {"value": "not available", "label": "Not available"},
]
EMPLOYEE_COUNT = _opts("0-1", "2-5", "6-10", "11-20", "20+")
GENDERS = _opts("Male", "Female", "Other")

# --- trainer profile ---
MARITAL_STATUS = _opts("Single", "Married", "Divorced", "Widowed")
BLOOD_GROUPS = _opts("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
SCHOOL_TYPES = _opts("Boys", "Girls", "Co-education")
APPOINTMENT_NATURE = _opts("Contractual", "Adhoc", "Regular", "Guest")
QUALIFICATION_LEVELS = _opts("10th", "12th", "Diploma", "Graduation", "Masters/Post-Graduation", "Doctorate", "Other")
COURSE_TYPES = _opts("Full Time", "Part Time", "Distance")
JOB_TYPES = _opts("Full Time", "Part Time")
JOB_NATURE = _opts("Contractual", "Adhoc", "Permanent", "Temporary")
PRINCIPAL_DESIGNATIONS = _opts(
    "Principal", "Headmaster", "Headmistress", "Principal (In-charge)",
    "Headmaster (In-charge)", "Headmistress (In-charge)", "Vice-Principal",
)
CLASS_GRADES = [{"value": g, "label": f"Class {g}"} for g in ("9", "10", "11", "12")]
REGISTRATION_CLASSES = [{"value": g, "label": f"Class {g}"} for g in ("9", "11")]
VERIFICATION_STATUS = _opts("pending", "verified", "rejected")
ENROLMENT_STATUS = _opts("Studying", "Completed", "Dropped Out", "Transferred Out")
TRAINER_STATUS = _opts("active", "substitute", "exited")
ASSESSMENT_TYPES = _opts("internal", "continuous", "year-end board")

# Everything the frontend receives in /meta/bootstrap under "enums".
ENUMS = {
    "day_types": DAY_TYPES,
    "activity_types": ACTIVITY_TYPES,
    "ojt_coordination_activities": OJT_COORDINATION_ACTIVITIES,
    "training_types": TRAINING_TYPES,
    "class_types": CLASS_TYPES,
    "theory_practical": THEORY_PRACTICAL,
    "module_types": MODULE_TYPES,
    "issue_main": ISSUE_MAIN,
    "issue_sub": ISSUE_SUB,
    "students_affected": STUDENTS_AFFECTED,
    "guest_lecture_types": GUEST_LECTURE_TYPES,
    "guest_lecture_methodology": GUEST_LECTURE_METHODOLOGY,
    "lecturer_work_status": LECTURER_WORK_STATUS,
    "equipment_status": EQUIPMENT_STATUS,
    "maintenance_status": MAINTENANCE_STATUS,
    "raw_material_availability": RAW_MATERIAL_AVAILABILITY,
    "employee_count": EMPLOYEE_COUNT,
    "genders": GENDERS,
    "marital_status": MARITAL_STATUS,
    "blood_groups": BLOOD_GROUPS,
    "school_types": SCHOOL_TYPES,
    "appointment_nature": APPOINTMENT_NATURE,
    "qualification_levels": QUALIFICATION_LEVELS,
    "course_types": COURSE_TYPES,
    "job_types": JOB_TYPES,
    "job_nature": JOB_NATURE,
    "principal_designations": PRINCIPAL_DESIGNATIONS,
    "class_grades": CLASS_GRADES,
    "registration_classes": REGISTRATION_CLASSES,
    "verification_status": VERIFICATION_STATUS,
    "enrolment_status": ENROLMENT_STATUS,
    "trainer_status": TRAINER_STATUS,
    "assessment_types": ASSESSMENT_TYPES,
}


def values(key):
    """Allowed stored values for an enum key (used by validators)."""
    return {o["value"] for o in ENUMS.get(key, [])}


def sub_issue_values(main_issue):
    return {o["value"] for o in ISSUE_SUB.get(main_issue, [])}
