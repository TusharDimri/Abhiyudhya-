"""Who hears about what. Each function below is one event in the app; it
works out who should know (org admins, the school's principal, the trainer
who raised it) and leaves each of them a notification with a link to the
page where they can act. The person who caused the event is never told
about their own action. Called inside the request's transaction, so a
notification only exists if what it announces was saved.
"""
from urllib.parse import urlencode

from app.extensions import db
from app.models.geography import School
from app.models.lab import Lab, Trainer
from app.models.misc import Notification
from app.models.user import User

OA, PR, VT = "OA", "PR", "VT"


def dmy(d):
    """A date as the app shows it: DD/MM/YYYY."""
    return d.strftime("%d/%m/%Y") if d else "-"


# ------------------------------------------------------------ recipients
def _active(q):
    return q.filter(User.is_deleted.is_(False), User.status == "active")


def org_admins(org_id):
    return _active(db.session.query(User).filter(User.organisation_id == org_id, User.role == OA)).all()


def principals_of(school_id):
    if not school_id:
        return []
    return _active(db.session.query(User).filter(User.school_id == school_id, User.role == PR)).all()


def user_by_id(user_id):
    u = db.session.get(User, user_id) if user_id else None
    return [u] if u is not None and not u.is_deleted else []


def trainer_user(trainer_id):
    t = db.session.get(Trainer, trainer_id) if trainer_id else None
    return user_by_id(t.user_id) if t else []


# ---------------------------------------------------------------- helpers
def _school(school_id):
    return db.session.get(School, school_id) if school_id else None


def _school_of_lab(lab_id):
    lab = db.session.get(Lab, lab_id) if lab_id else None
    return _school(lab.school_id) if lab else None


def _link(path, school=None, for_admin=False, record=None, act="view", **params):
    """A page, pre-filtered, opening the record itself. An admin's lists open
    on a school, so their links carry it (_district/_school, and _org for the
    super admin); `record` + `act` open it (the page reads _open/_act)."""
    q = {k: v for k, v in params.items() if v not in (None, "")}
    if for_admin and school is not None:
        q["_school"] = str(school.id)
        if school.district_id:
            q["_district"] = str(school.district_id)
    if record is not None:
        q["_open"] = str(record.id)
        q["_act"] = act
    return f"/app/{path}" + (f"?{urlencode(q)}" if q else "")


def _send(recipients, actor, *, org_id, title, body, category, link):
    seen = set()
    for u in recipients:
        if u is None or u.id in seen or (actor is not None and u.id == actor.id):
            continue
        seen.add(u.id)
        db.session.add(Notification(organisation_id=org_id or u.organisation_id, user_id=u.id,
                                    title=title[:200], body=body, category=category, link=link, is_read=False))


def _where(school):
    return f" at {school.name}" if school else ""


# ------------------------------------------------------ org admin: issues
def issue_raised(issue, actor, kind):
    """A trainer's (kind='vt') or a principal's (kind='pr') issue was added."""
    school = _school(issue.school_id) if kind == "pr" else _school_of_lab(issue.lab_id)
    who = "principal" if kind == "pr" else "trainer"
    _send(org_admins(issue.organisation_id), actor, org_id=issue.organisation_id,
          title=f"New issue from a {who}{_where(school)}",
          body=(issue.details or "")[:300], category="issue",
          link=_link("principal-issues" if kind == "pr" else "issues", school, True, record=issue, act="resolve",
                     workflow_status="open"))


def issue_status_changed(issue, actor, kind, status):
    school = _school(issue.school_id) if kind == "pr" else _school_of_lab(issue.lab_id)
    label = {"open": "Open", "in-progress": "In progress", "resolved": "Resolved"}.get(status, status)
    path = "principal-issues" if kind == "pr" else "issues"
    _send(org_admins(issue.organisation_id), actor, org_id=issue.organisation_id,
          title=f"Issue{_where(school)} is now {label}",
          body=(issue.details or "")[:300], category="issue",
          link=_link(path, school, True, record=issue, workflow_status=status))
    if status == "resolved":      # whoever raised it: the principal, or the trainer
        raiser = user_by_id(issue.created_by) or (trainer_user(issue.trainer_id) if kind == "vt" else [])
        _send(raiser, actor, org_id=issue.organisation_id,
              title="Your issue has been resolved",
              body=(issue.resolution_note or issue.details or "")[:300], category="issue",
              link=_link(path, record=issue, workflow_status="resolved"))


# ------------------------------------------- org admin: equipment & upkeep
def maintenance_logged(rec, equipment, actor):
    school = _school(equipment.school_id) if equipment else None
    name = equipment.name if equipment else "Lab equipment"
    _send(org_admins(rec.organisation_id), actor, org_id=rec.organisation_id,
          title=f"Maintenance needed: {name}{_where(school)}",
          body=(rec.issue or "")[:300], category="maintenance",
          link=_link("equipment-maintenance", school, True, record=rec, act="resolve"))


def maintenance_status_changed(rec, equipment, actor):
    """The trainer who logged it hears about every status change."""
    name = equipment.name if equipment else "Lab equipment"
    _send(user_by_id(rec.created_by), actor, org_id=rec.organisation_id,
          title=f"{name}: {rec.maintenance_status}",
          body=(rec.action or rec.note or rec.issue or "")[:300], category="maintenance",
          link=_link("equipment-maintenance", record=rec))


def equipment_saved(eq, actor, created):
    school = _school(eq.school_id)
    _send(org_admins(eq.organisation_id), actor, org_id=eq.organisation_id,
          title=f"Lab equipment {'added' if created else 'updated'}: {eq.name or 'item'}{_where(school)}",
          body=(eq.details or eq.note or "")[:300],
          category="equipment", link=_link("equipment", school, True, record=eq))


# --------------------------------------------- org admin: students to verify
def students_to_verify(org_id, school_id, count, actor, why="added"):
    school = _school(school_id)
    reason = {"added": "added", "class11": "moved into Class 11", "edited": "changed after verification"}[why]
    _send(org_admins(org_id), actor, org_id=org_id,
          title=f"{count} student{'s' if count != 1 else ''} to verify{_where(school)}",
          body=f"{count} student{'s were' if count != 1 else ' was'} {reason} and need{'' if count != 1 else 's'} verifying.",
          category="verification", link=_link("students", school, True, tab="verify"))


# ------------------------------------------------ a student leaving the school
def student_leaving(s, actor):
    """Step 1 done: the principal is asked to issue the TC."""
    _send(principals_of(s.school_id), actor, org_id=s.organisation_id,
          title=f"{s.full_name} is leaving - TC needed",
          body=f"Class {s.class_grade} {s.section or ''} · {s.leaving_type}: {s.left_reason or ''}"[:300],
          category="leaving", link=_link("students", record=s, leaving_stage="requested"))


def tc_to_verify(s, actor):
    """Step 2 done: the org admins check the TC and confirm."""
    school = _school(s.school_id)
    _send(org_admins(s.organisation_id), actor, org_id=s.organisation_id,
          title=f"TC to verify: {s.full_name}{_where(school)}",
          body=f"Class {s.class_grade} {s.section or ''} · {s.leaving_type}" + (f" · TC {s.tc_number}" if s.tc_number else ""),
          category="leaving", link=_link("students", school, True, record=s, act="leftverify", tab="leaving"))


# ------------------------------------------------------------- principal
def attendance_submitted(rec, actor, kind):
    """kind: 'daily' or 'class'."""
    path = "attendance" if kind == "daily" else "class-attendance"
    what = "Daily attendance" if kind == "daily" else f"Class {rec.class_grade} attendance"
    _send(principals_of(rec.school_id), actor, org_id=rec.organisation_id,
          title=f"{what} to verify",
          body=f"{actor.full_name if actor else 'A trainer'} marked {what.lower()} for {dmy(rec.date)}.",
          category="attendance", link=_link(path, record=rec, endorsement_status="submitted"))


def guest_lecture_added(rec, actor):
    _send(principals_of(rec.school_id), actor, org_id=rec.organisation_id,
          title=f"Guest lecture added: {rec.topic or 'lecture'}",
          body=f"{rec.lecturer_name or 'A guest'} · Class {rec.class_grade or '-'} · {dmy(rec.reporting_date)}",
          category="guest_lecture", link=_link("guest-lectures", record=rec))


# --------------------------------------------------------------- trainer
def attendance_verified(rec, actor, kind):
    path = "attendance" if kind == "daily" else "class-attendance"
    what = "daily attendance" if kind == "daily" else f"Class {rec.class_grade} attendance"
    _send(user_by_id(rec.created_by) or trainer_user(rec.trainer_id), actor, org_id=rec.organisation_id,
          title="Attendance verified",
          body=f"Your {what} for {dmy(rec.date)} was verified by the principal.",
          category="attendance", link=_link(path, record=rec, endorsement_status="endorsed"))


# ------------------------------------------------------------ super admin
PROFILE_ENTITIES = {"trainer_profile": "trainers", "principal_profile": "principals"}


def org_admin_action(actor, action, entity, entity_id, before, after):
    """The super admin hears what org admins do: every change an org admin
    makes (as the audit log records it), opening on the record itself."""
    from app.api.admin import ENTITY_NAMES, _record_name, _verb
    from app.api.registry import REGISTRY
    from app.models.organisation import Organisation
    admins = _active(db.session.query(User).filter(User.role == "SA")).all()
    if not admins or actor is None:
        return
    org = db.session.get(Organisation, actor.organisation_id) if actor.organisation_id else None
    what = ENTITY_NAMES.get(entity, entity.replace("_", " "))
    name = _record_name(entity, entity_id, before, after)

    # where it lives: its list, on its organisation (and school)
    resource = PROFILE_ENTITIES.get(entity) or next(
        (n for n, c in REGISTRY.items() if c.model.__tablename__ == entity), None)
    if entity == "app_user":
        link = "/app/admin/users"
    elif resource:
        cfg = REGISTRY[resource]
        rec = db.session.get(cfg.model, entity_id) if entity_id else None
        school_id = None
        if rec is not None:
            school_id = (getattr(rec, "school_id", None) or getattr(rec, "linked_school_id", None)
                         or (_school_of_lab(rec.lab_id).id if getattr(rec, "lab_id", None) and _school_of_lab(rec.lab_id) else None))
            if entity == "school":
                school_id = rec.id
        school = _school(school_id)
        q = {"_org": str(actor.organisation_id)} if actor.organisation_id else {}
        if school is not None:
            q["_school"] = str(school.id)
            if school.district_id:
                q["_district"] = str(school.district_id)
        if rec is not None:
            q["_open"], q["_act"] = str(rec.id), "view"
        link = f"/app/{resource}?{urlencode(q)}"
    else:
        link = "/app/admin/audit"
    _send(admins, actor, org_id=actor.organisation_id,
          title=f"{actor.full_name} {_verb(action, after).lower()} {what}" + (f": {name}" if name else ""),
          body=f"Org Admin at {org.name}" if org else "Org Admin", category="admin", link=link)
