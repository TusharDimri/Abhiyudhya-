"""Sealed location fixes.

The browser keeps the user's last location fix in session storage, where
anyone with developer tools can edit it. So the fix is sealed by the server
the moment it is taken: an HMAC over who took it, the coordinates, the
accuracy, the device's timestamp and the server's own clock. A record is only
stamped with a fix whose seal still matches - edit any part of it, reuse
someone else's, or keep one past its window, and it is refused.

(What no website can stop is a faked position at the moment of detection -
a browser's sensor override or a fake-GPS app. Checks such as "within N
metres of the school" are the defence against that, done on the stored point.)
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from flask import current_app

# How long a sealed fix may be used for. The browser re-detects after 10
# minutes; the rest is room for a long form and clock differences.
VALID_FOR = timedelta(minutes=30)


class LocationError(ValueError):
    """The fix sent is unusable; the message says why, for the user."""


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _message(user_id, lat, lng, accuracy, captured_at, issued_at):
    acc = "" if accuracy is None else f"{accuracy:.1f}"
    return f"{user_id}|{lat:.7f}|{lng:.7f}|{acc}|{captured_at}|{issued_at}".encode()


def _sign(msg):
    key = current_app.config["SECRET_KEY"].encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _numbers(lat, lng, accuracy):
    try:
        lat, lng = float(lat), float(lng)
        accuracy = None if accuracy is None else round(float(accuracy), 1)
    except (TypeError, ValueError):
        raise LocationError("The location sent was not valid.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (accuracy is not None and accuracy < 0):
        raise LocationError("The location sent was not valid.")
    return lat, lng, accuracy


def seal(user_id, lat, lng, accuracy=None, captured_at=None):
    """A just-detected fix, signed. Returns what the browser stores."""
    lat, lng, accuracy = _numbers(lat, lng, accuracy)
    issued_at = _now().isoformat()
    captured_at = str(captured_at or issued_at)
    return {
        "lat": lat, "lng": lng, "accuracy": accuracy,
        "captured_at": captured_at, "issued_at": issued_at,
        "sig": _sign(_message(user_id, lat, lng, accuracy, captured_at, issued_at)),
    }


def verify(user_id, fix):
    """(lat, lng, accuracy, captured_at as naive UTC) from a sealed fix, or
    LocationError."""
    fix = fix or {}
    lat, lng, accuracy = _numbers(fix.get("lat"), fix.get("lng"), fix.get("accuracy"))
    captured_at, issued_at, sig = fix.get("captured_at"), fix.get("issued_at"), fix.get("sig")
    if not (captured_at and issued_at and isinstance(sig, str)):
        raise LocationError("Your location couldn't be verified. Click “Detect My Location” and save again.")
    expected = _sign(_message(user_id, lat, lng, accuracy, str(captured_at), str(issued_at)))
    if not hmac.compare_digest(expected, sig):
        raise LocationError("Your location couldn't be verified. Click “Detect My Location” and save again.")
    issued = datetime.fromisoformat(str(issued_at))
    if _now() - issued > VALID_FOR:
        raise LocationError("Your location is out of date. Click “Detect My Location” and save again.")
    try:
        at = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        at = at.astimezone(timezone.utc).replace(tzinfo=None) if at.tzinfo else at
    except ValueError:
        at = issued.replace(tzinfo=None)
    return lat, lng, accuracy, at
