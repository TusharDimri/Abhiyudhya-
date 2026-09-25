"""Redis cache for read endpoints.

Every GET the app serves - lists, records, the bootstrap bundle, dashboards,
yearly targets - is cached per user (so each role's scoping is kept) under
its organisation's *data version*. Any write in an organisation bumps that
version, so its cached reads stop matching at once: nobody is shown data
from before their own save, and there is no invalidation list to keep in
step with the code. Platform-wide views (a Super Admin across organisations)
use a global version that every write bumps.

Redis being unreachable never breaks a request - it just isn't cached.
"""
import hashlib
import logging

from flask import current_app, has_app_context, request, Response
from sqlalchemy import event
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_client = None
_client_url = None


def _redis():
    """A shared client, or None when caching is off or Redis is down."""
    global _client, _client_url
    cfg = current_app.config
    if not cfg.get("CACHE_ENABLED", True):
        return None
    url = cfg.get("CACHE_REDIS_URL") or cfg.get("REDIS_URL")
    if _client is None or _client_url != url:
        import redis
        _client = redis.Redis.from_url(url, socket_timeout=0.3, socket_connect_timeout=0.3)
        _client_url = url
    return _client


def _prefix():
    return current_app.config.get("CACHE_PREFIX", "rnaf")


def _version_key(org_id):
    return f"{_prefix()}:v:{org_id or 'all'}"


def _versions(r, org_id):
    raw = r.mget(_version_key(org_id), _version_key(None))
    return ":".join((v or b"0").decode() for v in raw)


def bump(org_ids):
    """Mark everything cached for these organisations (and platform-wide) stale."""
    try:
        r = _redis()
        if r is None:
            return
        pipe = r.pipeline()
        for org in {o for o in org_ids if o}:
            pipe.incr(_version_key(org))
        pipe.incr(_version_key(None))
        pipe.execute()
    except Exception as exc:  # noqa: BLE001 - cache trouble never fails a write
        log.warning("cache: could not invalidate (%s)", exc)


def cached_json(namespace, ttl=120):
    """Decorator for a GET view (placed under @login_required): serve the
    JSON from Redis when this user already asked the same thing since the
    organisation last changed."""
    from functools import wraps

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if request.method != "GET":
                return fn(*args, **kwargs)
            try:
                r = _redis()
            except Exception:  # noqa: BLE001
                r = None
            if r is None:
                return fn(*args, **kwargs)
            from app.rbac import current_user
            user = current_user()
            try:
                versions = _versions(r, user.organisation_id)
                ask = hashlib.sha1(request.full_path.encode()).hexdigest()
                key = f"{_prefix()}:{namespace}:{user.id}:{versions}:{ask}"
                hit = r.get(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("cache: read skipped (%s)", exc)
                return fn(*args, **kwargs)
            if hit is not None:
                resp = Response(hit, mimetype="application/json")
                resp.headers["X-Cache"] = "HIT"
                return resp

            resp = current_app.make_response(fn(*args, **kwargs))
            if resp.status_code == 200 and resp.is_json:
                try:
                    r.setex(key, ttl, resp.get_data())
                except Exception as exc:  # noqa: BLE001
                    log.warning("cache: write skipped (%s)", exc)
            resp.headers["X-Cache"] = "MISS"
            return resp
        return wrapper
    return decorator


def _collect(session, flush_context):
    touched = session.info.setdefault("cache_orgs", set())
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        if type(obj).__name__ == "Organisation":
            touched.add(getattr(obj, "id", None))
        touched.add(getattr(obj, "organisation_id", None))


def _invalidate(session):
    touched = session.info.pop("cache_orgs", None)
    if touched and has_app_context():
        bump(touched)


def _forget(session):
    session.info.pop("cache_orgs", None)


def init_app(app):
    """Bump an organisation's data version whenever a commit touched any of
    its rows - whichever endpoint, workflow or script made the change.

    The hooks are process-wide and hold no app: installed once, however many
    apps get created (the test suite makes one per test)."""
    if event.contains(Session, "after_commit", _invalidate):
        return
    event.listen(Session, "after_flush", _collect)
    event.listen(Session, "after_commit", _invalidate)
    event.listen(Session, "after_rollback", _forget)
