"""Yearly targets per level - how many guest lectures / field visits each lab
has held for each level in an academic year, against what is required.

    15 guest lectures per level per year
     2 field visits    per level per year

Level follows class: Class 9 is Level 1 ... Class 12 is Level 4. A lab only
has the levels its job-role slots cover (a 9-10-only lab has Levels 1-2).
One record counts once for its class, however many sections attended it.
"""
from datetime import date

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import func

from app.extensions import db
from app.models.geography import School
from app.models.lab import Lab
from app.models.masters import AcademicYear
from app.models.operations import FieldVisit, GuestLecture
from app.rbac import apply_scope, current_user, login_required
from app.services.academic_year import academic_year_for
from app.services.cache import cached_json

bp = Blueprint("targets", __name__, url_prefix="/api/targets")

TARGETS = {
    "guest-lectures": {"model": GuestLecture, "target": 15, "noun": "guest lectures"},
    "field-visits": {"model": FieldVisit, "target": 2, "noun": "field visits"},
}

LEVEL_OF_CLASS = {"9": 1, "10": 2, "11": 3, "12": 4}


def _classes_of(lab):
    classes = []
    if lab.job_role_9_10_id:
        classes += ["9", "10"]
    if lab.job_role_11_12_id:
        classes += ["11", "12"]
    return classes or ["9", "10", "11", "12"]


@bp.get("/<resource>")
@login_required
@cached_json("progress", ttl=120)
def progress(resource):
    cfg = TARGETS.get(resource)
    if not cfg:
        abort(404)
    user = current_user()
    model, target = cfg["model"], cfg["target"]

    labs_q = db.session.query(Lab).filter(Lab.is_deleted.is_(False))
    if request.args.get("lab_id"):
        labs_q = labs_q.filter(Lab.id == request.args["lab_id"])
    if request.args.get("school_id"):   # an org admin looks at one school at a time
        labs_q = labs_q.filter(Lab.school_id == request.args["school_id"])
    labs = apply_scope(labs_q, Lab, user).order_by(Lab.name).all()
    lab_ids = [lab.id for lab in labs]
    schools = {
        s.id: s.name for s in db.session.query(School).filter(School.id.in_({l.school_id for l in labs} or [None]))
    }

    counts_q = db.session.query(
        model.lab_id, model.academic_year, model.class_grade, func.count(model.id)
    ).filter(model.is_deleted.is_(False), model.lab_id.in_(lab_ids or [None]))
    counts_q = apply_scope(counts_q, model, user).group_by(model.lab_id, model.academic_year, model.class_grade)
    counts = {(str(lab), ay, str(cls)): n for lab, ay, cls, n in counts_q.all()}

    # the years there is anything to say about: set up, or with records
    this_year = academic_year_for(user.organisation_id, date.today())
    set_up = [
        ay for (ay,) in apply_scope(
            db.session.query(AcademicYear.label).filter(AcademicYear.is_deleted.is_(False)), AcademicYear, user
        ).all()
    ]
    years = sorted({this_year, *set_up, *(ay for (_, ay, _) in counts if ay)}, reverse=True)

    wanted = request.args.get("academic_year") or this_year
    show_years = years if wanted == "all" else [wanted]
    status = request.args.get("status")  # met | not_met | (all)

    rows = []
    for ay in show_years:
        for lab in labs:
            for cls in _classes_of(lab):
                n = counts.get((str(lab.id), ay, cls), 0)
                met = n >= target
                if (status == "met" and not met) or (status == "not_met" and met):
                    continue
                rows.append({
                    "academic_year": ay, "lab_id": str(lab.id), "lab_name": lab.name,
                    "school_name": schools.get(lab.school_id),
                    "class_grade": cls, "level": LEVEL_OF_CLASS[cls],
                    "count": n, "target": target, "met": met, "remaining": max(target - n, 0),
                })

    return jsonify({
        "target": target, "noun": cfg["noun"], "years": years, "academic_year": wanted,
        "current_year": this_year, "rows": rows,
    })
