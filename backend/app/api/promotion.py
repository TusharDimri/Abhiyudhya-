"""End-of-year promotion, and a student leaving or rejoining.

Promotion moves a class up a year, once that year has ended:

    Class 9  -> Class 10
    Class 10 -> Class 11   (if the lab runs 11-12; otherwise the course is Completed)
    Class 11 -> Class 12
    Class 12 -> Completed

Each student is either promoted or held back (repeats the class next year).
Only verified students still studying are moved, and each outcome is kept in
student_promotion - the history behind a student's current class and year.
"""
from datetime import date

from flask import Blueprint, abort, jsonify, request

from app.extensions import db
from app.models.lab import Lab
from app.models.masters import JobRole
from app.models.student import Student, StudentPromotion
from app.rbac import apply_scope, can_access_row, current_user, login_required
from app.rbac.roles import Role
from app.services import audit
from app.services.academic_year import next_year_label, year_bounds, year_has_ended
from app.services.cache import cached_json
from app.services.cache import cached_json

bp = Blueprint("promotion", __name__, url_prefix="/api/promotion")

MANAGERS = {Role.TRAINER.value, Role.DISTRICT_MANAGER.value, Role.ORG_ADMIN.value, Role.SUPER_ADMIN.value}
NEXT_CLASS = {"9": "10", "10": "11", "11": "12", "12": None}
LEAVING = {"Dropped Out", "Transferred Out"}


def _user():
    user = current_user()
    if user.role not in MANAGERS:
        abort(403, description="You cannot promote students")
    return user


def _studying(user):
    q = db.session.query(Student).filter(
        Student.is_deleted.is_(False), Student.enrolment_status == "Studying"
    )
    return apply_scope(q, Student, user)


def _to_class(student, lab):
    """The class a student moves to, or None when they complete the course."""
    nxt = NEXT_CLASS.get(str(student.class_grade))
    if nxt == "11" and not (lab and lab.job_role_11_12_id):
        return None  # a 9-10-only lab: Class 10 finishes the course here
    return nxt


def _candidates(user, from_year, class_grade, sections):
    q = _studying(user).filter(Student.academic_year == from_year,
                               Student.class_grade == str(class_grade))
    if sections:
        q = q.filter(Student.section.in_(sections))
    return q.order_by(Student.section, Student.roll_number, Student.first_name).all()


def _sections_arg(value):
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    return [s.strip() for s in str(value or "").split(",") if s.strip()]


@bp.get("/options")
@login_required
@cached_json("options", ttl=120)
def options():
    """The year + class groups a trainer could promote, with how many
    students each holds and whether that year has ended."""
    user = _user()
    rows = (
        _studying(user)
        .with_entities(Student.academic_year, Student.class_grade, db.func.count(Student.id))
        .filter(Student.academic_year.isnot(None), Student.class_grade.isnot(None))
        .group_by(Student.academic_year, Student.class_grade)
        .all()
    )
    groups = []
    for ay, cls, n in rows:
        bounds = year_bounds(user.organisation_id, ay)
        groups.append({
            "academic_year": ay, "class_grade": str(cls), "students": n,
            "ended": year_has_ended(user.organisation_id, ay),
            "ends_on": bounds[1].isoformat() if bounds else None,
            "to_year": next_year_label(user.organisation_id, ay),
        })
    groups.sort(key=lambda g: (g["academic_year"], int(g["class_grade"])), reverse=False)
    return jsonify({"groups": groups})


@bp.get("/preview")
@login_required
@cached_json("preview", ttl=120)
def preview():
    user = _user()
    from_year = request.args.get("from_year")
    class_grade = request.args.get("class_grade")
    if not from_year or class_grade not in NEXT_CLASS:
        abort(400, description="Choose the year and class to promote.")
    students = _candidates(user, from_year, class_grade, _sections_arg(request.args.get("sections")))
    labs = {l.id: l for l in db.session.query(Lab).filter(Lab.id.in_({s.lab_id for s in students} or [None]))}
    out = []
    for s in students:
        lab = labs.get(s.lab_id)
        to_class = _to_class(s, lab)
        new_role = lab.job_role_for(to_class) if (lab and to_class) else None
        out.append({
            "id": str(s.id), "full_name": s.full_name, "roll_number": s.roll_number, "section": s.section,
            "verification_status": s.verification_status,
            "eligible": s.verification_status == "verified",
            "reason": None if s.verification_status == "verified" else "Verify this student first",
            "to_class": to_class,
            "to_job_role": db.session.get(JobRole, new_role).name if new_role else None,
        })
    bounds = year_bounds(user.organisation_id, from_year)
    return jsonify({
        "from_year": from_year, "to_year": next_year_label(user.organisation_id, from_year),
        "class_grade": class_grade,
        "ended": year_has_ended(user.organisation_id, from_year),
        "ends_on": bounds[1].isoformat() if bounds else None,
        "students": out,
    })


@bp.post("")
@login_required
def promote():
    """Body: {from_year, class_grade, sections?, promote: [ids], hold_back: [ids]}.
    Students in neither list are left as they are."""
    user = _user()
    data = request.get_json(silent=True) or {}
    from_year, class_grade = data.get("from_year"), str(data.get("class_grade") or "")
    if not from_year or class_grade not in NEXT_CLASS:
        abort(400, description="Choose the year and class to promote.")
    if not year_has_ended(user.organisation_id, from_year):
        bounds = year_bounds(user.organisation_id, from_year)
        ends = f" (it ends on {bounds[1]:%d/%m/%Y})" if bounds else ""
        abort(400, description=f"Students can be promoted once {from_year} has ended{ends}.")
    to_year = next_year_label(user.organisation_id, from_year)
    if not to_year:
        abort(400, description=f"Can't work out the year after {from_year}.")

    up = {str(x) for x in data.get("promote") or []}
    back = {str(x) for x in data.get("hold_back") or []}
    if up & back:
        abort(400, description="A student can't be both promoted and held back.")
    candidates = {str(s.id): s for s in _candidates(user, from_year, class_grade, _sections_arg(data.get("sections")))}
    unknown = (up | back) - set(candidates)
    if unknown:
        abort(400, description="Some students aren't in this class and year any more - reload and try again.")
    unverified = [candidates[i].full_name for i in up | back if candidates[i].verification_status != "verified"]
    if unverified:
        abort(400, description="Verify these students first: " + ", ".join(sorted(unverified)))
    if not (up or back):
        abort(400, description="Choose at least one student.")

    labs = {l.id: l for l in db.session.query(Lab).filter(Lab.id.in_({s.lab_id for s in candidates.values()} or [None]))}
    counts = {"Promoted": 0, "Held Back": 0, "Completed": 0}
    for sid in sorted(up | back):
        s = candidates[sid]
        before = {"class_grade": s.class_grade, "academic_year": s.academic_year,
                  "enrolment_status": s.enrolment_status}
        # the year that is ending, kept whole before anything below changes it
        was = dict(from_roll_number=s.roll_number, from_job_role_id=s.job_role_id, from_lab_id=s.lab_id,
                   from_school_id=s.school_id, from_verification_status=s.verification_status,
                   from_enrolment_status=s.enrolment_status, snapshot=s.to_dict(),
                   section=s.section)
        if sid in back:
            outcome, to_class = "Held Back", s.class_grade
            s.academic_year = to_year
        else:
            lab = labs.get(s.lab_id)
            to_class = _to_class(s, lab)
            if to_class is None:
                outcome = "Completed"
                s.enrolment_status = "Completed"
                s.left_on = date.today()
                s.left_reason = f"Completed Class {s.class_grade} ({from_year})"
            else:
                outcome = "Promoted"
                if to_class == "11":
                    # carrying on with the same trade into 11-12
                    s.had_vocational_9_10 = True
                    s.continuing_same_trade = True
                s.class_grade = to_class
                s.academic_year = to_year
                if lab:
                    s.job_role_id = lab.job_role_for(to_class)
        db.session.add(StudentPromotion(
            organisation_id=s.organisation_id, student_id=s.id,
            from_academic_year=from_year, to_academic_year=None if outcome == "Completed" else to_year,
            from_class=class_grade, to_class=None if outcome == "Completed" else to_class,
            outcome=outcome, created_by=user.id, **was,
        ))
        counts[outcome] += 1
        audit.record(user, "update", "student", s.id, before=before, after={
            "class_grade": s.class_grade, "academic_year": s.academic_year,
            "enrolment_status": s.enrolment_status, "promotion": outcome,
        })
    db.session.commit()
    return jsonify({"to_year": to_year, **{k.lower().replace(" ", "_"): v for k, v in counts.items()}})


@bp.get("/history/<uid>")
@login_required
@cached_json("promotion_history", ttl=120)
def history(uid):
    """A student's years: where they are now, then each year that ended, as
    it was logged when they were promoted, held back or completed."""
    from app.models.lab import Lab
    from app.models.user import User
    user = current_user()
    s = db.session.get(Student, uid)
    if s is None or s.is_deleted or not can_access_row(s, user):
        abort(404)
    rows = (
        db.session.query(StudentPromotion)
        .filter(StudentPromotion.student_id == s.id, StudentPromotion.is_deleted.is_(False))
        .order_by(StudentPromotion.created_at.desc())
        .all()
    )
    name = lambda model, pk, attr="name": getattr(db.session.get(model, pk), attr, None) if pk else None  # noqa: E731
    return jsonify({
        "student": {"id": str(s.id), "full_name": s.full_name},
        "current": {
            "academic_year": s.academic_year, "class_grade": s.class_grade, "section": s.section,
            "roll_number": s.roll_number, "job_role": name(JobRole, s.job_role_id),
            "lab": name(Lab, s.lab_id), "enrolment_status": s.enrolment_status,
            "verification_status": s.verification_status,
        },
        "years": [{
            "academic_year": r.from_academic_year, "class_grade": r.from_class, "section": r.section,
            "roll_number": r.from_roll_number, "job_role": name(JobRole, r.from_job_role_id),
            "lab": name(Lab, r.from_lab_id), "verification_status": r.from_verification_status,
            "outcome": r.outcome, "to_academic_year": r.to_academic_year, "to_class": r.to_class,
            "recorded_on": r.created_at.isoformat() if r.created_at else None,
            "recorded_by": name(User, r.created_by, "full_name"),
            "snapshot": r.snapshot,
        } for r in rows],
    })


@bp.post("/students/<uid>/status")
@login_required
def change_status(uid):
    """A student leaves (dropped out / transferred out) or rejoins.
    Body: {enrolment_status, date?, reason?}. Completing the course happens
    through promotion only."""
    user = _user()
    s = db.session.get(Student, uid)
    if s is None or s.is_deleted:
        abort(404)
    if not can_access_row(s, user):
        abort(403, description="Outside your scope")
    data = request.get_json(silent=True) or {}
    status = data.get("enrolment_status")
    if status not in LEAVING | {"Studying"}:
        abort(400, description="Status must be Dropped Out, Transferred Out or Studying.")
    before = {"enrolment_status": s.enrolment_status, "left_on": str(s.left_on or ""), "left_reason": s.left_reason}
    if status in LEAVING:
        if s.enrolment_status != "Studying":
            abort(400, description=f"{s.full_name} is already marked {s.enrolment_status}.")
        try:
            when = date.fromisoformat(str(data.get("date"))[:10]) if data.get("date") else date.today()
        except ValueError:
            abort(400, description="Enter the date as a real date.")
        if when > date.today():
            abort(400, description="The date can't be in the future.")
        if not (data.get("reason") or "").strip():
            abort(400, description="Give a short reason.")
        s.left_on, s.left_reason = when, data["reason"].strip()
    else:
        if s.enrolment_status not in LEAVING:
            abort(400, description=f"{s.full_name} is {s.enrolment_status.lower()} - only a student who left can rejoin.")
        if s.enrolment_status == "Transferred Out":
            abort(400, description=f"{s.full_name} was transferred out to another school and can't rejoin here.")
        s.left_on, s.left_reason = None, None
    s.enrolment_status = status
    s.updated_by = user.id
    audit.record(user, "update", "student", s.id, before=before,
                 after={"enrolment_status": status, "left_on": str(s.left_on or ""), "left_reason": s.left_reason})
    db.session.commit()
    return jsonify({"id": str(s.id), "enrolment_status": status})
