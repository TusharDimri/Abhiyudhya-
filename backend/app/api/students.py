"""Adding students - many at once.

POST /api/students/bulk
    {lab_id, class_grade, section, students: [{admission_number, first_name,
     last_name, gender, dob, father_name, mobile_primary, social_category_id,
     aadhaar_number, roll_number, cwsn}]}

Every student must have: admission number, first name, gender, date of birth,
father's name, contact number, category and Aadhaar number. Admission numbers
are unique within the school, Aadhaar numbers within the organisation.

The trainer picks the class (9-12, whichever the lab runs) and section once
and types one row per student.
Every row is checked first; if any is wrong nothing is saved and the answer
lists each problem by row, so the page can point at it. School, job role and
academic year are worked out (from the lab, the class and today's date);
roll numbers left blank are given the next free ones ("9A-07").
"""
import re
from datetime import date

from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models.lab import Lab
from app.models.masters import SocialCategory
from app.models.student import Student
from app.rbac import current_user, login_required
from app.rbac.curriculum import allowed_class_grades
from app.rbac.roles import Role
from app.services import audit
from app.services.academic_year import academic_year_for

bp = Blueprint("students_admin", __name__, url_prefix="/api/students")

MAX_ROWS = 100
# Any class the lab runs - a school joining mid-course has Class 10 and 12
# students too. (Moving up a class at year end is still Promote.)
REGISTRATION_CLASSES = ("9", "10", "11", "12")
MOBILE = re.compile(r"^[6-9]\d{9}$")
AADHAAR = re.compile(r"^\d{12}$")
ROLL_SUFFIX = re.compile(r"(\d+)$")


def _next_rolls(lab, class_grade, section, year, count):
    """The next `count` roll numbers after the highest one already used."""
    used = {
        r[0] for r in db.session.query(Student.roll_number).filter(
            Student.lab_id == lab.id, Student.class_grade == class_grade, Student.section == section,
            Student.academic_year == year, Student.is_deleted.is_(False), Student.roll_number.isnot(None))
    }
    top = max((int(m.group(1)) for r in used if (m := ROLL_SUFFIX.search(r))), default=0)
    return [f"{class_grade}{section}-{top + i:02d}" for i in range(1, count + 1)], used


@bp.post("/bulk")
@login_required
def add_students():
    user = current_user()
    if user.role != Role.TRAINER.value:
        abort(403, description="Only a trainer adds students.")
    data = request.get_json(silent=True) or {}
    rows = data.get("students") or []
    if not isinstance(rows, list) or not rows:
        abort(400, description="Add at least one student.")
    if len(rows) > MAX_ROWS:
        abort(400, description=f"Add up to {MAX_ROWS} students at a time.")

    # ---- the class they go into
    lab = db.session.get(Lab, data.get("lab_id")) if data.get("lab_id") else None
    if lab is None or lab.id not in {l.id for l in user.labs}:
        abort(400, description="Choose one of your labs.")
    class_grade, section = str(data.get("class_grade") or ""), str(data.get("section") or "").strip().upper()
    if class_grade not in REGISTRATION_CLASSES:
        abort(400, description="Choose Class 9, 10, 11 or 12.")
    job_role = lab.job_role_for(class_grade)
    if not job_role or class_grade not in allowed_class_grades(user, job_role):
        abort(400, description=f"Your lab doesn't run Class {class_grade}.")
    configured = lab.sections_for(class_grade)
    if not section or (configured and section not in configured):
        abort(400, description=f"Choose a section of Class {class_grade}"
                               + (f" ({', '.join(configured)})." if configured else "."))
    year = academic_year_for(user.organisation_id, date.today())

    # ---- check every row before saving any
    categories = {str(c.id) for c in db.session.query(SocialCategory.id).filter(
        SocialCategory.organisation_id == user.organisation_id)}
    from app.api import enums
    genders = enums.values("genders")
    auto, used = _next_rolls(lab, class_grade, section, year, len(rows))
    taken_admissions = {r[0] for r in db.session.query(Student.admission_number).filter(
        Student.school_id == lab.school_id, Student.is_deleted.is_(False), Student.admission_number.isnot(None))}
    taken_aadhaar = {r[0] for r in db.session.query(Student.aadhaar_number).filter(
        Student.organisation_id == user.organisation_id, Student.is_deleted.is_(False),
        Student.aadhaar_number.isnot(None))}
    batch_admissions, batch_aadhaar = set(), set()
    auto_iter = iter(auto)
    errors, clean, rolls_in_batch = [], [], set()
    for i, raw in enumerate(rows, start=1):
        raw = raw if isinstance(raw, dict) else {}
        problems = []
        admission = (raw.get("admission_number") or "").strip()
        if not admission:
            problems.append("admission number is missing")
        elif admission in taken_admissions or admission in batch_admissions:
            problems.append(f"admission number {admission} is already used")
        first = (raw.get("first_name") or "").strip()
        if not first:
            problems.append("first name is missing")
        gender = (raw.get("gender") or "").strip()
        if gender not in genders:
            problems.append("choose the gender")
        dob = None
        if not raw.get("dob"):
            problems.append("date of birth is missing")
        else:
            try:
                dob = date.fromisoformat(str(raw["dob"])[:10])
                age = (date.today() - dob).days / 365.25
                if not 10 <= age <= 25:
                    problems.append("date of birth looks wrong (age should be 10-25)")
            except ValueError:
                problems.append("date of birth isn't a real date")
        father = (raw.get("father_name") or "").strip()
        if not father:
            problems.append("father's name is missing")
        mobile = (raw.get("mobile_primary") or "").replace(" ", "") or None
        if not mobile:
            problems.append("contact number is missing")
        elif not MOBILE.match(mobile):
            problems.append("contact number must be 10 digits starting 6-9")
        cat = raw.get("social_category_id") or None
        if not cat:
            problems.append("choose the category")
        elif str(cat) not in categories:
            problems.append("unknown category")
        aadhaar = (raw.get("aadhaar_number") or "").replace(" ", "")
        if not aadhaar:
            problems.append("Aadhaar number is missing")
        elif not AADHAAR.match(aadhaar):
            problems.append("Aadhaar number must be 12 digits")
        elif aadhaar in taken_aadhaar or aadhaar in batch_aadhaar:
            problems.append("this Aadhaar number is already registered")
        roll = (raw.get("roll_number") or "").strip() or None
        if roll and (roll in used or roll in rolls_in_batch):
            problems.append(f"roll number {roll} is already taken")
        if problems:
            msg = "; ".join(problems)
            errors.append({"row": i, "message": msg[:1].upper() + msg[1:] + "."})
            continue
        roll = roll or next(auto_iter)
        while roll in used or roll in rolls_in_batch:   # a typed roll may have taken an auto one
            roll = next(auto_iter, None) or f"{class_grade}{section}-{len(used) + len(rolls_in_batch) + 1:02d}"
        rolls_in_batch.add(roll)
        batch_admissions.add(admission)
        batch_aadhaar.add(aadhaar)
        clean.append(dict(admission_number=admission, first_name=first,
                          last_name=(raw.get("last_name") or "").strip() or None,
                          gender=gender, dob=dob, father_name=father, mobile_primary=mobile,
                          social_category_id=cat, aadhaar_number=aadhaar, cwsn=bool(raw.get("cwsn")),
                          roll_number=roll))
    if errors:
        return jsonify({"error": "invalid_rows", "message": "Please fix the highlighted rows - nothing was saved.",
                        "errors": errors}), 400

    made = []
    for row in clean:
        s = Student(organisation_id=user.organisation_id, school_id=lab.school_id, lab_id=lab.id,
                    job_role_id=job_role, academic_year=year, class_grade=class_grade, section=section,
                    date_of_enrolment=date.today(), verification_status="pending",
                    enrolment_status="Studying", created_by=user.id, **row)
        db.session.add(s)
        made.append(s)
    db.session.flush()
    for s in made:
        audit.record(user, "create", "student", s.id, after=s.to_dict())
    db.session.commit()
    return jsonify({
        "added": len(made), "class_grade": class_grade, "section": section, "academic_year": year,
        "students": [{"id": str(s.id), "full_name": s.full_name, "roll_number": s.roll_number} for s in made],
    }), 201
