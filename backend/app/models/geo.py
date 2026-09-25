"""Where a record was made - PostGIS.

A model that mixes in `CapturesLocation` stores the point the user's device
reported when the record was created, how accurate that fix was, and when it
was taken. Stored as `geography(Point, 4326)` - plain latitude/longitude on
the WGS 84 globe, the same system phones and GPS use - so distances come out
in metres (ST_Distance, ST_DWithin) without any projection.
"""
from datetime import datetime

from geoalchemy2 import Geography, WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import DDL, Index, event
from sqlalchemy.orm import declared_attr

from app.extensions import db

# Tables PostGIS creates for itself - not ours, so never compared or migrated.
POSTGIS_TABLES = {"spatial_ref_sys"}

# `db.create_all()` (tests, a scratch database) needs the extension first.
# Migrations create it themselves (0005).
event.listen(
    db.metadata, "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS postgis").execute_if(dialect="postgresql"),
)


def include_object(obj, name, type_, reflected, compare_to):
    """Alembic filter: leave PostGIS's own tables out of autogenerate."""
    return not (type_ == "table" and name in POSTGIS_TABLES)


class CapturesLocation:
    location = db.Column(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
    location_accuracy_m = db.Column(db.Float)  # radius of uncertainty the device reported
    location_captured_at = db.Column(db.DateTime)  # UTC

    @declared_attr.directive
    def __table_args__(cls):
        # GiST: the index kind spatial queries ("within 200 m of the school") use
        return (Index(f"ix_{cls.__tablename__}_location", "location", postgresql_using="gist"),)

    def set_location(self, lat, lng, accuracy_m=None, captured_at=None):
        self.location = WKTElement(f"POINT({lng} {lat})", srid=4326)
        self.location_accuracy_m = accuracy_m
        self.location_captured_at = captured_at or datetime.utcnow()


# How close to their school a trainer must be to mark attendance.
ATTENDANCE_RADIUS_M = 1000


def point_wkt(lat, lng):
    return WKTElement(f"POINT({lng} {lat})", srid=4326)


def _km(metres):
    return f"{metres / 1000:,.1f} km" if metres < 100_000 else f"{metres / 1000:,.0f} km"


def school_distance_error(instance, school_id, radius_m=ATTENDANCE_RADIUS_M):
    """Record how far the device was from the school and refuse anything
    outside the radius. Measured by PostGIS on the globe, in metres.

    Only applies when the record carries a location (a trainer's); sets
    `instance.distance_from_school_m`. Returns an error message or None."""
    from sqlalchemy import func
    from app.models.geography import School

    latlng = point_to_latlng(instance.location)
    if latlng is None:
        return None
    school = db.session.get(School, school_id) if school_id else None
    if school is None or school.location is None:
        return ("Your school's location hasn't been set up yet, so attendance can't be "
                "checked. Ask your admin to add it (Schools \u2192 edit \u2192 Location).")
    lat, lng = latlng
    metres = db.session.query(
        func.ST_Distance(School.location, func.ST_GeogFromText(f"SRID=4326;POINT({lng} {lat})"))
    ).filter(School.id == school.id).scalar()
    instance.distance_from_school_m = round(float(metres), 1)
    if metres > radius_m:
        return (f"You're about {_km(metres)} from {school.name}. Attendance can only be "
                f"marked within {_km(radius_m)} of the school.")
    return None


def point_to_latlng(value):
    """A stored/pending point -> (lat, lng); None when there is none."""
    if not isinstance(value, (WKBElement, WKTElement)):
        return None
    pt = to_shape(value)
    return pt.y, pt.x
