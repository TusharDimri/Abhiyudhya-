"""Three test schools for trying out location tracking.

Run after `flask seed`:   flask test-schools

Each school sits on a well-known public landmark, so its coordinates are easy
to type into the browser's location override (Chrome DevTools -> Sensors):

    Test School A - Delhi       India Gate          28.6129, 77.2295
    Test School B - Mumbai      Gateway of India    18.9220, 72.8347
    Test School C - Bengaluru   Vidhana Soudha      12.9796, 77.5907

and gets a lab, a trainer login and a principal login (password Password@123):

    vt.a@test.demo / pr.a@test.demo   ...   vt.c@test.demo / pr.c@test.demo

Everything is fictional apart from the landmark coordinates. Running it again
changes nothing.
"""
from datetime import date

from app.extensions import db
from app.models.geo import point_wkt
from app.models.geography import District, Principal, School, State
from app.models.lab import Lab, Trainer
from app.models.masters import JobRole, Sector
from app.models.organisation import Organisation
from app.models.user import User

PASSWORD = "Password@123"
SCHOOLS = [
    # key, school, district, landmark, lat, lng, school type
    ("a", "Test School A - Delhi", "Test District Delhi", "India Gate", 28.6129, 77.2295, "Co-education"),
    ("b", "Test School B - Mumbai", "Test District Mumbai", "Gateway of India", 18.9220, 72.8347, "Girls"),
    ("c", "Test School C - Bengaluru", "Test District Bengaluru", "Vidhana Soudha", 12.9796, 77.5907, "Boys"),
]


def _user(org, name, email, role, **scope):
    u = db.session.query(User).filter_by(email=email).first()
    if u is None:
        u = User(organisation_id=org.id, full_name=name, email=email, role=role, **scope)
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.flush()
    return u


def run_test_schools():
    org = db.session.query(Organisation).filter_by(org_code="RNAF-DEMO").first()
    if org is None:
        print("Run `flask seed` first - there is no demo organisation yet.")
        return
    state = db.session.query(State).filter_by(organisation_id=org.id).first()
    sector = db.session.query(Sector).filter_by(organisation_id=org.id, name="IT/ITeS").first()
    jr_low = db.session.query(JobRole).filter_by(organisation_id=org.id, name="Domestic Data Entry Operator").first()
    jr_high = db.session.query(JobRole).filter_by(organisation_id=org.id, name="Junior Software Developer").first()

    print("Test schools (password for every login: %s)" % PASSWORD)
    for n, (key, name, district_name, landmark, lat, lng, kind) in enumerate(SCHOOLS, start=1):
        district = db.session.query(District).filter_by(organisation_id=org.id, name=district_name).first()
        if district is None:
            district = District(organisation_id=org.id, state_id=state.id, name=district_name, code=f"T{key.upper()}")
            db.session.add(district)
            db.session.flush()
        school = db.session.query(School).filter_by(organisation_id=org.id, name=name).first()
        if school is None:
            school = School(organisation_id=org.id, district_id=district.id, name=name,
                            udise_code=f"9900000000{n}", block=f"Test Block {key.upper()}",
                            address=f"Next to {landmark}", school_type=kind,
                            email=f"school.{key}@test.demo", phone=f"011-2000000{n}")
            school.location = point_wkt(lat, lng)
            db.session.add(school)
            db.session.flush()
        lab = db.session.query(Lab).filter_by(school_id=school.id).first()
        if lab is None:
            lab = Lab(organisation_id=org.id, name=f"IT Lab - Test {key.upper()}", sector_id=sector.id,
                      school_id=school.id, job_role_9_10_id=jr_low.id, job_role_11_12_id=jr_high.id,
                      curriculum_level="1-4", sections_9="A", sections_10="A", sections_11="A", sections_12="A")
            db.session.add(lab)
            db.session.flush()

        vt = _user(org, f"Trainer {key.upper()}", f"vt.{key}@test.demo", "VT", school_id=school.id)
        if lab not in vt.labs:
            vt.labs.append(lab)
        if db.session.query(Trainer).filter_by(user_id=vt.id).first() is None:
            db.session.add(Trainer(organisation_id=org.id, full_name=f"Trainer {key.upper()}", school_id=school.id,
                                   lab_id=lab.id, job_role_id=jr_low.id, email=vt.email, phone=f"98000001{n}0",
                                   gender="Female", trainer_status="active", user_id=vt.id,
                                   date_of_joining=date(2025, 7, 1), vtp_name="Test Skills Pvt. Ltd.",
                                   appointment_nature="Contractual"))
        pr = _user(org, f"Principal {key.upper()}", f"pr.{key}@test.demo", "PR", school_id=school.id)
        if db.session.query(Principal).filter_by(user_id=pr.id).first() is None:
            p = Principal(organisation_id=org.id, full_name=f"Principal {key.upper()}", email=pr.email,
                          mobile=f"98000002{n}0", linked_school_id=school.id, user_id=pr.id,
                          designation="Principal", employee_id=f"EMP-TEST-{key.upper()}", gender="Male",
                          appointment_nature="Regular", date_of_joining=date(2022, 6, 1))
            db.session.add(p)
            db.session.flush()
            school.principal_id = p.id
        print(f"  {name:<28} {landmark:<18} {lat:.4f}, {lng:.4f}   vt.{key}@test.demo   pr.{key}@test.demo")
    db.session.commit()
