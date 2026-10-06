"""Who hears about what. Each function below is one event in the app; it
works out who should know (org admins, the school's principal, the trainer
who raised it) and leaves each of them a notification with a link to the
page where they can act. The person who caused the event is never told
about their own action. Called inside the request's transaction, so a
notification only exists if what it announces was saved.
"""
import uuid
from urllib.parse import parse_qsl, urlencode

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


def district_managers_of(school):
    """The district managers looking after this school's district."""
    if school is None or not school.district_id:
        return []
    from app.models.geography import District
    return _active(db.session.query(User).filter(
        User.organisation_id == school.organisation_id, User.role == "DM",
        User.districts.any(District.id == school.district_id))).all()


def resolvers_of(org_id, school):
    """Who can resolve an issue or a maintenance entry at this school: the
    org admins, and the district managers of its district."""
    return org_admins(org_id) + district_managers_of(school)


def super_admins():
    return _active(db.session.query(User).filter(User.role == "SA")).all()


def _issue_resolvers(issue, school, kind):
    """A principal's issue: the org admins and the district's managers. A
    trainer's: the org admins only (district managers don't see those)."""
    if kind == "vt":
        return org_admins(issue.organisation_id)
    return resolvers_of(issue.organisation_id, school)


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
    """A page, pre-filtered, pointing at the record itself. An admin's lists
    open on a school, so their links carry it (_district/_school, and _org for
    the super admin); `focus` is the record - the page opens where it is and
    flashes it. (`act` is kept for callers; the row's own buttons do the rest.)"""
    q = {k: v for k, v in params.items() if v not in (None, "")}
    if for_admin and school is not None:
        q["_school"] = str(school.id)
        if school.district_id:
            q["_district"] = str(school.district_id)
    if record is not None:
        q["focus"] = str(record.id)
    return f"/app/{path}" + (f"?{urlencode(q)}" if q else "")


# What an admin's list needs picked before it shows anything - mirrors
# ORG_ADMIN_SCOPE in frontend/src/lib/modules.js (the super admin also picks
# the organisation first, on every list but Organisations).
LIST_NEEDS = {"districts": "state", "schools": "district", "principals": "school", **{k: "school" for k in (
    "labs", "trainers", "students", "assessments", "attendance", "class-attendance", "principal-issues",
    "issues", "field-visits", "guest-lectures", "equipment", "equipment-maintenance", "ojt-placements")}}
ADMINS = ("SA", "OA", "DM")


def _school_of_record(resource, rec):
    """The school a record belongs to, however it's linked to one."""
    if resource == "schools":
        return rec
    sid = getattr(rec, "school_id", None) or getattr(rec, "linked_school_id", None)
    if sid:
        return _school(sid)
    if getattr(rec, "lab_id", None):
        return _school_of_lab(rec.lab_id)
    if getattr(rec, "equipment_id", None):
        from app.models.operations import LabEquipment
        eq = db.session.get(LabEquipment, rec.equipment_id)
        return _school(eq.school_id) if eq else None
    if getattr(rec, "student_id", None):
        from app.models.student import Student
        st = db.session.get(Student, rec.student_id)
        return _school(st.school_id) if st else None
    return None


def link_for(user, link):
    """The link a notification opens, made whole for `user` - however old the
    notification is. Links have changed shape over time (no record at all;
    then `_open`/`_act`; now `focus`), and an admin's list shows nothing until
    its organisation / state / district / school is picked. So the record is
    looked up and its place is filled in from it: every link opens the right
    list, on the right pick, at the record. (Stored links stay as they were.)"""
    if not link or not link.startswith("/app/"):
        return link
    path, _, qs = link.partition("?")
    q = dict(parse_qsl(qs))
    if "_open" in q:                                  # older links
        legacy = q.pop("_open")
        q.setdefault("focus", legacy)
    q.pop("_act", None)
    parts = path.strip("/").split("/")                # app/<resource> or app/master/<resource>
    resource = parts[2] if len(parts) > 2 and parts[1] == "master" else (parts[1] if len(parts) > 1 else "")
    rec = None
    if user.role in ADMINS and q.get("focus"):
        from app.api.registry import REGISTRY
        cfg = REGISTRY.get(resource)
        try:
            rec = db.session.get(cfg.model, uuid.UUID(q["focus"])) if cfg else None
        except (ValueError, TypeError):
            rec = None
    if resource == "students" and "tab" in q:
        # only the org admin's Students page has tabs (View / Verify / TC to
        # verify) - and a student verified since, or whose TC was checked,
        # is no longer on the tab the link named: open them on View
        tab = q["tab"]
        if user.role != "OA":
            q.pop("tab")
        elif rec is not None and ((tab == "verify" and rec.verification_status != "pending")
                                  or (tab == "leaving" and rec.leaving_stage != "tc_issued")):
            q["tab"] = "view"
    if rec is not None:
        if user.role == "SA" and resource != "organisations" and getattr(rec, "organisation_id", None):
            q["_org"] = str(rec.organisation_id)
        need = LIST_NEEDS.get(resource)
        if need == "state" and getattr(rec, "state_id", None):
            q["_state"] = str(rec.state_id)
        elif need == "district" and getattr(rec, "district_id", None):
            q["_district"] = str(rec.district_id)
        elif need == "school":
            school = _school_of_record(resource, rec)
            if school is not None:
                q["_school"] = str(school.id)
                if school.district_id:
                    q["_district"] = str(school.district_id)
    return path + (f"?{urlencode(q)}" if q else "")


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
    _send(_issue_resolvers(issue, school, kind), actor, org_id=issue.organisation_id,
          title=f"New issue from a {who}{_where(school)}",
          body=(issue.details or "")[:300], category="issue",
          link=_link("principal-issues" if kind == "pr" else "issues", school, True, record=issue, act="resolve",
                     workflow_status="open"))


def _org_issue_link(issue, status):
    """An org admin issue on the super admin's list: its organisation picked."""
    q = {"_org": str(issue.organisation_id), "workflow_status": status, "focus": str(issue.id)}
    return f"/app/org-issues?{urlencode(q)}"


def org_issue_raised(issue, actor):
    """An org admin raised one of their own issues: the super admin resolves it."""
    from app.models.organisation import Organisation
    org = db.session.get(Organisation, issue.organisation_id)
    _send(super_admins(), actor, org_id=issue.organisation_id,
          title=f"New issue from {actor.full_name if actor else 'an org admin'}" + (f" ({org.name})" if org else ""),
          body=(issue.details or "")[:300], category="issue",
          link=_org_issue_link(issue, "open"))


def close_resolver_notices(record, actor, note=""):
    """Resolved by one admin: every resolver's notification about it (org
    admins', district managers', or the super admins' for an org admin's
    own issue) now says so, opens the resolved list, and
    no longer waits to be read - nobody is left thinking it's still open."""
    who = actor.full_name if actor is not None else "an admin"
    notices = (db.session.query(Notification).join(User, User.id == Notification.user_id)
               .filter(User.role.in_(("SA", "OA", "DM")), Notification.link.like(f"%focus={record.id}%"),
                       Notification.category.in_(("issue", "maintenance"))).all())
    for n in notices:
        if not n.title.startswith("Resolved"):
            n.title = f"Resolved - {n.title}"[:200]
        n.body = (f"Resolved by {who}" + (f": {note}" if note else "."))[:300]
        n.link = (n.link or "").replace("workflow_status=open", "workflow_status=resolved")
        n.is_read = True


def issue_status_changed(issue, actor, kind, status):
    label = {"open": "Open", "in-progress": "In progress", "resolved": "Resolved"}.get(status, status)
    if kind == "oa":      # an org admin's own issue - the super admin resolves it
        if status == "resolved":
            close_resolver_notices(issue, actor, issue.resolution_note or "")
            _send(user_by_id(issue.raised_by), actor, org_id=issue.organisation_id,
                  title="Your issue has been resolved",
                  body=(issue.resolution_note or issue.details or "")[:300], category="issue",
                  link=_link("org-issues", record=issue, workflow_status="resolved"))
        else:
            _send(super_admins(), actor, org_id=issue.organisation_id,
                  title=f"Org admin issue is now {label}",
                  body=(issue.details or "")[:300], category="issue",
                  link=_org_issue_link(issue, status))
        return
    school = _school(issue.school_id) if kind == "pr" else _school_of_lab(issue.lab_id)
    path = "principal-issues" if kind == "pr" else "issues"
    if status == "resolved":
        close_resolver_notices(issue, actor, issue.resolution_note or "")
    else:   # opened again: the resolvers hear it's back
        _send(_issue_resolvers(issue, school, kind), actor, org_id=issue.organisation_id,
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
    _send(resolvers_of(rec.organisation_id, school), actor, org_id=rec.organisation_id,
          title=f"Maintenance needed: {name}{_where(school)}",
          body=(rec.issue or "")[:300], category="maintenance",
          link=_link("equipment-maintenance", school, True, record=rec, act="resolve"))


def maintenance_status_changed(rec, equipment, actor):
    """The trainer who logged it hears about every status change; once it's
    resolved, the other resolvers' notifications say so."""
    name = equipment.name if equipment else "Lab equipment"
    if rec.maintenance_status == "Resolved":
        close_resolver_notices(rec, actor, rec.action or "")
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
def students_to_verify(org_id, school_id, count, actor, why="added", first=None):
    """`first`: one of the students - the list opens on (and flashes) them."""
    school = _school(school_id)
    reason = {"added": "added", "class11": "moved into Class 11", "edited": "changed after verification"}[why]
    _send(org_admins(org_id), actor, org_id=org_id,
          title=f"{count} student{'s' if count != 1 else ''} to verify{_where(school)}",
          body=f"{count} student{'s were' if count != 1 else ' was'} {reason} and need{'' if count != 1 else 's'} verifying.",
          category="verification", link=_link("students", school, True, record=first, tab="verify"))


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


def attendance_verified_many(recs, actor, kind):
    """Several verified at once: each trainer hears once, for all of theirs."""
    by_trainer = {}
    for rec in recs:
        by_trainer.setdefault(rec.created_by or rec.trainer_id, []).append(rec)
    path = "attendance" if kind == "daily" else "class-attendance"
    for group in by_trainer.values():
        if len(group) == 1:
            attendance_verified(group[0], actor, kind)
            continue
        first = group[0]
        what = "daily attendance" if kind == "daily" else "class attendance"
        dates = ", ".join(dmy(r.date) for r in sorted(group, key=lambda r: r.date))
        _send(user_by_id(first.created_by) or trainer_user(first.trainer_id), actor, org_id=first.organisation_id,
              title=f"{len(group)} attendance records verified",
              body=f"Your {what} for {dates} was verified by the principal."[:300],
              category="attendance", link=_link(path, endorsement_status="endorsed"))


# ------------------------------------------------------------ super admin
PROFILE_ENTITIES = {"trainer_profile": "trainers", "principal_profile": "principals"}


def org_admin_action(actor, action, entity, entity_id, before, after):
    """The super admin hears what org admins do: every change an org admin
    makes (as the audit log records it), opening on the record itself."""
    from app.api.admin import ENTITY_NAMES, _record_name, _verb
    from app.api.registry import REGISTRY
    from app.models.organisation import Organisation
    if entity == "org_issue":     # told by org_issue_raised instead, as an issue to resolve
        return
    admins = super_admins()
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
            q["focus"] = str(rec.id)
        link = f"/app/{resource}?{urlencode(q)}"
    else:
        link = "/app/admin/audit"
    _send(admins, actor, org_id=actor.organisation_id,
          title=f"{actor.full_name} {_verb(action, after).lower()} {what}" + (f": {name}" if name else ""),
          body=f"Org Admin at {org.name}" if org else "Org Admin", category="admin", link=link)
