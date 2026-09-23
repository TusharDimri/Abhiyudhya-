"""Derives a Vocational Trainer's own subject/class-band associations.

A trainer's "subject" isn't a separate field to keep in sync - it's implied by
the lab(s) they're already assigned (the authoritative RBAC scope, see
rbac/scope.py). Each lab carries two job-role slots, one per class band (spec
Part 1.3: 9-10 and 11-12 can be the same job role or different). Deriving from
that single source avoids a second, independently-maintained association that
could drift out of sync with the trainer's actual lab assignment.
"""


def allowed_job_role_ids(user):
    """Job roles actually taught in this trainer's assigned lab(s)."""
    ids = set()
    for lab in getattr(user, "labs", None) or []:
        if lab.job_role_9_10_id:
            ids.add(lab.job_role_9_10_id)
        if lab.job_role_11_12_id:
            ids.add(lab.job_role_11_12_id)
    return ids


def allowed_class_grades(user, job_role_id):
    """Class grades this trainer may log against a given job role, based on
    which lab-slot (9-10 vs 11-12) that job role occupies in their lab(s)."""
    if job_role_id is None:
        return set()
    grades = set()
    for lab in getattr(user, "labs", None) or []:
        if lab.job_role_9_10_id and str(lab.job_role_9_10_id) == str(job_role_id):
            grades.update({"9", "10"})
        if lab.job_role_11_12_id and str(lab.job_role_11_12_id) == str(job_role_id):
            grades.update({"11", "12"})
    return grades


def class_grades_by_job_role(user):
    """{job_role_id (str) -> [grades]} for every job role this trainer may
    teach - drives the class dropdown in daily-entry forms (frontend UX)."""
    return {str(jr): sorted(allowed_class_grades(user, jr)) for jr in allowed_job_role_ids(user)}
