"""A complete demo site: every role, several schools, a year and a bit of work.

    flask db upgrade        (an empty PostgreSQL database with PostGIS)
    flask seed-demo

Builds on `flask seed` (the demo organisation and its first logins) and adds:

  * a second organisation, so the Super Admin sees more than one
  * users of every role - Super Admin, Org Admins, District Managers, and a
    Principal and two Vocational Trainers (9-10 and 11-12) for every school
  * seven schools (four in the demo organisation, the three location-test
    schools from `flask test-schools`), each with its location and a lab
  * for every lab: students in Classes 9-12 (with promotion history, a few
    pending verification, one dropped out and one transferred), daily and
    class attendance since this school year began (mostly verified), guest
    lectures and field visits for last year and this (some levels meeting
    their yearly target, some not), trainer and principal issues, lab
    equipment and its maintenance log, assessments, OJT for Class 12,
    employers with student mappings and diaries, and feedback
  * filled-in profiles for every trainer and principal

Everything is fictional (Aadhaar numbers all start 9999). Dates are worked out
from the day it runs, so the data always looks current. Running it again adds
nothing: every school, user and lab's activity is created only once.
"""
import json
import math
import random
import uuid
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models.geo import point_to_latlng, point_wkt
from app.models.geography import District, Principal, School, State
from app.models.internship import DailyDiary, Employer, EmployerStudentMap, OJTPlacement
from app.models.lab import Lab, Trainer
from app.models.masters import AcademicYear, JobRole, Sector, SocialCategory
from app.models.misc import AuditLog, Feedback, Notification
from app.models.operations import (
    ClassAttendance, ClassAttendanceStudentMark, DailyAttendance, EquipmentMaintenance, FieldVisit,
    FieldVisitStudentMark, GuestLecture, GuestLectureStudentMark, LabEquipment, OrgIssue, PrincipalIssue, VTIssue,
)
from app.models.organisation import Organisation
from app.models.student import Assessment, Student, StudentPromotion
from app.models.trainer_profile import (
    PrincipalPosting, PrincipalQualification, PrincipalTraining,
    TrainerExperience, TrainerPosting, TrainerQualification, TrainerTraining,
)
from app.models.user import User
from app.services.academic_year import academic_year_for

PASSWORD = "Password@123"
R = random.Random(2026)            # same data on every machine


# ============================================================== reference data
FIRST_M = ["Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Reyansh", "Krishna", "Ishaan", "Rohan", "Kabir",
           "Omkar", "Pranav", "Siddharth", "Harsh", "Yash", "Atharva", "Vedant", "Soham", "Tejas", "Aniket"]
FIRST_F = ["Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Pari", "Anika", "Navya", "Riya",
           "Tanvi", "Sneha", "Pooja", "Neha", "Aditi", "Gauri", "Shravani", "Sakshi", "Mrunal", "Isha"]
LAST = ["Patil", "Deshmukh", "Joshi", "Kulkarni", "Pawar", "Shinde", "More", "Jadhav", "Gaikwad", "Chavan",
        "Kale", "Bhosale", "Sawant", "Salunkhe", "Mane", "Shaikh", "Pathan", "Nair", "Iyer", "Rao",
        "Gowda", "Hegde", "Shetty", "Naik", "Kamat"]
ACTIVITIES = {
    "IT": {
        "9": ["Practical: keyboard layout and typing drill", "Theory: parts of a computer",
              "Practical: files and folders", "Theory: data entry accuracy", "Revision and oral quiz"],
        "10": ["Practical: formatting a document", "Theory: data privacy and backups",
               "Practical: sorting and filtering a spreadsheet", "Mock test: data entry speed", "Practical: mail merge"],
        "11": ["Theory: variables, loops and conditions", "Practical: first Python programs",
               "Practical: debugging", "Theory: introduction to databases", "Practical: simple SQL queries"],
        "12": ["Practical: building a web page", "Theory: version control with Git", "Practical: CRUD mini project",
               "Mock practical exam", "Project review and viva practice"],
    },
    "AUTO": {
        "9": ["Theory: parts of a two-wheeler", "Practical: tools and safety", "Practical: tyre pressure and puncture repair",
              "Theory: fuel system basics", "Revision and oral quiz"],
        "10": ["Practical: chain and sprocket adjustment", "Theory: braking systems", "Practical: battery checks",
               "Practical: oil change", "Mock practical test"],
        "11": ["Theory: four-stroke engine", "Practical: engine tune-up", "Practical: electrical wiring",
               "Theory: transmission", "Practical: wheel alignment basics"],
        "12": ["Practical: diagnosing with a scan tool", "Theory: service records", "Practical: full service job card",
               "Mock practical exam", "Workshop project review"],
    },
}
TOPICS = {
    "IT": {"9": ["Careers in data entry", "Staying safe online"], "10": ["Spreadsheets at work", "Digital payments"],
           "11": ["A day as a software developer", "Intro to open source"], "12": ["Preparing for IT interviews", "Cloud basics"]},
    "AUTO": {"9": ["Careers in auto service", "Road safety"], "10": ["How a service centre works", "EV basics"],
             "11": ["Modern engine diagnostics", "Customer handling"], "12": ["Starting a garage", "Electric vehicles"]},
}
LECTURERS = [
    ("Dr. Meera Rao", "PhD Computer Science", "meera.rao@example.com", "9812300001", "15 years, university faculty"),
    ("Rahul Mehta", "B.E. Computer Engineering", "rahul.mehta@example.com", "9812300002", "8 years, software developer"),
    ("Sunita Kulkarni", "MCA", "sunita.k@example.com", "9812300003", "10 years, IT trainer"),
    ("Anil Deshpande", "Diploma in Automobile Engg.", "anil.d@example.com", "9812300004", "12 years, service centre head"),
    ("Farah Sheikh", "M.Sc. Data Science", "farah.s@example.com", "9812300005", "6 years, data analyst"),
    ("Vikram Nair", "B.Tech Mechanical", "vikram.nair@example.com", "9812300006", "9 years, automotive engineer"),
]
ORGS = [
    ("Sahyadri Data Services", "Plot 12, Hinjewadi Phase 1, Pune", "Kiran Joshi", "HR Manager", "hr@sahyadri-data.example", "9822000011"),
    ("Deccan Softlabs", "3rd Floor, Baner Road, Pune", "Ritu Kapoor", "Training Head", "training@deccansoft.example", "9822000012"),
    ("City Motors Service Centre", "MIDC Area", "Sachin More", "Works Manager", "works@citymotors.example", "9822000013"),
    ("District Bank Data Centre", "Station Road", "Mahesh Pawar", "Operations Lead", "ops@distbank.example", "9822000014"),
    ("Railway Reservation Office", "Railway Station", "A. Qureshi", "Station Manager", "prs@railway.example", "9822000015"),
]
VT_ISSUES = [("Two computers do not start", "resolved"), ("Internet very slow in the lab", "in-progress"),
             ("Projector bulb fused", "resolved"), ("One socket sparks - needs an electrician", "open"),
             ("Textbooks for Class 11 not received", "in-progress"), ("Field visit travel bill pending", "open")]
PR_ISSUES = [("Lab room roof leaks during rain", "open"), ("Need a second trainer for Class 11-12", "open"),
             ("Electricity bill for the lab not reimbursed", "in-progress"),
             ("Boundary wall near the lab is damaged", "in-progress"),
             ("Lab furniture delivered short by 5 benches", "resolved"),
             ("Trainer salary for last month is pending", "resolved")]
# an org admin's own issues ("My Issues") - the super admin resolves them
OA_ISSUES = [("Funds for the second-term lab consumables have not been released", "open", None),
             ("Need approval to add two schools in the new district", "open", None),
             ("Board exam fee portal is not accepting our trainers' logins", "resolved",
              "Portal access restored with the board; trainers can log in again")]
EQUIPMENT = {
    "IT": [("Desktop computers (1-10)", "10 desktops with keyboards and mice"), ("Desktop computers (11-20)", "10 desktops"),
           ("LCD projector", "Ceiling mounted, with screen"), ("Laser printer", "Mono, A4"), ("UPS 5 kVA", "Whole-lab backup"),
           ("Wi-Fi router", "Dual band"), ("Network switch", "24 ports")],
    "AUTO": [("Two-wheeler training model", "Cut-section engine on stand"), ("Tool kit (set of 10)", "Spanners, sockets, screwdrivers"),
             ("Air compressor", "With tyre inflator"), ("Battery tester", "Digital"), ("Hydraulic jack", "2 ton"),
             ("Wheel balancer", "Bench type"), ("Projector", "For theory classes")],
}
MAINTENANCE = [(0, "Two units not starting", "Resolved"), (2, "Needs a replacement part", "Under Progress"),
               (3, "Faded output / weak reading", "Under Progress"), (4, "Battery backup under 5 minutes", "Under Progress"),
               (5, "Drops connection every hour", "Reported")]
HOLIDAY_DAYS = {(8, 15), (10, 2), (1, 26), (11, 1)}   # (month, day) - national holidays and one festival day

# The demo organisation's schools (the first two come from `flask seed`)
RNAF_SCHOOLS = [
    # key, school, district, lat, lng, type, lab name, sector, size
    ("pune", "Govt High School Pune", "Pune", 18.5204, 73.8567, "Co-education", None, "IT", "big"),
    ("nagpur", "Govt High School Nagpur", "Nagpur", 21.1458, 79.0882, "Boys", None, "IT", "small"),
    ("nashik", "Govt Secondary School Nashik", "Nashik", 19.9975, 73.7898, "Girls", "IT Lab - Nashik", "IT", "small"),
    ("kolhapur", "Govt High School Kolhapur", "Kolhapur", 16.7050, 74.2433, "Co-education", "Automotive Lab - Kolhapur", "AUTO", "small"),
]
SIZES = {"big": {"9": 8, "10": 7, "11": 9, "12": 7}, "small": {"9": 6, "10": 5, "11": 6, "12": 5}}


# ================================================================== helpers
class Clock:
    """The school years, worked out from the day the seed runs."""

    def __init__(self, today=None):
        self.today = today or date.today()
        y = self.today.year if self.today.month >= 6 else self.today.year - 1
        self.start_year = y
        self.this_label = f"{y}-{(y + 1) % 100:02d}"
        self.last_label = f"{y - 1}-{y % 100:02d}"
        self.this_span = (date(y, 6, 15), self.today - timedelta(days=1))
        self.last_span = (date(y - 1, 6, 16), date(y, 4, 25))

    def school_days(self, start, end):
        d = start
        while d <= end:
            if d.weekday() < 6 and (d.month, d.day) not in HOLIDAY_DAYS:
                yield d
            d += timedelta(days=1)


def _phone():
    return f"9{R.randint(100000000, 999999999)}"


def _near(lat, lng, max_m=450, min_m=15):
    d, bearing = R.uniform(min_m, max_m), R.uniform(0, 2 * math.pi)
    return (lat + d * math.cos(bearing) / 111_320,
            lng + d * math.sin(bearing) / (111_320 * math.cos(math.radians(lat))), round(d, 1))


def _stamp(rec, school_latlng, when, distance=True):
    """Where the device was: mostly at the school (green, up to 750 m), now
    and then 751-980 m out (yellow) - never past the 1 km the app accepts."""
    far = R.random() < 0.15
    lat, lng, dist = _near(*school_latlng, min_m=760, max_m=980) if far else _near(*school_latlng, max_m=700)
    rec.set_location(lat, lng, round(R.uniform(8, 40), 1), when)
    if distance:
        rec.distance_from_school_m = dist


def _verified(day, today):
    return "submitted" if (today - day).days <= 5 else R.choices(["endorsed", "submitted"], weights=[92, 8])[0]


def _user(org, name, email, role, **scope):
    u = db.session.query(User).filter_by(email=email).first()
    if u is None:
        u = User(organisation_id=org.id if org else None, full_name=name, email=email, role=role, **scope)
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.flush()
    return u


class Counter:
    """Unique admission / Aadhaar numbers across the whole seed."""

    def __init__(self):
        self.n = 0
        taken = db.session.query(Student.aadhaar_number).filter(Student.aadhaar_number.like("9999%")).all()
        self.used = {t[0] for t in taken}

    def aadhaar(self):
        while True:
            self.n += 1
            a = f"9999{(self.n * 7919 + 12345) % 100_000_000:08d}"
            if a not in self.used:
                self.used.add(a)
                return a


# ======================================================= organisations + years
def _ensure_years(org, clock):
    """This school year and last, set up June to April; this one is current."""
    for label, start in ((clock.last_label, clock.start_year - 1), (clock.this_label, clock.start_year)):
        ay = db.session.query(AcademicYear).filter_by(organisation_id=org.id, label=label).first()
        if ay is None:
            ay = AcademicYear(organisation_id=org.id, label=label, start_date=date(start, 6, 1),
                              end_date=date(start + 1, 4, 30))
            db.session.add(ay)
        ay.is_current = label == clock.this_label
    for ay in db.session.query(AcademicYear).filter(AcademicYear.organisation_id == org.id,
                                                    AcademicYear.label != clock.this_label):
        ay.is_current = False


def _masters(org):
    """Sectors, job roles and categories an organisation needs (created once)."""
    def sector(name, code):
        s = db.session.query(Sector).filter_by(organisation_id=org.id, name=name).first()
        if s is None:
            s = Sector(organisation_id=org.id, name=name, code=code)
            db.session.add(s)
            db.session.flush()
        return s

    def role(name, sec, qp, level, band):
        j = db.session.query(JobRole).filter_by(organisation_id=org.id, name=name).first()
        if j is None:
            j = JobRole(organisation_id=org.id, name=name, sector_id=sec.id, qp_code=qp, nsqf_level=level, class_band=band)
            db.session.add(j)
            db.session.flush()
        return j

    it, auto = sector("IT/ITeS", "IT"), sector("Automotive", "AUTO")
    roles = {
        "IT": (role("Domestic Data Entry Operator", it, "SSC/Q0212", 2, "9-10"),
               role("Junior Software Developer", it, "SSC/Q0508", 4, "11-12")),
        "AUTO": (role("Automotive Service Assistant", auto, "ASC/Q1401", 2, "9-10"),
                 role("Automotive Service Technician", auto, "ASC/Q1402", 4, "11-12")),
    }
    for cat in ["General", "SC", "ST", "OBC", "VJ", "SBC", "NT-B", "NT-C", "NT-D"]:
        if not db.session.query(SocialCategory).filter_by(organisation_id=org.id, name=cat).first():
            db.session.add(SocialCategory(organisation_id=org.id, name=cat))
    db.session.flush()
    return {"IT": it, "AUTO": auto}, roles


def _second_org():
    org = db.session.query(Organisation).filter_by(org_code="SAHYOG-DEMO").first()
    if org is None:
        org = Organisation(name="Sahyog Skills Foundation", legal_name="Sahyog Skills Foundation (demo)",
                           org_code="SAHYOG-DEMO", primary_contact_name="Admin",
                           primary_contact_email="oa@sahyog.demo", primary_contact_phone="9888888888")
        db.session.add(org)
        db.session.flush()
    return org


# ========================================================== schools + people
def _school(org, state, district_name, name, lat, lng, kind, udise):
    district = db.session.query(District).filter_by(organisation_id=org.id, name=district_name).first()
    if district is None:
        district = District(organisation_id=org.id, state_id=state.id, name=district_name, code=district_name[:3].upper())
        db.session.add(district)
        db.session.flush()
    school = db.session.query(School).filter_by(organisation_id=org.id, name=name).first()
    if school is None:
        school = School(organisation_id=org.id, district_id=district.id, name=name, udise_code=udise,
                        block=f"{district_name} Block", school_type=kind,
                        email=f"{name.split()[-1].lower()}.school@example.com", phone=f"0{R.randint(2000000000, 2999999999)}",
                        address=f"Main Road, {district_name}")
        db.session.add(school)
        db.session.flush()
    if school.location is None:
        school.location = point_wkt(lat, lng)
    school.school_type = school.school_type or kind
    return school, district


def _lab(org, school, name, sector, roles):
    lab = db.session.query(Lab).filter_by(school_id=school.id).first()
    if lab is None:
        lab = Lab(organisation_id=org.id, name=name, sector_id=sector.id, school_id=school.id,
                  job_role_9_10_id=roles[0].id, job_role_11_12_id=roles[1].id, curriculum_level="1-4",
                  sections_9="A,B", sections_10="A", sections_11="A", sections_12="A")
        db.session.add(lab)
        db.session.flush()
    return lab


def _trainer(org, school, lab, role, name, email, gender):
    """A trainer login + trainer record for one job-role slot of a lab."""
    u = _user(org, name, email, "VT", school_id=school.id)
    if lab not in u.labs:
        u.labs.append(lab)
    t = db.session.query(Trainer).filter_by(user_id=u.id).first()
    if t is None:
        t = (db.session.query(Trainer).filter_by(lab_id=lab.id, job_role_id=role.id, user_id=None).first()
             or Trainer(organisation_id=org.id, full_name=name, school_id=school.id, lab_id=lab.id, job_role_id=role.id))
        t.user_id, t.email = u.id, email
        db.session.add(t)
    t.trainer_status = t.trainer_status or "active"
    t.phone = t.phone or _phone()
    t.gender = t.gender or gender
    t.date_of_joining = t.date_of_joining or date(R.choice([2022, 2023, 2024]), R.choice([6, 7]), R.randint(1, 28))
    t.vtp_name = t.vtp_name or "Demo Skills Pvt. Ltd."
    t.appointment_nature = t.appointment_nature or "Contractual"
    db.session.flush()
    return u, t


def _principal(org, school, name, email, gender, emp):
    u = _user(org, name, email, "PR", school_id=school.id)
    p = db.session.query(Principal).filter_by(user_id=u.id).first()
    if p is None:
        p = (db.session.query(Principal).filter_by(linked_school_id=school.id, user_id=None).first()
             or Principal(organisation_id=org.id, full_name=name, email=email, linked_school_id=school.id))
        p.user_id = u.id
        db.session.add(p)
    p.linked_school_id = p.linked_school_id or school.id
    p.mobile = p.mobile or _phone()
    p.gender = p.gender or gender
    p.designation = p.designation or "Principal"
    p.employee_id = p.employee_id or emp
    p.appointment_nature = p.appointment_nature or "Regular"
    p.date_of_joining = p.date_of_joining or date(R.choice([2019, 2020, 2021]), 6, R.randint(1, 28))
    db.session.flush()
    school.principal_id = school.principal_id or p.id
    return u, p


# ============================================================ a lab's year
def _principal_issues(org, school, pr_user, today):
    """A few issues the principal has raised - open, being handled, resolved.
    Runs for every school that has none yet, even one filled earlier."""
    if db.session.query(PrincipalIssue).filter_by(school_id=school.id).first():
        return 0
    principal = db.session.query(Principal).filter_by(user_id=pr_user.id).first()
    picked = R.sample(PR_ISSUES, 4)
    for text, status in picked:
        day = today - timedelta(days=R.randint(2, 60))
        db.session.add(PrincipalIssue(
            organisation_id=org.id, school_id=school.id, principal_id=principal.id,
            academic_year=academic_year_for(org.id, day), reporting_date=day,
            reporting_time=time(R.randint(10, 16), R.choice([0, 15, 30, 45])), details=text,
            workflow_status=status, created_by=pr_user.id,
            resolved_on=datetime.combine(min(day + timedelta(days=5), today), time(12)) if status == "resolved" else None,
            resolution_note="Sorted out by the district office" if status == "resolved" else None))
    return len(picked)


def _org_issues(org, today):
    """A few issues the org admin raised for the super admin - two open, one
    resolved - each with the notices the app would have sent (the super
    admin: raised / resolved; the org admin: resolved). Idempotent."""
    from urllib.parse import urlencode
    from app.services.notify import _link
    oa = db.session.query(User).filter_by(organisation_id=org.id, role="OA", is_deleted=False).order_by(User.created_at).first()
    if oa is None or db.session.query(OrgIssue.id).filter_by(organisation_id=org.id).first():
        return 0
    sas = db.session.query(User).filter(User.role == "SA", User.is_deleted.is_(False)).all()
    for i, (text, status, note) in enumerate(OA_ISSUES):
        day = today - timedelta(days=3 + i * 4)
        rec = OrgIssue(organisation_id=org.id, raised_by=oa.id, created_by=oa.id,
                       academic_year=academic_year_for(org.id, day), reporting_date=day,
                       reporting_time=time(11 + i, 15), details=text, workflow_status=status, resolution_note=note,
                       resolved_on=datetime.combine(day + timedelta(days=2), time(16)) if note else None)
        db.session.add(rec)
        db.session.flush()
        q = {"_org": str(org.id), "workflow_status": "open", "focus": str(rec.id)}
        when = datetime.combine(day, time(11 + i, 20))
        for sa in sas:
            title = f"New issue from {oa.full_name} ({org.name})"
            if note:
                q["workflow_status"] = "resolved"
            db.session.add(Notification(
                organisation_id=org.id, user_id=sa.id, category="issue", created_at=when, is_read=bool(note),
                title=(f"Resolved - {title}" if note else title)[:200],
                body=(f"Resolved by {sa.full_name}: {note}" if note else text)[:300],
                link=f"/app/org-issues?{urlencode(q)}"))
        if note:
            db.session.add(Notification(
                organisation_id=org.id, user_id=oa.id, category="issue", is_read=False,
                created_at=datetime.combine(day + timedelta(days=2), time(16, 5)),
                title="Your issue has been resolved", body=note[:300],
                link=_link("org-issues", record=rec, workflow_status="resolved")))
    return len(OA_ISSUES)


def _notifications(org, today):
    """What each bell shows - org admins, principals, trainers, and the super
    admin (about org admins) - some read, some not. Each one points at a real
    record, built the way the app builds its own (services/notify.py), so a
    click opens that record's list, filtered, with the row flashing. Anyone
    who already has notifications is left as they are."""
    from urllib.parse import urlencode
    from app.services.notify import _link

    schools = db.session.query(School).filter_by(organisation_id=org.id).order_by(School.name).all()
    if not schools:
        return
    first = schools[0]
    lab_ids = lambda school: [l.id for l in db.session.query(Lab).filter_by(school_id=school.id)]  # noqa: E731

    def one(model, *conds, order=None):
        q = db.session.query(model).filter(model.organisation_id == org.id, model.is_deleted.is_(False), *conds)
        return q.order_by(order if order is not None else model.created_at.desc()).first()

    def oa_notices(school):
        labs = lab_ids(school)
        vt_issue = one(VTIssue, VTIssue.lab_id.in_(labs), VTIssue.workflow_status == "open")
        pr_issue = one(PrincipalIssue, PrincipalIssue.school_id == school.id, PrincipalIssue.workflow_status == "open")
        pr_done = one(PrincipalIssue, PrincipalIssue.school_id == school.id, PrincipalIssue.workflow_status == "resolved")
        eq = one(LabEquipment, LabEquipment.school_id == school.id)
        maint = one(EquipmentMaintenance, EquipmentMaintenance.equipment_id.in_(
            [e.id for e in db.session.query(LabEquipment.id).filter(LabEquipment.school_id == school.id)]),
            EquipmentMaintenance.maintenance_status != "Resolved")
        pending = one(Student, Student.school_id == school.id, Student.verification_status == "pending")
        tc = one(Student, Student.school_id == school.id, Student.leaving_stage == "tc_issued")
        at = f" at {school.name}"
        return [x for x in (
            vt_issue and ("New issue from a trainer" + at, vt_issue.details, "issue",
                          _link("issues", school, True, record=vt_issue, workflow_status="open"), False),
            pr_issue and ("New issue from a principal" + at, pr_issue.details, "issue",
                          _link("principal-issues", school, True, record=pr_issue, workflow_status="open"), False),
            maint and (f"Maintenance needed{at}", maint.issue, "maintenance",
                       _link("equipment-maintenance", school, True, record=maint), False),
            pending and ("A student to verify" + at, f"{pending.full_name} was added and needs verifying.", "verification",
                         _link("students", school, True, record=pending, tab="verify"), False),
            tc and ("TC to verify: " + tc.full_name + at, f"{tc.leaving_type} · TC {tc.tc_number or ''}", "leaving",
                    _link("students", school, True, record=tc, tab="leaving"), False),
            eq and (f"Lab equipment added: {eq.name}{at}", eq.details or "", "equipment",
                    _link("equipment", school, True, record=eq), True),
            pr_done and ("Issue" + at + " is now Resolved", pr_done.details, "issue",
                         _link("principal-issues", school, True, record=pr_done, workflow_status="resolved"), True),
        ) if x]

    def pr_notices(u):
        school = db.session.get(School, u.school_id) if u.school_id else None
        if school is None:
            return []
        daily = one(DailyAttendance, DailyAttendance.school_id == school.id, DailyAttendance.endorsement_status == "submitted",
                    order=DailyAttendance.date.desc())
        cls = one(ClassAttendance, ClassAttendance.school_id == school.id, ClassAttendance.endorsement_status == "submitted",
                  order=ClassAttendance.date.desc())
        lecture = one(GuestLecture, GuestLecture.school_id == school.id, order=GuestLecture.reporting_date.desc())
        leaving = one(Student, Student.school_id == school.id, Student.leaving_stage == "requested")
        done = one(PrincipalIssue, PrincipalIssue.school_id == school.id, PrincipalIssue.workflow_status == "resolved")
        return [x for x in (
            daily and ("Daily attendance to verify", f"Marked for {daily.date:%d/%m/%Y}.", "attendance",
                       _link("attendance", record=daily, endorsement_status="submitted"), False),
            cls and (f"Class {cls.class_grade} attendance to verify", f"Marked for {cls.date:%d/%m/%Y}.", "attendance",
                     _link("class-attendance", record=cls, endorsement_status="submitted"), False),
            leaving and (f"{leaving.full_name} is leaving - TC needed", leaving.left_reason or "", "leaving",
                         _link("students", record=leaving, leaving_stage="requested"), False),
            lecture and (f"Guest lecture added: {lecture.topic}", lecture.lecturer_name or "", "guest_lecture",
                         _link("guest-lectures", record=lecture), True),
            done and ("Your issue has been resolved", done.resolution_note or done.details, "issue",
                      _link("principal-issues", record=done, workflow_status="resolved"), True),
        ) if x]

    def vt_notices(u):
        daily = one(DailyAttendance, DailyAttendance.created_by == u.id, DailyAttendance.endorsement_status == "endorsed",
                    order=DailyAttendance.date.desc())
        cls = one(ClassAttendance, ClassAttendance.created_by == u.id, ClassAttendance.endorsement_status == "endorsed",
                  order=ClassAttendance.date.desc())
        maint = one(EquipmentMaintenance, EquipmentMaintenance.created_by == u.id)
        return [x for x in (
            daily and ("Attendance verified", f"Your daily attendance for {daily.date:%d/%m/%Y} was verified.", "attendance",
                       _link("attendance", record=daily, endorsement_status="endorsed"), False),
            maint and (f"Maintenance: {maint.maintenance_status}", maint.issue or "", "maintenance",
                       _link("equipment-maintenance", record=maint), False),
            cls and ("Attendance verified", f"Your Class {cls.class_grade} attendance for {cls.date:%d/%m/%Y} was verified.",
                     "attendance", _link("class-attendance", record=cls, endorsement_status="endorsed"), True),
        ) if x]

    def sa_notices():
        """what org admins did - opening in their organisation"""
        def link(path, school, rec):
            q = {"_org": str(org.id), "_school": str(school.id), "focus": str(rec.id)}
            if school.district_id:
                q["_district"] = str(school.district_id)
            return f"/app/{path}?{urlencode(q)}"
        trainer = db.session.query(Trainer).filter_by(organisation_id=org.id, school_id=first.id).first()
        pr_issue = one(PrincipalIssue, PrincipalIssue.school_id == first.id)
        return [x for x in (
            ("Org Admin added a school: " + first.name, f"Org Admin at {org.name}", "admin", link("schools", first, first), False),
            trainer and ("Org Admin added a trainer: " + trainer.full_name, f"Org Admin at {org.name}", "admin",
                         link("trainers", first, trainer), False),
            pr_issue and ("Org Admin changed a principal's issue", f"Org Admin at {org.name}", "admin",
                          link("principal-issues", first, pr_issue), True),
        ) if x]

    def add(u, notices, hour):
        for i, (title, body, category, link, read) in enumerate(notices):
            when = datetime.combine(today - timedelta(days=i * 2 + 1), time(hour + i))
            db.session.add(Notification(organisation_id=org.id, user_id=u.id, title=title[:200], body=(body or "")[:300],
                                        category=category, link=link, is_read=read, created_at=when))

    has = {uid for (uid,) in db.session.query(Notification.user_id).filter(Notification.organisation_id == org.id)}
    def dm_notices(u):
        """a district manager: issues and maintenance, at a school in their districts"""
        mine = {d.id for d in u.districts}
        school = next((s for s in schools if s.district_id in mine), None)
        return [x for x in oa_notices(school) if x[2] in ("issue", "maintenance")] if school else []

    for u in db.session.query(User).filter(User.organisation_id == org.id, User.role.in_(["OA", "DM", "PR", "VT"])):
        if u.id in has:
            continue
        notices = (oa_notices(first) if u.role == "OA" else dm_notices(u) if u.role == "DM"
                   else pr_notices(u) if u.role == "PR" else vt_notices(u))
        add(u, notices, 9)
    for sa in db.session.query(User).filter(User.role == "SA", User.is_deleted.is_(False)):
        if not db.session.query(Notification.id).filter_by(user_id=sa.id, organisation_id=org.id).first():
            add(sa, sa_notices(), 11)


def _audit_trail(org):
    """The audit log entries the app writes as people work: a principal
    verifying attendance, trainers and principals raising issues. One entry
    per record, so running again adds nothing."""
    logged = {e for (e,) in db.session.query(AuditLog.entity_id).filter(AuditLog.organisation_id == org.id)}
    users = {u.id: u for u in db.session.query(User).filter_by(organisation_id=org.id)}

    def add(uid, action, entity, rec_id, when, before=None, after=None):
        u = users.get(uid)
        if u is None or rec_id in logged:
            return
        db.session.add(AuditLog(id=uuid.uuid4(), organisation_id=org.id, actor_id=u.id, actor_email=u.email,
                                actor_role=u.role, action=action, entity=entity, entity_id=rec_id,
                                before=json.dumps(before) if before else None,
                                after=json.dumps(after) if after else None, ip="127.0.0.1", created_at=when))

    for model in (DailyAttendance, ClassAttendance):
        verified = (db.session.query(model).filter_by(organisation_id=org.id, endorsement_status="endorsed")
                    .order_by(model.endorsed_on.desc()).limit(40))
        for rec in verified:
            add(rec.endorsed_by, "update", model.__tablename__, rec.id, rec.endorsed_on,
                {"endorsement_status": "submitted"}, {"endorsement_status": "endorsed"})
    for model in (VTIssue, PrincipalIssue):
        for rec in db.session.query(model).filter_by(organisation_id=org.id):
            add(rec.created_by, "create", model.__tablename__, rec.id,
                datetime.combine(rec.reporting_date, rec.reporting_time or time(12)),
                after={"details": rec.details, "workflow_status": "open"})


def _fill_lab(org, school, lab, sector_code, vt_low, vt_high, pr_user, size, clock, counter, cats):
    """Everything a lab does in a year and a bit. Skipped if already there."""
    if db.session.query(ClassAttendance.id).filter_by(lab_id=lab.id).first():
        return None
    today = clock.today
    oid = org.id
    where = point_to_latlng(school.location)
    role_of = {c: lab.job_role_for(c) for c in ("9", "10", "11", "12")}
    trainer_of = {"9": vt_low, "10": vt_low, "11": vt_high, "12": vt_high}   # (user, trainer)
    adm_prefix = school.udise_code[-3:]
    adm_n = db.session.query(Student).filter(Student.school_id == school.id).count()

    # ---- students
    students = {}
    for cls in ("9", "10", "11", "12"):
        students[cls] = []
        for sec in lab.sections_for(cls):
            for n in range(1, SIZES[size][cls] + 1):
                female = R.random() < 0.5
                adm_n += 1
                s = Student(
                    id=uuid.uuid4(), organisation_id=oid, school_id=school.id, lab_id=lab.id,
                    job_role_id=role_of[cls], academic_year=clock.this_label, class_grade=cls, section=sec,
                    roll_number=f"{cls}{sec}-{n:02d}", admission_number=f"{clock.start_year}{adm_prefix}{adm_n:04d}",
                    first_name=R.choice(FIRST_F if female else FIRST_M), last_name=R.choice(LAST),
                    gender="Female" if female else "Male",
                    dob=date(clock.start_year - 14 - (int(cls) - 9), R.randint(1, 12), R.randint(1, 28)),
                    father_name=f"{R.choice(FIRST_M)} {R.choice(LAST)}", mother_name=f"{R.choice(FIRST_F)} {R.choice(LAST)}",
                    mobile_primary=_phone(), social_category_id=R.choice(cats), aadhaar_number=counter.aadhaar(),
                    date_of_enrolment=date(clock.start_year - (1 if cls in ("10", "12") else 0), 6, 16),
                    verification_status="verified" if R.random() > 0.08 else "pending",
                    had_vocational_9_10=True if cls in ("11", "12") else None,
                    continuing_same_trade=True if cls in ("11", "12") else None,
                )
                db.session.add(s)
                students[cls].append(s)
    db.session.flush()
    # one dropped out, one transferred - and Class 10 / 12 came up last year
    left_on = min(today - timedelta(days=10), clock.this_span[0] + timedelta(days=40))
    for n, (s, status, why) in enumerate(((students["10"][-1], "Dropped Out", "Family moved away"),
                                          (students["11"][-1], "Transferred Out", "Moved to another school"))):
        s.enrolment_status, s.left_on, s.left_reason = status, left_on, why
        # their leaving went all the way: marked, TC issued, confirmed
        s.leaving_stage, s.leaving_type, s.leave_requested_on = "left", status, left_on - timedelta(days=7)
        s.tc_number, s.tc_issued_on = f"TC/{clock.start_year}/{R.randint(100, 999)}", left_on
        s.tc_verified_on = datetime.combine(left_on + timedelta(days=2), time(11))
    # and two on their way out: one waiting for the principal's TC, one for the org admin
    waiting = students["9"][-1]
    waiting.leaving_stage, waiting.leaving_type = "requested", "Dropped Out"
    waiting.leave_requested_on, waiting.left_reason = today - timedelta(days=3), "Family moving to another city"
    checking = students["12"][-1]
    checking.leaving_stage, checking.leaving_type = "tc_issued", "Transferred Out"
    checking.leave_requested_on, checking.left_reason = today - timedelta(days=9), "Admission at a junior college"
    checking.tc_number, checking.tc_issued_on = f"TC/{clock.start_year}/{R.randint(100, 999)}", today - timedelta(days=2)
    for cls, prev in (("10", "9"), ("12", "11")):
        for s in students[cls]:
            db.session.add(StudentPromotion(
                organisation_id=oid, student_id=s.id, from_academic_year=clock.last_label,
                to_academic_year=clock.this_label, from_class=prev, to_class=cls, section=s.section,
                outcome="Promoted", from_roll_number=s.roll_number, from_job_role_id=role_of[prev],
                from_lab_id=lab.id, from_school_id=school.id, from_verification_status="verified",
                from_enrolment_status="Studying",
                snapshot={"class_grade": prev, "academic_year": clock.last_label, "section": s.section},
                created_by=vt_low[0].id))
    studying = {c: [s for s in v if s.enrolment_status == "Studying"] for c, v in students.items()}

    def roster(cls, secs):
        return [s for s in studying[cls] if s.section in secs]

    # ---- daily + class attendance, this school year so far
    n_daily = n_class = 0
    for day in clock.school_days(*clock.this_span):
        for (u, t), classes in ((vt_low, ("9", "10")), (vt_high, ("11", "12"))):
            if R.random() < 0.04:
                continue   # the odd day off
            at = datetime.combine(day, time(8, R.randint(35, 59)))
            status = _verified(day, today)
            d = DailyAttendance(organisation_id=oid, trainer_id=t.id, school_id=school.id, lab_id=lab.id,
                                academic_year=clock.this_label, date=day, day_type="Working day",
                                attendance_time=at.time(), endorsement_status=status, created_by=u.id,
                                details=R.choice([None, None, None, "Staff meeting after school"]),
                                endorsed_by=pr_user.id if status == "endorsed" else None,
                                endorsed_on=datetime.combine(day + timedelta(days=2), time(16)) if status == "endorsed" else None)
            _stamp(d, where, at - timedelta(hours=5, minutes=30))
            db.session.add(d)
            n_daily += 1
            for cls in classes:
                if R.random() < 0.3:
                    continue
                secs = lab.sections_for(cls)
                if len(secs) > 1 and R.random() < 0.7:
                    secs = [R.choice(secs)]
                when = datetime.combine(day, time(R.choice([10, 11, 12, 13]), R.choice([0, 15, 30, 45])))
                status = _verified(day, today)
                ca = ClassAttendance(id=uuid.uuid4(), organisation_id=oid, trainer_id=t.id, school_id=school.id,
                                     lab_id=lab.id, job_role_id=role_of[cls], academic_year=clock.this_label, date=day,
                                     time=when.time(), class_grade=cls, sections=",".join(secs),
                                     activity=R.choice(ACTIVITIES[sector_code][cls]), created_by=u.id,
                                     comment=R.choice([None, None, "Power cut for 20 minutes"]),
                                     endorsement_status=status, endorsed_by=pr_user.id if status == "endorsed" else None,
                                     endorsed_on=datetime.combine(day + timedelta(days=2), time(16, 30)) if status == "endorsed" else None)
                _stamp(ca, where, when - timedelta(hours=5, minutes=30))
                db.session.add(ca)
                for s in roster(cls, secs):
                    db.session.add(ClassAttendanceStudentMark(organisation_id=oid, class_attendance_id=ca.id,
                                                              student_id=s.id, present=R.random() < 0.9))
                n_class += 1

    # ---- guest lectures + field visits: last year (targets mostly met) and this year so far
    per_class = {  # (lectures, visits) - a big school meets more targets
        "last": {"9": (15, 2), "10": (15, 2), "11": (12, 1), "12": (9, 2)} if size == "big"
        else {"9": (15, 2), "10": (11, 1), "11": (8, 2), "12": (6, 1)},
        "this": {"9": (5, 1), "10": (4, 0), "11": (3, 1), "12": (2, 0)},
    }
    n_gl = n_fv = 0
    for which, span in (("last", clock.last_span), ("this", clock.this_span)):
        days = list(clock.school_days(*span))
        if not days:
            continue
        for cls, (lectures, visits) in per_class[which].items():
            u = trainer_of[cls][0]
            for day in sorted(R.sample(days, min(lectures, len(days)))):
                name, qual, email, phone, exp = R.choice(LECTURERS)
                gl = GuestLecture(id=uuid.uuid4(), organisation_id=oid, school_id=school.id, lab_id=lab.id,
                                  job_role_id=role_of[cls], class_grade=cls, sections=",".join(lab.sections_for(cls)),
                                  academic_year=academic_year_for(oid, day), reporting_date=day,
                                  topic=R.choice(TOPICS[sector_code][cls]), lecturer_name=name,
                                  lecturer_qualification=qual, lecturer_email=email, lecturer_phone=phone,
                                  lecturer_experience=exp, created_by=u.id)
                _stamp(gl, where, datetime.combine(day, time(6, 30)), distance=False)
                db.session.add(gl)
                if which == "this":
                    for s in roster(cls, lab.sections_for(cls)):
                        db.session.add(GuestLectureStudentMark(organisation_id=oid, guest_lecture_id=gl.id,
                                                               student_id=s.id, present=R.random() < 0.85))
                n_gl += 1
            for day in sorted(R.sample(days, min(visits, len(days)))):
                org_name, addr, person, desig, mail, mob = R.choice(ORGS)
                secs = [R.choice(lab.sections_for(cls))]
                fv = FieldVisit(id=uuid.uuid4(), organisation_id=oid, school_id=school.id, lab_id=lab.id,
                                job_role_id=role_of[cls], class_grade=cls, sections=",".join(secs),
                                academic_year=academic_year_for(oid, day), reporting_date=day,
                                organisation_name=org_name, address=addr, purpose="See real work in the trade",
                                activities="Walkthrough of the work floor and a live demonstration",
                                contact_person=person, contact_designation=desig, contact_email=mail,
                                contact_mobile=mob, created_by=u.id)
                _stamp(fv, where, datetime.combine(day, time(5)), distance=False)
                db.session.add(fv)
                if which == "this":
                    for s in roster(cls, secs):
                        db.session.add(FieldVisitStudentMark(organisation_id=oid, field_visit_id=fv.id,
                                                             student_id=s.id, present=R.random() < 0.92))
                n_fv += 1

    # ---- issues (trainers' and the principal's)
    for i, (text, status) in enumerate(R.sample(VT_ISSUES, 4)):
        day = today - timedelta(days=R.randint(3, 80))
        u, t = vt_low if i % 2 else vt_high
        iss = VTIssue(organisation_id=oid, trainer_id=t.id, lab_id=lab.id, academic_year=academic_year_for(oid, day),
                      reporting_date=day, reporting_time=time(R.randint(9, 15), R.choice([0, 20, 40])), details=text,
                      workflow_status=status, created_by=u.id,
                      resolved_on=datetime.combine(day + timedelta(days=7), time(12)) if status == "resolved" else None,
                      resolution_note="Fixed by the vendor" if status == "resolved" else None)
        _stamp(iss, where, datetime.combine(day, time(6)), distance=False)
        db.session.add(iss)

    # ---- lab equipment + maintenance log
    items = []
    for i, (name, desc) in enumerate(EQUIPMENT[sector_code]):
        u, t = vt_low if i % 3 else vt_high
        eq = LabEquipment(id=uuid.uuid4(), organisation_id=oid, school_id=school.id, lab_id=lab.id, trainer_id=t.id,
                          name=name, details=desc, created_by=u.id,
                          receipt_date=date(clock.start_year - 1, R.randint(6, 12), R.randint(1, 28)),
                          note=R.choice([None, "Under warranty", "Asset tag on the back"]))
        db.session.add(eq)
        items.append(eq)
    # saved before the log that points at them (no ORM relationship tells
    # SQLAlchemy the order)
    db.session.flush()
    for idx, issue, status in MAINTENANCE:
        db.session.add(EquipmentMaintenance(organisation_id=oid, equipment_id=items[idx].id,
                                            date=today - timedelta(days=R.randint(2, 80)), issue=issue,
                                            maintenance_status=status, note=R.choice([None, "Vendor informed"])))

    # ---- assessments + OJT
    n_as = 0
    tests = [("Unit test 1", "Monthly", clock.this_span[0] + timedelta(days=35), 25),
             ("Practical assessment 1", "Quarterly", clock.this_span[0] + timedelta(days=70), 50)]
    for cls, group in studying.items():
        for s in group:
            if s.verification_status != "verified":
                continue
            for name, kind, when, maxm in tests:
                if when >= today:
                    continue
                got = R.randint(int(maxm * 0.35), maxm)
                db.session.add(Assessment(organisation_id=oid, student_id=s.id, academic_year=clock.this_label,
                                          class_grade=cls, job_role_id=role_of[cls], nsqf_level=int(cls) - 8,
                                          assessment_type=kind, name=name, date=when, max_marks=maxm,
                                          marks_obtained=got, result="pass" if got >= maxm * 0.4 else "fail"))
                n_as += 1
    for s in studying["12"]:
        if s.verification_status == "verified":
            db.session.add(OJTPlacement(organisation_id=oid, student_id=s.id, academic_year=clock.this_label,
                                        job_role_id=role_of["12"], ojt_establishment=R.choice(ORGS)[0],
                                        ojt_hours_required=50, ojt_hours_logged=R.choice([10, 20, 30, 40, 50]),
                                        ojt_start=clock.this_span[0] + timedelta(days=50),
                                        placement_interested=R.random() < 0.6))

    # ---- feedback about the school
    for subject, rating in (("Lab sessions are useful", 5), ("Need more practical time", 3)):
        db.session.add(Feedback(organisation_id=oid, source=R.choice(["student", "teacher"]), subject=subject,
                                rating=rating, comments="Collected during a school visit", school_id=school.id,
                                lab_id=lab.id, date=today - timedelta(days=R.randint(5, 60))))
    db.session.flush()
    return {"students": sum(len(v) for v in students.values()), "daily": n_daily, "class": n_class,
            "lectures": n_gl, "visits": n_fv, "assessments": n_as, "class_12": studying["12"], "class_11": studying["11"]}


# =========================================================== internship data
def _internships(org, sector, seniors, clock):
    """Employers, their student mappings and the students' diaries."""
    if db.session.query(Employer.id).filter_by(organisation_id=org.id).first():
        return
    employers = []
    for name, addr, person, desig, mail, mob in ORGS[:4]:
        first, *rest = person.split()
        e = Employer(id=uuid.uuid4(), organisation_id=org.id, org_name=name, first_name=first,
                     last_name=" ".join(rest) or None, business_description="Takes vocational students for OJT",
                     employee_count=R.choice(["6-10", "11-20", "20+"]), year_of_foundation=R.randint(1985, 2015),
                     sector_id=sector.id, is_active=True, branch_name="Main branch", branch_address=addr,
                     poc_mobile=mob, poc_email=mail)
        db.session.add(e)
        employers.append(e)
    db.session.flush()   # before the mappings and diaries that point at them
    for s in seniors:
        e = R.choice(employers)
        start = clock.this_span[0] + timedelta(days=50)
        if start >= clock.today:
            continue
        db.session.add(EmployerStudentMap(organisation_id=org.id, student_id=s.id, employer_id=e.id,
                                          job_role_id=s.job_role_id, academic_year=clock.this_label,
                                          start_date=start, status="ongoing", ojt_hours_target=50,
                                          ojt_hours_logged=R.randint(5, 40)))
        for k in range(3):
            day = start + timedelta(days=7 * k + 1)
            if day >= clock.today:
                break
            db.session.add(DailyDiary(organisation_id=org.id, date=day, student_id=s.id, school_id=s.school_id,
                                      lab_id=s.lab_id, class_grade=s.class_grade, section=s.section, employer_id=e.id,
                                      learning=R.choice(["Learnt how customer records are kept",
                                                         "Helped with a service job card", "Observed the team's daily stand-up"]),
                                      hours_spent=R.choice([3, 4, 5])))


# ================================================================ profiles
def _trainer_profile(t, school):
    if t.father_name:
        return
    t.father_name, t.mother_name = f"{R.choice(FIRST_M)} {R.choice(LAST)}", f"{R.choice(FIRST_F)} {R.choice(LAST)}"
    t.dob = date(R.randint(1984, 1995), R.randint(1, 12), R.randint(1, 28))
    t.domicile_state, t.nationality, t.marital_status = "Maharashtra", "Indian", R.choice(["Single", "Married"])
    t.blood_group = R.choice(["A+", "B+", "O+", "AB+"])
    t.correspondence_address = t.permanent_address = f"{R.randint(1, 99)}, Shivaji Nagar, near {school.name}"
    t.beneficiary_name, t.bank_name, t.branch_address = t.full_name, "Demo Co-operative Bank", "Main branch"
    t.account_number, t.ifsc_code = f"{R.randint(10**11, 10**12 - 1)}", "DEMO0001234"
    t.gross_salary, t.deduction_epf, t.deduction_esi, t.deduction_tds, t.deduction_other = 24500, 1800, 180, 0, 0
    t.pan_number = f"ABCDE{R.randint(1000, 9999)}F"
    oid = t.organisation_id
    for row in (
        TrainerQualification(qualification="12th", course="HSC Science", institution="State Board", course_type="Full Time", passing_year=2008),
        TrainerQualification(qualification="Graduation", course="B.Sc. / B.E.", institution="State University", course_type="Full Time", passing_year=2012),
        TrainerExperience(organisation_name="City Computer Institute", address="Main Road", date_of_joining=date(2014, 7, 1),
                          date_of_resignation=date(2018, 5, 31), last_designation="Instructor", last_salary=15000,
                          job_type="Full Time", job_nature="Contractual", reason_for_resignation="Joined the NSQF programme"),
        TrainerTraining(training_type="Induction training for vocational trainers", training_level="State",
                        venue="SCERT", from_date=date(2022, 7, 4), to_date=date(2022, 7, 8)),
        TrainerPosting(vtp_name=t.vtp_name, district="-", block="-", school_name=school.name, school_year="-",
                       school_type=school.school_type, date_of_joining=t.date_of_joining,
                       appointment_nature="Contractual", appointment_letter=True, experience_certificate=False),
    ):
        row.organisation_id, row.trainer_id = oid, t.id
        db.session.add(row)


def _principal_profile(p):
    if p.father_name:
        return
    p.father_name, p.dob = f"{R.choice(FIRST_M)} {R.choice(LAST)}", date(R.randint(1968, 1978), R.randint(1, 12), R.randint(1, 28))
    p.alternate_mobile = _phone()
    p.service_joining_date = date(R.randint(1996, 2004), 7, 1)
    p.substantive_post = R.choice(["Lecturer (PGT) Mathematics", "Lecturer (PGT) Physics", "Headmaster"])
    p.highest_qualification, p.professional_qualification = "Masters/Post-Graduation", "B.Ed, M.Ed"
    p.subject_specialisation = R.choice(["Mathematics", "Physics", "English"])
    p.correspondence_address = p.permanent_address = f"Staff Quarters {R.randint(1, 20)}, Civil Lines"
    for row in (
        PrincipalQualification(qualification="Masters/Post-Graduation", course="M.Sc.", institution="State University",
                               course_type="Full Time", passing_year=1995),
        PrincipalPosting(school_name="Govt Junior College", district="-", block="-", designation="Lecturer",
                         from_date=p.service_joining_date, to_date=(p.date_of_joining or date(2020, 6, 1)) - timedelta(days=1)),
        PrincipalTraining(training_type="School leadership programme", training_level="State", venue="SCERT",
                          from_date=date(2021, 9, 6), to_date=date(2021, 9, 17)),
    ):
        row.organisation_id, row.principal_id = p.organisation_id, p.id
        db.session.add(row)


# ===================================================================== run
def run_full_seed(today=None, quiet=False):
    from app.seed import seed_base
    from app.test_schools import run_test_schools

    clock = Clock(today)
    counter = Counter()
    say = (lambda *a: None) if quiet else print

    org = seed_base()
    _ensure_years(org, clock)
    sectors, roles = _masters(org)
    state = db.session.query(State).filter_by(organisation_id=org.id).first()
    cats = [c.id for c in db.session.query(SocialCategory).filter_by(organisation_id=org.id)]

    # ---- the demo organisation's schools, labs, trainers and principals
    labs = []
    for n, (key, name, district, lat, lng, kind, lab_name, sec, size) in enumerate(RNAF_SCHOOLS, start=1):
        school, _ = _school(org, state, district, name, lat, lng, kind, f"2700000000{n}")
        lab = _lab(org, school, lab_name or f"IT Lab - {district}", sectors[sec], roles[sec])
        low, high = roles[sec] if lab.job_role_9_10_id == roles[sec][0].id else (
            db.session.get(JobRole, lab.job_role_9_10_id), db.session.get(JobRole, lab.job_role_11_12_id))
        vt_low = _trainer(org, school, lab, low, "Vocational Trainer" if key == "pune" else f"Trainer {district} (9-10)",
                          "vt@rnaf.demo" if key == "pune" else f"vt.{key}@rnaf.demo", "Female")
        vt_high = _trainer(org, school, lab, high, "Senior Vocational Trainer" if key == "pune" else f"Trainer {district} (11-12)",
                           "vt.senior@rnaf.demo" if key == "pune" else f"vt.{key}.senior@rnaf.demo", "Male")
        pr = _principal(org, school, "Principal One" if key == "pune" else f"Principal {district}",
                        "pr@rnaf.demo" if key == "pune" else f"pr.{key}@rnaf.demo", "Male", f"EMP-{key.upper()}")
        labs.append((org, school, lab, sec, vt_low, vt_high, pr, size))

    # ---- the three location-test schools (vt.a@test.demo ...)
    run_test_schools()
    for key in ("a", "b", "c"):
        u = db.session.query(User).filter_by(email=f"vt.{key}@test.demo").first()
        if u is None:
            continue
        school = db.session.get(School, u.school_id)
        lab = u.labs[0]
        vt_low = (u, db.session.query(Trainer).filter_by(user_id=u.id).one())
        vt_high = _trainer(org, school, lab, db.session.get(JobRole, lab.job_role_11_12_id),
                           f"Trainer {key.upper()} (11-12)", f"vt.{key}.senior@test.demo", "Male")
        pr_user = db.session.query(User).filter_by(email=f"pr.{key}@test.demo").one()
        labs.append((org, school, lab, "IT", vt_low, vt_high,
                     (pr_user, db.session.query(Principal).filter_by(user_id=pr_user.id).one()), "small"))

    # ---- district managers and a second org admin
    districts = {d.name: d for d in db.session.query(District).filter_by(organisation_id=org.id)}
    dm2 = _user(org, "District Manager North", "dm2@rnaf.demo", "DM")
    for dname in ("Nashik", "Kolhapur"):
        if districts.get(dname) and districts[dname] not in dm2.districts:
            dm2.districts.append(districts[dname])
    _user(org, "Org Admin (Programmes)", "oa2@rnaf.demo", "OA")

    # ---- a second organisation, so the Super Admin sees more than one
    org2 = _second_org()
    _ensure_years(org2, clock)
    sectors2, roles2 = _masters(org2)
    state2 = db.session.query(State).filter_by(organisation_id=org2.id).first()
    if state2 is None:
        state2 = State(organisation_id=org2.id, name="Karnataka", code="KA")
        db.session.add(state2)
        db.session.flush()
    school2, district2 = _school(org2, state2, "Mysuru", "Govt PU College Mysuru", 12.2958, 76.6394,
                                 "Co-education", "29000000001")
    lab2 = _lab(org2, school2, "IT Lab - Mysuru", sectors2["IT"], roles2["IT"])
    _user(org2, "Org Admin Sahyog", "oa@sahyog.demo", "OA")
    dm_s = _user(org2, "District Manager Mysuru", "dm@sahyog.demo", "DM")
    if district2 not in dm_s.districts:
        dm_s.districts.append(district2)
    labs.append((org2, school2, lab2, "IT",
                 _trainer(org2, school2, lab2, roles2["IT"][0], "Trainer Mysuru (9-10)", "vt@sahyog.demo", "Female"),
                 _trainer(org2, school2, lab2, roles2["IT"][1], "Trainer Mysuru (11-12)", "vt.senior@sahyog.demo", "Male"),
                 _principal(org2, school2, "Principal Mysuru", "pr@sahyog.demo", "Female", "EMP-MYS"), "small"))
    db.session.flush()

    # ---- a year and a bit of work in every lab, and everyone's profile
    seniors = {}
    say("Filling each lab:")
    for o, school, lab, sec, vt_low, vt_high, pr, size in labs:
        cats_o = [c.id for c in db.session.query(SocialCategory).filter_by(organisation_id=o.id)]
        made = _fill_lab(o, school, lab, sec, vt_low, vt_high, pr[0], size, clock, counter, cats_o)
        if made:
            seniors.setdefault(o.id, []).extend(made["class_11"][:3] + made["class_12"][:3])
            say(f"  {school.name:<30} {made['students']:>3} students, {made['daily']:>3} daily + "
                f"{made['class']:>3} class attendance, {made['lectures']:>2} lectures, {made['visits']} visits")
        else:
            say(f"  {school.name:<30} already filled - skipped")
        if _principal_issues(o, school, pr[0], clock.today) and not made:
            say(f"  {school.name:<30} + principal issues")
        _trainer_profile(vt_low[1], school)
        _trainer_profile(vt_high[1], school)
        _principal_profile(pr[1])
    for o in (org, org2):
        _notifications(o, clock.today)
        if _org_issues(o, clock.today):
            say(f"  {o.name:<30} + org admin issues")
    db.session.flush()
    for o in (org, org2):
        _audit_trail(o)
    for o in (org, org2):
        _internships(o, db.session.query(Sector).filter_by(organisation_id=o.id, name="IT/ITeS").first(),
                     seniors.get(o.id, []), clock)
    db.session.commit()

    say(f"\nDemo site ready (school year {clock.this_label}). Every password: {PASSWORD}")
    say("  Super Admin        sa@rnaf.demo")
    say("  Org Admins         oa@rnaf.demo, oa2@rnaf.demo, oa@sahyog.demo")
    say("  District Managers  dm@rnaf.demo (Pune, Nagpur), dm2@rnaf.demo (Nashik, Kolhapur), dm@sahyog.demo")
    say("  Principals         pr@rnaf.demo (Pune), pr.nagpur@, pr.nashik@, pr.kolhapur@ (…@rnaf.demo), pr@sahyog.demo,")
    say("                     pr.a@ / pr.b@ / pr.c@test.demo (location-test schools)")
    say("  Trainers           vt@rnaf.demo + vt.senior@rnaf.demo (Pune), vt.<school>@ and vt.<school>.senior@rnaf.demo,")
    say("                     vt@sahyog.demo, vt.a@ / vt.b@ / vt.c@test.demo")
