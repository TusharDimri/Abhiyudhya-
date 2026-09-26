"""Seed a demo organisation with one login per role - spec Part 7.5.

Run:  flask seed   (or:  python -m app.seed)

Creates:
  - 1 Organisation (RNAF Demo)
  - State + 2 Districts, 2 Schools, Sectors, Job Roles, Academic Year
  - 2 Labs, curriculum tree sample, Trainers, Students
  - One user per role, all password: Password@123
"""
from datetime import date

from app import create_app
from app.extensions import db
from app.models.organisation import Organisation
from app.models.user import User
from app.models.geography import State, District, School, Principal
from app.models.masters import AcademicYear, Sector, JobRole, SocialCategory
from app.models.lab import Lab, Module, Unit, Session, Trainer
from app.models.student import Student
from app.models.geo import point_wkt

DEMO_PASSWORD = "Password@123"


def _mkuser(org, name, email, role, **scope):
    u = User(organisation_id=org.id if role != "SA" else None,
             full_name=name, email=email, role=role, **scope)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    return u


def run_seed():
    """`flask seed`: the demo organisation with one login per role."""
    app = create_app()
    with app.app_context():
        if db.session.query(Organisation).filter_by(org_code="RNAF-DEMO").first():
            print("Seed already present. Skipping.")
            return
        seed_base()


def seed_base():
    """Create the demo organisation (inside the current app context) unless it
    is already there; returns it. Used by `flask seed` and `flask seed-demo`."""
    existing = db.session.query(Organisation).filter_by(org_code="RNAF-DEMO").first()
    if existing:
        return existing

    # small inline SVG so the org-logo feature is visible out of the box
    logo = ("data:image/svg+xml;utf8,"
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'>"
            "<rect width='48' height='48' rx='10' fill='%2312294B'/>"
            "<text x='24' y='31' font-size='18' font-family='Arial' font-weight='bold'"
            " fill='%23C39A4D' text-anchor='middle'>RN</text></svg>")
    org = Organisation(name="RNAF Demo Organisation", legal_name="Ragini Narendra Abhiyudhya Foundation",
                       org_code="RNAF-DEMO", primary_contact_name="Admin", logo_url=logo,
                       primary_contact_email="oa@rnaf.demo", primary_contact_phone="9999999999")
    db.session.add(org)
    db.session.flush()

    ay = AcademicYear(organisation_id=org.id, label="2025-26",
                      start_date=date(2025, 6, 1), end_date=date(2026, 4, 30), is_current=True)
    db.session.add(ay)

    for cat in ["General", "SC", "ST", "OBC", "VJ", "SBC", "NT-B", "NT-C", "NT-D"]:
        db.session.add(SocialCategory(organisation_id=org.id, name=cat))

    state = State(organisation_id=org.id, name="Maharashtra", code="MH")
    db.session.add(state)
    db.session.flush()
    d1 = District(organisation_id=org.id, state_id=state.id, name="Pune", code="PN")
    d2 = District(organisation_id=org.id, state_id=state.id, name="Nagpur", code="NG")
    db.session.add_all([d1, d2])
    db.session.flush()

    it = Sector(organisation_id=org.id, name="IT/ITeS", code="IT")
    auto = Sector(organisation_id=org.id, name="Automotive", code="AUTO")
    db.session.add_all([it, auto])
    db.session.flush()

    jr_ddeo = JobRole(organisation_id=org.id, name="Domestic Data Entry Operator",
                      sector_id=it.id, qp_code="SSC/Q0212", nsqf_level=2, class_band="9-10")
    jr_jsd = JobRole(organisation_id=org.id, name="Junior Software Developer",
                     sector_id=it.id, qp_code="SSC/Q0508", nsqf_level=4, class_band="11-12")
    db.session.add_all([jr_ddeo, jr_jsd])
    db.session.flush()

    p1 = Principal(organisation_id=org.id, full_name="Principal One", email="pr@rnaf.demo",
                   mobile="9800000001",
                   # what the admin records when the principal takes charge (fictional)
                   designation="Principal", employee_id="EMP-DEMO-0001", gender="Male",
                   appointment_nature="Regular", date_of_joining=date(2021, 6, 15))
    db.session.add(p1)
    db.session.flush()

    s1 = School(organisation_id=org.id, district_id=d1.id, name="Govt High School Pune",
                udise_code="27000000001", block="Haveli", principal_id=p1.id,
                email="school1@rnaf.demo", phone="9820000001")
    s2 = School(organisation_id=org.id, district_id=d2.id, name="Govt High School Nagpur",
                udise_code="27000000002", block="Nagpur Rural", email="school2@rnaf.demo")
    # where the schools are: trainers mark attendance within 1 km of these
    s1.location = point_wkt(18.5204, 73.8567)   # Pune
    s1.school_type, s2.school_type = "Co-education", "Boys"
    s2.location = point_wkt(21.1458, 79.0882)   # Nagpur
    db.session.add_all([s1, s2])
    db.session.flush()
    p1.linked_school_id = s1.id

    # sections are configured per class here and every section dropdown in
    # the app reads them back (spec 1.3)
    lab1 = Lab(organisation_id=org.id, name="IT Lab - Pune", sector_id=it.id, school_id=s1.id,
               job_role_9_10_id=jr_ddeo.id, job_role_11_12_id=jr_jsd.id,
               curriculum_level="1-4", sections_per_class=2, academic_year_of_setup="2025-26",
               sections_9="A,B", sections_10="A,B", sections_11="A", sections_12="A")
    lab2 = Lab(organisation_id=org.id, name="IT Lab - Nagpur", sector_id=it.id, school_id=s2.id,
               job_role_9_10_id=jr_ddeo.id, job_role_11_12_id=jr_jsd.id, curriculum_level="1-2",
               sections_9="A", sections_10="A", sections_11="A", sections_12="A")
    db.session.add_all([lab1, lab2])
    db.session.flush()

    # curriculum sample - both module types, so the
    # Employability/Vocational -> module -> unit -> session cascade has
    # something to walk through out of the box
    mod = Module(organisation_id=org.id, job_role_id=jr_ddeo.id, nsqf_level=1,
                 name="Introduction to IT", module_type="Vocational", sort_order=1)
    mod_emp = Module(organisation_id=org.id, job_role_id=jr_ddeo.id, nsqf_level=1,
                     name="Communication Skills", module_type="Employability", sort_order=2)
    db.session.add_all([mod, mod_emp])
    db.session.flush()
    unit = Unit(organisation_id=org.id, module_id=mod.id, name="Computer Basics", sort_order=1)
    unit2 = Unit(organisation_id=org.id, module_id=mod.id, name="Operating Systems", sort_order=2)
    unit_emp = Unit(organisation_id=org.id, module_id=mod_emp.id, name="Speaking at Work", sort_order=1)
    db.session.add_all([unit, unit2, unit_emp])
    db.session.flush()
    db.session.add_all([
        Session(organisation_id=org.id, unit_id=unit.id, name="Parts of a Computer", sort_order=1),
        Session(organisation_id=org.id, unit_id=unit.id, name="Input and Output Devices", sort_order=2),
        Session(organisation_id=org.id, unit_id=unit2.id, name="Files and Folders", sort_order=1),
        Session(organisation_id=org.id, unit_id=unit_emp.id, name="Introducing Yourself", sort_order=1),
    ])

    # students
    st1 = Student(organisation_id=org.id, school_id=s1.id, lab_id=lab1.id, job_role_id=jr_ddeo.id,
                  academic_year="2025-26", class_grade="9", section="A", roll_number="9A-01",
                  first_name="Aarav", last_name="Sharma", gender="Male",
                  mobile_primary="9700000001", date_of_enrolment=date(2025, 6, 10),
                  verification_status="verified")
    st2 = Student(organisation_id=org.id, school_id=s1.id, lab_id=lab1.id, job_role_id=jr_jsd.id,
                  academic_year="2025-26", class_grade="11", section="A", roll_number="11A-01",
                  first_name="Diya", last_name="Patil", gender="Female",
                  mobile_primary="9700000002", date_of_enrolment=date(2025, 6, 10),
                  had_vocational_9_10=True, continuing_same_trade=True,
                  verification_status="pending")
    db.session.add_all([st1, st2])
    # a class worth marking attendance for
    for i, (fn, ln, sec, gender) in enumerate(
        [("Kabir", "Joshi", "A", "Male"), ("Isha", "Kulkarni", "A", "Female"),
         ("Rohan", "Deshmukh", "B", "Male"), ("Sara", "Shaikh", "B", "Female")], start=2
    ):
        db.session.add(Student(
            organisation_id=org.id, school_id=s1.id, lab_id=lab1.id, job_role_id=jr_ddeo.id,
            academic_year="2025-26", class_grade="9", section=sec,
            roll_number=f"9{sec}-{i:02d}", first_name=fn, last_name=ln, gender=gender,
            date_of_enrolment=date(2025, 6, 10), verification_status="verified",
        ))
    db.session.flush()

    # --- users: one per role ---
    sa = _mkuser(org, "Super Admin", "sa@rnaf.demo", "SA")
    oa = _mkuser(org, "Org Admin", "oa@rnaf.demo", "OA")
    dm = _mkuser(org, "District Manager", "dm@rnaf.demo", "DM")
    pr = _mkuser(org, "Principal One", "pr@rnaf.demo", "PR", school_id=s1.id)
    vt = _mkuser(org, "Vocational Trainer", "vt@rnaf.demo", "VT", school_id=s1.id)
    db.session.flush()

    dm.districts.append(d1)
    dm.districts.append(d2)
    vt.labs.append(lab1)
    p1.user_id = pr.id

    # trainer profiles - one per job role in the lab (spec 1.5): the
    # 9-10 trainer is the one with the demo login.
    tr = Trainer(organisation_id=org.id, full_name="Vocational Trainer", school_id=s1.id,
                 lab_id=lab1.id, job_role_id=jr_ddeo.id, email="vt@rnaf.demo",
                 trainer_status="active", user_id=vt.id,
                 # what the admin records when the trainer is taken on (fictional)
                 phone="9800000011", gender="Female", date_of_joining=date(2024, 7, 1),
                 vtp_name="Demo Skills Pvt. Ltd.", appointment_nature="Contractual")
    tr2 = Trainer(organisation_id=org.id, full_name="Senior Vocational Trainer", school_id=s1.id,
                  lab_id=lab1.id, job_role_id=jr_jsd.id, email="vt2@rnaf.demo",
                  trainer_status="active")
    db.session.add_all([tr, tr2])

    db.session.commit()
    print("Seed complete. Logins (password: %s):" % DEMO_PASSWORD)
    for email in ["sa@rnaf.demo", "oa@rnaf.demo", "dm@rnaf.demo", "pr@rnaf.demo",
                  "vt@rnaf.demo"]:
        print("  -", email)

    return org

if __name__ == "__main__":
    run_seed()
