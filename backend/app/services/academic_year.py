"""Which academic year a date belongs to.

A record's year comes from its own date, not from whichever year happens to
be marked current - a lecture held in September 2026 belongs to 2026-27 even
if nobody has rolled the "current" flag over yet, and a back-dated entry
belongs to the year it happened in.
"""
from datetime import date

from app.extensions import db


def school_year_label(d: date) -> str:
    """Fallback when the organisation hasn't set a year up: the Indian school
    year, June to May ("2026-27" for any date from 1 June 2026 to 31 May 2027)."""
    start = d.year if d.month >= 6 else d.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def academic_year_for(organisation_id, d: date) -> str | None:
    """The label of the organisation's academic year containing `d`."""
    if d is None:
        return None
    from app.models.masters import AcademicYear
    row = (
        db.session.query(AcademicYear.label)
        .filter(
            AcademicYear.organisation_id == organisation_id,
            AcademicYear.is_deleted.is_(False),
            AcademicYear.start_date <= d,
            AcademicYear.end_date >= d,
        )
        .order_by(AcademicYear.start_date.desc())
        .first()
    )
    return row[0] if row else school_year_label(d)


def current_year_label(organisation_id, today=None):
    """This academic year's label, worked out once per request."""
    from flask import g, has_app_context
    today = today or date.today()
    key = (organisation_id, today)
    cache = g.setdefault("_year_labels", {}) if has_app_context() else {}
    if key not in cache:
        cache[key] = academic_year_for(organisation_id, today)
    return cache[key]


def record_year(obj):
    """The academic year a record belongs to: its own academic_year, else the
    year of its date. None for records that aren't tied to a year (a school,
    a lab, a person)."""
    # a dated record belongs to its date's year (whatever year was sent with it)
    for attr in ("date", "reporting_date", "receipt_date"):
        d = getattr(obj, attr, None)
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d[:10])
            except ValueError:
                d = None
        if isinstance(d, date):
            return academic_year_for(getattr(obj, "organisation_id", None), d)
    label = getattr(obj, "academic_year", None)
    return label if _parse_label(label) is not None else None


def is_past_year(obj, today=None):
    """True for a record from an academic year that has already ended -
    those are closed: nobody but the super admin changes them."""
    label = record_year(obj)
    if label is None:
        return False
    current = _parse_label(current_year_label(getattr(obj, "organisation_id", None), today))
    mine = _parse_label(label)
    return current is not None and mine is not None and mine < current


PAST_YEAR_MESSAGE = "This record belongs to a previous academic year ({year}), which is closed - it can't be changed."
NEW_IN_PAST_MESSAGE = "That date falls in a previous academic year ({year}), which is closed - pick a date in this year."


def guard_closed_year(obj, user, creating=False):
    """Stop anyone but the super admin changing (or adding to) an academic
    year that has ended."""
    from flask import abort
    if getattr(user, "role", None) == "SA" or not is_past_year(obj):
        return
    msg = NEW_IN_PAST_MESSAGE if creating else PAST_YEAR_MESSAGE
    abort(400 if creating else 403, description=msg.format(year=record_year(obj)))


def _parse_label(label):
    """"2025-26" -> 2025; None for a label that isn't in that shape."""
    try:
        start = int(str(label)[:4])
        return start if str(label)[4] == "-" else None
    except (ValueError, IndexError):
        return None


def year_bounds(organisation_id, label):
    """(start, end) of an academic year: as the organisation set it up, else
    the June-May school year its label names. None if neither applies."""
    from app.models.masters import AcademicYear
    row = (
        db.session.query(AcademicYear.start_date, AcademicYear.end_date)
        .filter(AcademicYear.organisation_id == organisation_id, AcademicYear.label == label,
                AcademicYear.is_deleted.is_(False))
        .first()
    )
    if row and row[0] and row[1]:
        return row[0], row[1]
    start = _parse_label(label)
    if start is None:
        return None
    return date(start, 6, 1), date(start + 1, 5, 31)


def year_has_ended(organisation_id, label, today=None):
    bounds = year_bounds(organisation_id, label)
    return bool(bounds) and (today or date.today()) > bounds[1]


def next_year_label(organisation_id, label):
    """The academic year after `label`: the next one set up, else the next
    June-May school year."""
    from app.models.masters import AcademicYear
    bounds = year_bounds(organisation_id, label)
    if bounds:
        row = (
            db.session.query(AcademicYear.label)
            .filter(AcademicYear.organisation_id == organisation_id,
                    AcademicYear.is_deleted.is_(False),
                    AcademicYear.start_date > bounds[1])
            .order_by(AcademicYear.start_date.asc())
            .first()
        )
        if row:
            return row[0]
        start = bounds[0].year
    else:
        start = _parse_label(label)
        if start is None:
            return None
    # the June-May school year after the one that started in `start`
    return f"{start + 1}-{(start + 2) % 100:02d}"
