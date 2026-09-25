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
