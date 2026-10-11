"""Role definitions and the access model.

Roles (from spec Part 0.2):
  SA  Super Admin            - creates orgs + org admins; full cross-org access
  OA  Organisation Admin     - full access inside one org
  DM  District Manager       - scoped to one or more districts
  DEPT Department Login      - scoped to one or more districts; reads a few lists, changes nothing
  PR  Principal / Headmaster  - scoped to their school; endorses attendance/reports
  VT  Vocational Trainer     - scoped to their lab(s) + job role(s)

Students are records managed by staff; they never log in.
"""
from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "SA"
    ORG_ADMIN = "OA"
    DISTRICT_MANAGER = "DM"
    DEPARTMENT = "DEPT"
    PRINCIPAL = "PR"
    TRAINER = "VT"


ROLE_LABELS = {
    Role.SUPER_ADMIN: "Super Admin",
    Role.ORG_ADMIN: "Organisation Admin",
    Role.DISTRICT_MANAGER: "District Manager",
    Role.DEPARTMENT: "Department Login",
    Role.PRINCIPAL: "Principal / Headmaster",
    Role.TRAINER: "Vocational Trainer",
}

# Roles whose scope is the district(s) they hold (user_district).
DISTRICT_ROLES = (Role.DISTRICT_MANAGER.value, Role.DEPARTMENT.value)

# Roles that are not bound to a single organisation.
CROSS_ORG_ROLES = {Role.SUPER_ADMIN}

# Ordering used for "at least this privileged" style checks (higher = more).
ROLE_RANK = {
    Role.TRAINER: 1,
    Role.PRINCIPAL: 2,
    Role.DISTRICT_MANAGER: 3,
    Role.DEPARTMENT: 3,
    Role.ORG_ADMIN: 4,
    Role.SUPER_ADMIN: 5,
}


def all_roles():
    return [r.value for r in Role]
