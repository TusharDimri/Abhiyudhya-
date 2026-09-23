"""Tenant-isolation RBAC suite - spec Part 7.7 (the highest-risk area).

Asserts a user from one org/scope can never read another's data, even by
guessing IDs. This suite is what substitutes for a staging soak (spec 7.6).
"""
import os
import pytest

os.environ["TESTING"] = "1"

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from tests.conftest import reset_schema  # noqa: E402
from app.models.organisation import Organisation  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.geography import State, District, School  # noqa: E402


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        reset_schema()
        yield app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _org_with_school(name, code):
    org = Organisation(name=name, org_code=code)
    db.session.add(org)
    db.session.flush()
    st = State(organisation_id=org.id, name="S")
    db.session.add(st)
    db.session.flush()
    dist = District(organisation_id=org.id, state_id=st.id, name="D")
    db.session.add(dist)
    db.session.flush()
    school = School(organisation_id=org.id, district_id=dist.id,
                    name=f"School {code}", udise_code=f"UD-{code}")
    db.session.add(school)
    db.session.flush()
    return org, school


def _mk_oa(org, email):
    u = User(organisation_id=org.id, full_name="OA", email=email, role="OA")
    u.set_password("Password@123")
    db.session.add(u)
    db.session.flush()
    return u


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": "Password@123"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def test_org_admin_cannot_see_other_org_schools(client, app):
    with app.app_context():
        orgA, schoolA = _org_with_school("Org A", "A")
        orgB, schoolB = _org_with_school("Org B", "B")
        _mk_oa(orgA, "a@a.com")
        _mk_oa(orgB, "b@b.com")
        db.session.commit()
        school_b_id = str(schoolB.id)

    token = _login(client, "a@a.com")
    hdr = {"Authorization": f"Bearer {token}"}

    # List: only Org A's school appears
    r = client.get("/api/schools", headers=hdr)
    assert r.status_code == 200
    names = [row["udise_code"] for row in r.get_json()["data"]]
    assert "UD-A" in names and "UD-B" not in names

    # Detail by guessed ID: forbidden
    r = client.get(f"/api/schools/{school_b_id}", headers=hdr)
    assert r.status_code == 403


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/schools").status_code == 401
