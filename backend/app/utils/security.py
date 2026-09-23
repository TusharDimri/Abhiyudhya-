"""Security helpers: password policy + response headers."""
import re

# Enterprise-reasonable policy: length + mixed character classes, no hard 128 cap
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")


def validate_password(pw: str):
    """Return (ok, message). Kept lenient enough not to frustrate users."""
    if not pw or len(pw) < 8:
        return False, "Password must be at least 8 characters"
    if len(pw) > 128:
        return False, "Password must be at most 128 characters"
    checks = sum(bool(rx.search(pw)) for rx in (_UPPER, _LOWER, _DIGIT))
    if checks < 2:
        return False, "Password must mix upper/lower case letters and numbers"
    return True, ""


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "0",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # API returns JSON only; a tight CSP is safe and blocks injected script/frames.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def apply_security_headers(response, is_prod: bool):
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if is_prod:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response
