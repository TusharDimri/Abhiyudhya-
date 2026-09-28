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
        if problems:
            msg = "; ".join(problems)
            errors.append({"row": i, "message": msg[:1].upper() + msg[1:] + "."})
            continue
        roll = next(auto_iter)   # always the next free one - never typed in
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
    from app.services import notify
    notify.students_to_verify(user.organisation_id, lab.school_id, len(made), user, "added")
    db.session.commit()
    return jsonify({
        "added": len(made), "class_grade": class_grade, "section": section, "academic_year": year,
        "students": [{"id": str(s.id), "full_name": s.full_name, "roll_number": s.roll_number} for s in made],
    }), 201


# --------------------------------------------- previous students, into Class 11
# Class 11 takes new students and also this lab's earlier Class 10 students who
# aren't in 11-12 yet (they finished Class 10, left during it, or were never
# moved up). Either way they are verified again, as at Class 9.
REJOIN_FROM = ("Completed", "Dropped Out")


def _trainer_lab(user, lab_id):
    if user.role != Role.TRAINER.value:
        abort(403, description="Only a trainer adds students.")
    lab = db.session.get(Lab, lab_id) if lab_id else None
    if lab is None or lab.id not in {l.id for l in user.labs}:
        abort(400, description="Choose one of your labs.")
    if not lab.job_role_11_12_id:
        abort(400, description="Your lab doesn't run Class 11.")
    return lab


def _previous_students(lab, year):
    """Earlier Class 10 students of this lab who can join Class 11 now."""
    from sqlalchemy import and_, or_
    return (db.session.query(Student)
            .filter(Student.lab_id == lab.id, Student.class_grade == "10", Student.is_deleted.is_(False),
                    or_(Student.enrolment_status.in_(REJOIN_FROM),
                        and_(Student.enrolment_status == "Studying", Student.academic_year != year)))
            .order_by(Student.first_name, Student.last_name).all())


@bp.get("/previous")
@login_required
def previous_students():
    user = current_user()
    lab = _trainer_lab(user, request.args.get("lab_id"))
    year = academic_year_for(user.organisation_id, date.today())
    return jsonify({"data": [{
        "id": str(s.id), "full_name": s.full_name, "admission_number": s.admission_number,
        "section": s.section, "roll_number": s.roll_number, "academic_year": s.academic_year,
        "enrolment_status": s.enrolment_status,
    } for s in _previous_students(lab, year)]})


@bp.post("/previous")
@login_required
def add_previous_students():
    """Body: {lab_id, section, student_ids}. Moves them into Class 11 this
    year: next roll numbers, pending verification, Class 10 kept in history."""
    from app.models.student import StudentPromotion

    user = current_user()
    data = request.get_json(silent=True) or {}
    lab = _trainer_lab(user, data.get("lab_id"))
    section = str(data.get("section") or "").strip().upper()
    if section not in lab.sections_for("11"):
        abort(400, description="Choose a section of Class 11.")
    year = academic_year_for(user.organisation_id, date.today())
    allowed = {str(s.id): s for s in _previous_students(lab, year)}
    wanted = [str(i) for i in (data.get("student_ids") or [])]
    if not wanted:
        abort(400, description="Choose at least one student.")
    unknown = [i for i in wanted if i not in allowed]
    if unknown:
        abort(400, description="Some of these students can't join Class 11 from here.")

    rolls, _ = _next_rolls(lab, "11", section, year, len(wanted))
    job_role = lab.job_role_for("11")
    added = []
    for sid, roll in zip(wanted, rolls):
        s = allowed[sid]
        db.session.add(StudentPromotion(
            organisation_id=s.organisation_id, student_id=s.id,
            from_academic_year=s.academic_year, to_academic_year=year, from_class="10", to_class="11",
            outcome="Joined Class 11", created_by=user.id,
            from_roll_number=s.roll_number, from_job_role_id=s.job_role_id, from_lab_id=s.lab_id,
            from_school_id=s.school_id, from_verification_status=s.verification_status,
            from_enrolment_status=s.enrolment_status, snapshot=s.to_dict(), section=s.section,
        ))
        before = {"class_grade": s.class_grade, "academic_year": s.academic_year, "enrolment_status": s.enrolment_status}
        s.class_grade, s.section, s.roll_number, s.academic_year = "11", section, roll, year
        s.job_role_id = job_role
        s.enrolment_status, s.left_on, s.left_reason = "Studying", None, None
        s.had_vocational_9_10 = s.continuing_same_trade = True
        s.verification_status, s.verified_by, s.verified_on = "pending", None, None
        s.updated_by = user.id
        audit.record(user, "update", "student", s.id, before=before,
                     after={"class_grade": "11", "section": section, "academic_year": year, "joined": "Class 11"})
        added.append({"id": sid, "full_name": s.full_name, "roll_number": roll})
    from app.services import notify
    notify.students_to_verify(user.organisation_id, lab.school_id, len(added), user, "class11")
    db.session.commit()
    return jsonify({"added": len(added), "class_grade": "11", "section": section,
                    "academic_year": year, "students": added})


# ------------------------------------------------------------------ sections
SECTION_NAME = re.compile(r"^[A-Z0-9]{1,3}$")
MAX_SECTIONS = 10


def _section_target(user, data):
    """The trainer's lab and class a section change is about, checked."""
    if user.role != Role.TRAINER.value:
        abort(403, description="Only a trainer changes their lab's sections.")
    lab = db.session.get(Lab, data.get("lab_id")) if data.get("lab_id") else None
    if lab is None or lab.id not in {l.id for l in user.labs}:
        abort(400, description="Choose one of your labs.")
    class_grade = str(data.get("class_grade") or "")
    if class_grade not in REGISTRATION_CLASSES:
        abort(400, description="Select a class first.")
    job_role = lab.job_role_for(class_grade)
    if not job_role or class_grade not in allowed_class_grades(user, job_role):
        abort(400, description=f"Your lab doesn't run Class {class_grade}.")
    name = str(data.get("section") or "").strip().upper()
    if not SECTION_NAME.match(name):
        abort(400, description="A section is 1 to 3 letters or digits, e.g. C.")
    return lab, class_grade, name


def _save_sections(user, lab, class_grade, sections, what):
    before = lab.sections_for(class_grade)
    setattr(lab, f"sections_{class_grade}", ",".join(sections))
    lab.updated_by = user.id
    audit.record(user, "update", "lab", lab.id, before={f"sections_{class_grade}": before},
                 after={f"sections_{class_grade}": sections, "change": what})
    db.session.commit()
    return jsonify({"lab_id": str(lab.id), "class_grade": class_grade, "sections": sections})


@bp.post("/sections")
@login_required
def add_section():
    """A trainer adds a section to one class of their lab (Class 9 gets a 'C')."""
    user = current_user()
    lab, class_grade, name = _section_target(user, request.get_json(silent=True) or {})
    sections = lab.sections_for(class_grade)
    if name in sections:
        abort(400, description=f"Class {class_grade} already has Section {name}.")
    if len(sections) >= MAX_SECTIONS:
        abort(400, description=f"A class can have up to {MAX_SECTIONS} sections.")
    return _save_sections(user, lab, class_grade, sorted(sections + [name]), f"added {name}")


@bp.post("/<uid>/section")
@login_required
def move_to_section(uid):
    """Move a student to another section of the same class (e.g. to empty a
    section before removing it). They get the next roll number there."""
    user = current_user()
    s = db.session.get(Student, uid)
    if s is None or s.is_deleted:
        abort(404)
    data = request.get_json(silent=True) or {}
    lab, class_grade, name = _section_target(user, {**data, "lab_id": s.lab_id, "class_grade": s.class_grade})
    if s.enrolment_status != "Studying":
        abort(400, description=f"{s.full_name} is no longer studying here.")
    if name not in lab.sections_for(class_grade):
        abort(400, description=f"Class {class_grade} has no Section {name}.")
    if name == s.section:
        abort(400, description=f"{s.full_name} is already in Section {name}.")
    before = {"section": s.section, "roll_number": s.roll_number}
    (roll,), _ = _next_rolls(lab, class_grade, name, s.academic_year, 1)
    s.section, s.roll_number, s.updated_by = name, roll, user.id
    audit.record(user, "update", "student", s.id, before=before, after={"section": name, "roll_number": roll})
    db.session.commit()
    return jsonify({"id": str(s.id), "full_name": s.full_name, "section": name, "roll_number": roll})


@bp.post("/sections/remove")
@login_required
def remove_section():
    """Remove a section - only an empty one, and never a class's last."""
    user = current_user()
    lab, class_grade, name = _section_target(user, request.get_json(silent=True) or {})
    sections = lab.sections_for(class_grade)
    if name not in sections:
        abort(400, description=f"Class {class_grade} has no Section {name}.")
    if len(sections) == 1:
        abort(400, description="A class needs at least one section.")
    in_it = db.session.query(Student.id).filter(
        Student.lab_id == lab.id, Student.class_grade == class_grade, Student.section == name,
        Student.is_deleted.is_(False), Student.enrolment_status == "Studying").count()
    if in_it:
        abort(400, description=f"Section {name} still has {in_it} student{'s' if in_it != 1 else ''} "
                               "- move them to another section first.")
    return _save_sections(user, lab, class_grade, [x for x in sections if x != name], f"removed {name}")
