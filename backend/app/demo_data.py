"""Fill the demo organisation with a working school's worth of records.

Run after `flask seed`:   flask demo-data

Everything is fictional - names, phone numbers, Aadhaar/PAN/bank numbers,
companies - and generated from a fixed random seed, so every run produces the
same data. It follows the same rules the app enforces: attendance is marked
within 1 km of the school, dates are never in the future, a record's year
follows its date, a class's job role follows the lab's slot, and so on.

Adds (for the Pune school, both of its trainers):
  students in Classes 9-12 (a few pending, dropped out or transferred), with
  promotion history; daily and class attendance since the start of this
  year, mostly endorsed; guest lectures and field visits for this year and
  last (some levels meeting their yearly target, some not); issues, lab
  equipment and its maintenance log; assessments; OJT for Class 12; and
  filled-in trainer and principal profiles.
"""
import math
import random
from datetime import date, datetime, time, timedelta

from app.extensions import db
from app.models.geo import point_wkt
from app.models.geography import Principal, School
from app.models.lab import Lab, Trainer
from app.models.masters import JobRole, SocialCategory
from app.models.operations import (
    ClassAttendance, ClassAttendanceStudentMark, DailyAttendance, EquipmentMaintenance, FieldVisit,
    FieldVisitStudentMark, GuestLecture, GuestLectureStudentMark, LabEquipment, VTIssue,
)
from app.models.internship import OJTPlacement
from app.models.organisation import Organisation
from app.models.student import Assessment, Student, StudentPromotion
from app.models.trainer_profile import (
    PrincipalPosting, PrincipalQualification, PrincipalTraining,
    TrainerExperience, TrainerPosting, TrainerQualification, TrainerTraining,
)
from app.models.user import User
from app.services.academic_year import academic_year_for

R = random.Random(2026)
THIS_YEAR_START = date(2026, 6, 15)       # the current school year's first day
LAST_YEAR = (date(2025, 6, 16), date(2026, 4, 25))
HOLIDAYS = {date(2026, 8, 15), date(2026, 8, 27), date(2025, 8, 15), date(2025, 10, 2), date(2025, 10, 20),
            date(2025, 10, 21), date(2026, 1, 26), date(2026, 3, 4)}

FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Reyansh", "Krishna", "Ishaan", "Rohan", "Kabir",
         "Ananya", "Diya", "Saanvi", "Aadhya", "Kiara", "Myra", "Pari", "Anika", "Navya", "Riya",
         "Omkar", "Pranav", "Siddharth", "Tanvi", "Sneha", "Pooja", "Neha", "Harsh", "Yash", "Aditi"]
LAST = ["Patil", "Deshmukh", "Joshi", "Kulkarni", "Pawar", "Shinde", "More", "Jadhav", "Gaikwad", "Chavan",
        "Kale", "Bhosale", "Sawant", "Salunkhe", "Mane", "Shaikh", "Pathan", "Nair", "Iyer", "Rao"]
ACTIVITIES = {
    "9": ["Practical: keyboard layout and typing speed drill", "Theory: parts of a computer",
          "Practical: creating and saving files in folders", "Theory: data entry basics and accuracy",
          "Practical: spreadsheet data entry exercise", "Revision and oral quiz"],
    "10": ["Practical: formatting a document in a word processor", "Theory: data privacy and backups",
           "Practical: sorting and filtering in a spreadsheet", "Mock test: data entry speed and accuracy",
           "Practical: mail merge exercise", "Theory: workplace health and safety"],
    "11": ["Theory: variables, loops and conditions", "Practical: first Python programs",
           "Practical: debugging a small program", "Theory: introduction to databases",
           "Practical: writing simple SQL queries", "Group activity: pseudocode for a billing app"],
    "12": ["Practical: building a small web page", "Theory: version control with Git",
           "Practical: CRUD app mini project", "Mock practical exam", "Theory: software testing basics",
           "Project review and viva practice"],
}
LECTURERS = [
    ("Dr. Meera Rao", "PhD Computer Science", "meera.rao@example.com", "9812300001", "15 years, university faculty"),
    ("Rahul Mehta", "B.E. Computer Engineering", "rahul.mehta@example.com", "9812300002", "8 years, software developer"),
    ("Sunita Kulkarni", "MCA", "sunita.k@example.com", "9812300003", "10 years, IT trainer"),
    ("Anil Deshpande", "Diploma in IT", "anil.d@example.com", "9812300004", "12 years, data centre operations"),
    ("Farah Sheikh", "M.Sc. Data Science", "farah.s@example.com", "9812300005", "6 years, data analyst"),
    ("Vikram Nair", "B.Tech IT", "vikram.nair@example.com", "9812300006", "9 years, cyber security"),
]
TOPICS = {
    "9": ["Careers in data entry", "Staying safe online", "Typing for speed", "How offices use computers"],
    "10": ["Spreadsheets at work", "Digital payments basics", "Customer data and privacy", "Office automation"],
    "11": ["A day as a software developer", "Intro to open source", "Logic and problem solving", "How apps are built"],
    "12": ["Preparing for IT interviews", "Freelancing and startups", "Cloud computing basics", "Building a portfolio"],
}
ORGS = [
    ("Sahyadri Data Services", "Plot 12, Hinjewadi Phase 1, Pune", "Kiran Joshi", "HR Manager", "hr@sahyadri-data.example", "9822000011"),
    ("Deccan Softlabs", "3rd Floor, Baner Road, Pune", "Ritu Kapoor", "Training Head", "training@deccansoft.example", "9822000012"),
    ("Pune City Bank - Data Centre", "Shivajinagar, Pune", "Mahesh Pawar", "Operations Lead", "ops@pcb.example", "9822000013"),
    ("Maratha Motors (IT Dept.)", "Chakan MIDC, Pune", "Sachin More", "IT Manager", "it@marathamotors.example", "9822000014"),
    ("Western Railway Reservation Office", "Pune Station", "A. Qureshi", "Station Manager", "prs@railway.example", "9822000015"),
]
ISSUES = [
    ("Two desktop computers do not start", "resolved"), ("Internet connection very slow in the lab", "in-progress"),
    ("Projector bulb fused", "resolved"), ("Lab room needs electrical repair - one socket sparks", "open"),
    ("Textbooks for Class 11 not yet received", "in-progress"), ("Travel reimbursement for field visit pending", "open"),
    ("UPS battery drains in 5 minutes", "resolved"), ("Printer paper and toner not supplied", "open"),
]
EQUIPMENT = [
    ("Desktop computer (Lab PC 1-10)", "10 desktop computers with keyboards and mice"),
    ("Desktop computer (Lab PC 11-20)", "10 desktop computers with keyboards and mice"),
    ("LCD projector", "Ceiling mounted, with screen"), ("Laser printer", "Mono laser, A4"),
    ("UPS 5 kVA", "Backup for the whole lab"), ("Wi-Fi router", "Dual band"), ("Network switch 24-port", "Rack mounted"),
    ("Whiteboard", "6 ft x 4 ft"), ("Scanner", "Flatbed, A4"), ("Air conditioner", "1.5 ton split"),
    ("Headphones (set of 20)", "For typing tutor audio"), ("Server rack", "For the lab server"),
]
MAINTENANCE = [
    (1, "Two PCs not booting - SMPS failure", "Repaired"), (2, "Projector bulb fused", "Replaced"),
    (4, "UPS battery backup under 5 minutes", "Awaiting Spare Parts"), (3, "Paper jam and faded prints", "Repaired"),
    (5, "Router drops connection every hour", "Under Inspection"), (9, "AC not cooling", "Sent for Repair"),
    (0, "One monitor flickers", "Under Repair"), (10, "Four headphones broken", "Reported"),
]


# ------------------------------------------------------------------ helpers
def _near(lat, lng, max_m=450):
    """A point up to `max_m` metres from (lat, lng), and its distance."""
    d, bearing = R.uniform(15, max_m), R.uniform(0, 2 * math.pi)
    dlat = d * math.cos(bearing) / 111_320
    dlng = d * math.sin(bearing) / (111_320 * math.cos(math.radians(lat)))
    return lat + dlat, lng + dlng, round(d, 1)


def _stamp(rec, lat, lng, when, school_lat, school_lng, with_distance=True):
    plat, plng, dist = _near(school_lat, school_lng)
    rec.set_location(plat, plng, round(R.uniform(8, 40), 1), when)
    if with_distance:
        rec.distance_from_school_m = dist


def _school_days(start, end):
    d = start
    while d <= end:
        if d.weekday() < 6 and d not in HOLIDAYS:   # Monday to Saturday
            yield d
        d += timedelta(days=1)


def _phone():
    return f"9{R.randint(100000000, 999999999)}"


def _endorsement(day, today):
    if (today - day).days <= 5:
        return "submitted"
    return R.choices(["endorsed", "returned", "submitted"], weights=[90, 3, 7])[0]


def run_demo_data():
    today = date.today()
    org = db.session.query(Organisation).filter_by(org_code="RNAF-DEMO").first()
    if org is None:
        print("Run `flask seed` first - there is no demo organisation yet.")
        return
    school = db.session.query(School).filter_by(organisation_id=org.id, name="Govt High School Pune").first()
    lab = db.session.query(Lab).filter_by(school_id=school.id).first()
    if db.session.query(ClassAttendance).filter_by(organisation_id=org.id).first():
        print("The demo organisation already has activity - skipping. (Reset with "
              "`docker compose -f docker-compose.local.yml down -v`, then db upgrade, seed, demo-data.)")
        return

    vt_user = db.session.query(User).filter_by(email="vt@rnaf.demo").one()
    pr_user = db.session.query(User).filter_by(email="pr@rnaf.demo").one()
    tr = db.session.query(Trainer).filter_by(user_id=vt_user.id).one()
    tr2 = db.session.query(Trainer).filter(Trainer.lab_id == lab.id, Trainer.id != tr.id).first()
    principal = db.session.query(Principal).filter_by(user_id=pr_user.id).one()
    general = db.session.query(SocialCategory).filter_by(organisation_id=org.id, name="General").first()
    obc = db.session.query(SocialCategory).filter_by(organisation_id=org.id, name="OBC").first()
    from app.models.geo import point_to_latlng
    slat, slng = point_to_latlng(school.location)
    org_id = org.id
    year_now = academic_year_for(org_id, today)
    year_last = academic_year_for(org_id, LAST_YEAR[0])
    who = {"9": tr, "10": tr, "11": tr2, "12": tr2}   # 9-10 slot and 11-12 slot trainers
    role_of = {c: lab.job_role_for(c) for c in ("9", "10", "11", "12")}

    # ---------------------------------------------------------- students
    sections = {"9": ["A", "B"], "10": ["A", "B"], "11": ["A"], "12": ["A"]}
    per_section = {"9": 8, "10": 7, "11": 9, "12": 7}
    students = {c: [] for c in sections}
    used = set()
    for cls, secs in sections.items():
        for sec in secs:
            for n in range(1, per_section[cls] + 1):
                while True:
                    fn, ln = R.choice(FIRST), R.choice(LAST)
                    if (fn, ln) not in used:
                        used.add((fn, ln))
                        break
                s = Student(
                    organisation_id=org_id, school_id=school.id, lab_id=lab.id, job_role_id=role_of[cls],
                    academic_year=year_now, class_grade=cls, section=sec, roll_number=f"{cls}{sec}-{n:02d}",
                    first_name=fn, last_name=ln, gender="Female" if fn in FIRST[10:20] + ["Tanvi", "Sneha", "Pooja", "Neha", "Aditi"] else "Male",
                    dob=date(2026 - 5 - int(cls), R.randint(1, 12), R.randint(1, 28)),
                    father_name=f"{R.choice(FIRST[:10])} {ln}", mother_name=f"{R.choice(FIRST[10:20])} {ln}",
                    mobile_primary=_phone(), social_category_id=R.choice([general.id, obc.id]),
                    date_of_enrolment=date(2025, 6, 16) if cls in ("10", "12") else THIS_YEAR_START,
                    verification_status="verified" if R.random() > 0.08 else "pending",
                    had_vocational_9_10=True if cls in ("11", "12") else None,
                    continuing_same_trade=True if cls in ("11", "12") else None,
                )
                db.session.add(s)
                students[cls].append(s)
    db.session.flush()
    # a few have left
    left = [(students["10"][3], "Dropped Out", "Family moved to another city"),
            (students["11"][5], "Transferred Out", "Moved to a junior college in Mumbai")]
    for s, status, why in left:
        s.enrolment_status, s.left_on, s.left_reason = status, date(2026, 8, 20), why
    # Class 10 and 12 came up from 9 and 11 last year
    for cls, prev in (("10", "9"), ("12", "11")):
        for s in students[cls]:
            db.session.add(StudentPromotion(organisation_id=org_id, student_id=s.id, from_academic_year=year_last,
                                            to_academic_year=year_now, from_class=prev, to_class=cls,
                                            section=s.section, outcome="Promoted"))
    studying = {c: [s for s in students[c] if s.enrolment_status != "Dropped Out" and s.enrolment_status != "Transferred Out"]
                for c in students}

    def roster(cls, secs, on_day):
        return [s for s in studying[cls] if s.section in secs
                and not (s.left_on and s.left_on <= on_day)]

    # ------------------------------------------------- daily + class attendance
    counts = {"daily": 0, "class": 0}
    for day in _school_days(THIS_YEAR_START, today - timedelta(days=1)):
        for t, classes in ((tr, ("9", "10")), (tr2, ("11", "12"))):
            if t is None or R.random() < 0.04:   # the odd day off
                continue
            at = datetime.combine(day, time(8, R.randint(35, 59)))
            status = _endorsement(day, today)
            daily = DailyAttendance(
                organisation_id=org_id, trainer_id=t.id, school_id=school.id, lab_id=lab.id,
                academic_year=year_now, date=day, day_type="Working day", attendance_time=at.time(),
                details=R.choice([None, None, None, "Reached early to set up the lab", "Staff meeting after school"]),
                endorsement_status=status, created_by=vt_user.id if t is tr else None,
                endorsed_by=pr_user.id if status != "submitted" else None,
                endorsed_on=datetime.combine(day + timedelta(days=2), time(16, 30)) if status != "submitted" else None,
                endorsement_remarks="Please correct the time" if status == "returned" else None,
            )
            _stamp(daily, None, None, at - timedelta(hours=5, minutes=30), slat, slng)
            db.session.add(daily)
            counts["daily"] += 1
            for cls in classes:
                if R.random() < 0.25:
                    continue
                secs = sections[cls] if len(sections[cls]) == 1 or R.random() < 0.3 else [R.choice(sections[cls])]
                when = datetime.combine(day, time(R.choice([10, 11, 12, 13]), R.choice([0, 15, 30, 45])))
                status = _endorsement(day, today)
                ca = ClassAttendance(
                    organisation_id=org_id, trainer_id=t.id, school_id=school.id, lab_id=lab.id,
                    job_role_id=role_of[cls], academic_year=year_now, date=day, time=when.time(),
                    class_grade=cls, sections=",".join(secs), activity=R.choice(ACTIVITIES[cls]),
                    comment=R.choice([None, None, "Two students late", "Power cut for 20 minutes"]),
                    endorsement_status=status, endorsed_by=pr_user.id if status != "submitted" else None,
                    endorsed_on=datetime.combine(day + timedelta(days=2), time(16, 45)) if status != "submitted" else None,
                    endorsement_remarks="Section missing" if status == "returned" else None,
                    created_by=vt_user.id if t is tr else None,
                )
                _stamp(ca, None, None, when - timedelta(hours=5, minutes=30), slat, slng)
                db.session.add(ca)
                db.session.flush()
                for s in roster(cls, secs, day):
                    db.session.add(ClassAttendanceStudentMark(organisation_id=org_id, class_attendance_id=ca.id,
                                                              student_id=s.id, present=R.random() < 0.9))
                counts["class"] += 1

    # ------------------------------------------ guest lectures + field visits
    def spread(n, start, end):
        days = list(_school_days(start, end))
        return sorted(R.sample(days, min(n, len(days))))

    plan = {
        # (year range, per class: guest lectures, field visits)
        "last": (LAST_YEAR, {"9": (15, 2), "10": (15, 2), "11": (12, 1), "12": (9, 2)}),
        "this": ((THIS_YEAR_START, today - timedelta(days=1)), {"9": (5, 1), "10": (4, 0), "11": (3, 1), "12": (2, 0)}),
    }
    n_gl = n_fv = 0
    for which, ((start, end), per_class) in plan.items():
        for cls, (n_lect, n_visit) in per_class.items():
            t = who[cls]
            for day in spread(n_lect, start, end):
                name, qual, email, phone, exp = R.choice(LECTURERS)
                secs = sections[cls]
                gl = GuestLecture(
                    organisation_id=org_id, school_id=school.id, lab_id=lab.id, job_role_id=role_of[cls],
                    class_grade=cls, sections=",".join(secs), academic_year=academic_year_for(org_id, day),
                    reporting_date=day, topic=R.choice(TOPICS[cls]), lecturer_name=name,
                    lecturer_qualification=qual, lecturer_email=email, lecturer_phone=phone, lecturer_experience=exp,
                    created_by=vt_user.id if t is tr else None,
                )
                _stamp(gl, None, None, datetime.combine(day, time(6, 30)), slat, slng, with_distance=False)
                db.session.add(gl)
                db.session.flush()
                if which == "this":
                    for s in roster(cls, secs, day):
                        db.session.add(GuestLectureStudentMark(organisation_id=org_id, guest_lecture_id=gl.id,
                                                               student_id=s.id, present=R.random() < 0.85))
                n_gl += 1
            for day in spread(n_visit, start, end):
                org_name, addr, person, desig, mail, mob = R.choice(ORGS)
                secs = [R.choice(sections[cls])]
                fv = FieldVisit(
                    organisation_id=org_id, school_id=school.id, lab_id=lab.id, job_role_id=role_of[cls],
                    class_grade=cls, sections=",".join(secs), academic_year=academic_year_for(org_id, day),
                    reporting_date=day, organisation_name=org_name, address=addr,
                    activities="Walkthrough of the work floor and a live demonstration",
                    purpose=R.choice(["See how data entry is done at scale", "Understand a real software team",
                                      "Learn about IT careers in industry"]),
                    contact_person=person, contact_designation=desig, contact_email=mail, contact_mobile=mob,
                    created_by=vt_user.id if t is tr else None,
                )
                _stamp(fv, None, None, datetime.combine(day, time(5, 0)), slat, slng, with_distance=False)
                db.session.add(fv)
                db.session.flush()
                if which == "this":
                    for s in roster(cls, secs, day):
                        db.session.add(FieldVisitStudentMark(organisation_id=org_id, field_visit_id=fv.id,
                                                             student_id=s.id, present=R.random() < 0.92))
                n_fv += 1

    # -------------------------------------------------------------- issues
    for i, (text, status) in enumerate(ISSUES):
        day = today - timedelta(days=R.randint(3, 90))
        t = tr if i % 3 else tr2
        iss = VTIssue(organisation_id=org_id, trainer_id=t.id, lab_id=lab.id, academic_year=academic_year_for(org_id, day),
                      reporting_date=day, reporting_time=time(R.randint(9, 15), R.choice([0, 20, 40])), details=text,
                      workflow_status=status, resolved_on=datetime.combine(day + timedelta(days=7), time(12)) if status == "resolved" else None,
                      resolution_note="Fixed by the vendor" if status == "resolved" else None)
        _stamp(iss, None, None, datetime.combine(day, time(6)), slat, slng, with_distance=False)
        db.session.add(iss)

    # -------------------------------------------- equipment + maintenance log
    items = []
    for i, (name, desc) in enumerate(EQUIPMENT):
        eq = LabEquipment(organisation_id=org_id, school_id=school.id, lab_id=lab.id,
                          trainer_id=(tr if i % 3 else tr2).id, name=name, details=desc,
                          receipt_date=date(2025, R.randint(6, 12), R.randint(1, 28)),
                          note=R.choice([None, "Under warranty till 2027", "Asset tag on the back"]))
        db.session.add(eq)
        items.append(eq)
    db.session.flush()
    for idx, issue, status in MAINTENANCE:
        db.session.add(EquipmentMaintenance(organisation_id=org_id, equipment_id=items[idx].id,
                                            date=today - timedelta(days=R.randint(2, 80)), issue=issue,
                                            maintenance_status=status,
                                            note=R.choice([None, "Vendor informed", "Complaint no. logged"])))

    # --------------------------------------------------------- assessments
    n_as = 0
    for cls, group in studying.items():
        for s in group:
            if s.verification_status != "verified":
                continue
            for name, kind, when, maxm in (("Unit test 1", "internal", date(2026, 7, 20), 25),
                                           ("Practical assessment 1", "continuous", date(2026, 8, 24), 50)):
                got = R.randint(int(maxm * 0.35), maxm)
                db.session.add(Assessment(organisation_id=org_id, student_id=s.id, academic_year=year_now,
                                          class_grade=cls, job_role_id=role_of[cls], nsqf_level=int(cls) - 8,
                                          assessment_type=kind, name=name, date=when, max_marks=maxm,
                                          marks_obtained=got, result="pass" if got >= maxm * 0.4 else "fail"))
                n_as += 1

    # -------------------------------------------------------------- OJT
    for s in studying["12"]:
        if s.verification_status != "verified":
            continue
        est = R.choice(ORGS)[0]
        db.session.add(OJTPlacement(organisation_id=org_id, student_id=s.id, academic_year=year_now,
                                    job_role_id=role_of["12"], ojt_establishment=est,
                                    ojt_hours_required=50, ojt_hours_logged=R.choice([10, 20, 30, 40, 50]),
                                    ojt_start=date(2026, 8, 3), placement_interested=R.random() < 0.6))

    # --------------------------------------------------- trainer profiles
    profile = dict(
        father_name="Ramesh Sharma", mother_name="Sunita Sharma", dob=date(1990, 4, 12),
        domicile_state="Maharashtra", social_category_id=general.id, marital_status="Married",
        nationality="Indian", blood_group="B+", aadhaar_number="999988887777",
        correspondence_address="Flat 4, Sai Residency, Kothrud, Pune 411038, Maharashtra",
        permanent_address="Flat 4, Sai Residency, Kothrud, Pune 411038, Maharashtra",
        beneficiary_name=tr.full_name, bank_name="Demo Co-operative Bank", branch_address="Kothrud, Pune",
        account_number="001234567890", ifsc_code="DEMO0001234", gross_salary=24500, deduction_epf=1800,
        deduction_esi=180, deduction_tds=0, deduction_other=0, pan_number="ABCDE1234F", uan_number="100200300400",
    )
    for k, v in profile.items():
        if getattr(tr, k, None) in (None, ""):
            setattr(tr, k, v)
    for row in [
        TrainerQualification(qualification="10th", course="SSC", institution="Maharashtra State Board", course_type="Full Time", passing_year=2006),
        TrainerQualification(qualification="12th", course="HSC Science", institution="Maharashtra State Board", course_type="Full Time", passing_year=2008),
        TrainerQualification(qualification="Graduation", course="B.Sc. Computer Science", institution="Savitribai Phule Pune University", course_type="Full Time", passing_year=2011),
        TrainerQualification(qualification="Masters/Post-Graduation", course="MCA", institution="Savitribai Phule Pune University", course_type="Full Time", passing_year=2014),
        TrainerExperience(organisation_name="Pune Data Solutions", address="Hadapsar, Pune", date_of_joining=date(2014, 8, 1),
                          date_of_resignation=date(2018, 5, 31), last_designation="Data Analyst", last_salary=18000,
                          job_type="Full Time", job_nature="Permanent", reason_for_resignation="Moved into teaching"),
        TrainerExperience(organisation_name="Bright Futures Computer Institute", address="Kothrud, Pune",
                          date_of_joining=date(2018, 6, 15), date_of_resignation=date(2024, 6, 20),
                          last_designation="Computer Instructor", last_salary=21000, job_type="Full Time",
                          job_nature="Contractual", reason_for_resignation="Joined the NSQF programme"),
        TrainerTraining(training_type="Induction training for vocational trainers", training_level="State",
                        venue="SCERT, Pune", from_date=date(2024, 7, 8), to_date=date(2024, 7, 12)),
        TrainerTraining(training_type="IT/ITeS sector skill update", training_level="National",
                        venue="Online", from_date=date(2025, 11, 3), to_date=date(2025, 11, 7)),
        TrainerPosting(vtp_name=tr.vtp_name or "Demo Skills Pvt. Ltd.", district="Pune", block="Haveli",
                       school_name=school.name, school_year="2024-25", school_type="Co-education",
                       date_of_joining=tr.date_of_joining or date(2024, 7, 1), appointment_nature="Contractual",
                       appointment_letter=True, experience_certificate=False),
    ]:
        row.organisation_id, row.trainer_id = org_id, tr.id
        db.session.add(row)
    if tr2 is not None:
        for k, v in dict(phone="9800000012", gender="Male", date_of_joining=date(2023, 6, 12),
                         vtp_name="Demo Skills Pvt. Ltd.", appointment_nature="Contractual",
                         father_name="Mohan Kale", dob=date(1987, 9, 3), blood_group="O+", nationality="Indian").items():
            if getattr(tr2, k, None) in (None, ""):
                setattr(tr2, k, v)

    # -------------------------------------------------- principal profile
    for k, v in dict(father_name="Vasant Deshmukh", dob=date(1972, 11, 5), social_category_id=general.id,
                     alternate_mobile="9800000021", service_joining_date=date(1998, 7, 1),
                     substantive_post="Lecturer (PGT) Mathematics", highest_qualification="Masters/Post-Graduation",
                     professional_qualification="B.Ed, M.Ed", subject_specialisation="Mathematics",
                     correspondence_address="Bungalow 7, Model Colony, Pune 411016, Maharashtra",
                     permanent_address="Bungalow 7, Model Colony, Pune 411016, Maharashtra").items():
        if getattr(principal, k, None) in (None, ""):
            setattr(principal, k, v)
    for row in [
        PrincipalQualification(qualification="Graduation", course="B.Sc. Mathematics", institution="Fergusson College, Pune", course_type="Full Time", passing_year=1993),
        PrincipalQualification(qualification="Masters/Post-Graduation", course="M.Sc. Mathematics", institution="Savitribai Phule Pune University", course_type="Full Time", passing_year=1995),
        PrincipalQualification(qualification="Other", course="B.Ed", institution="Tilak College of Education", course_type="Full Time", passing_year=1996),
        PrincipalPosting(school_name="Govt Junior College, Satara", district="Satara", block="Satara",
                         designation="Lecturer (PGT) Mathematics", from_date=date(1998, 7, 1), to_date=date(2012, 5, 31)),
        PrincipalPosting(school_name="Govt High School, Baramati", district="Pune", block="Baramati",
                         designation="Vice-Principal", from_date=date(2012, 6, 1), to_date=date(2021, 6, 14)),
        PrincipalTraining(training_type="School leadership programme", training_level="State",
                          venue="SCERT, Pune", from_date=date(2021, 9, 6), to_date=date(2021, 9, 17)),
    ]:
        row.organisation_id, row.principal_id = org_id, principal.id
        db.session.add(row)
    if not school.phone:
        school.phone, school.email = "020-25530000", "ghs.pune@example.com"
    if not school.address:
        school.address = "Near Shaniwar Wada, Shaniwar Peth, Pune 411030"

    db.session.commit()
    total = sum(len(v) for v in students.values())
    print(f"Demo data added for {school.name}:")
    print(f"  {total} students (Classes 9-12), {counts['daily']} daily attendance, {counts['class']} class attendance")
    print(f"  {n_gl} guest lectures, {n_fv} field visits ({year_last} and {year_now}), {len(ISSUES)} issues")
    print(f"  {len(EQUIPMENT)} lab equipment, {len(MAINTENANCE)} maintenance entries, {n_as} assessments")
    print("  trainer and principal profiles filled in")
