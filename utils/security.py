"""
Cross-cutting security helpers: secure HTTP headers, session-based auth
decorators, and RBAC enforcement.
"""
from functools import wraps
from flask import session, redirect, url_for, request, jsonify, abort


def apply_secure_headers(response):
    """Attach standard hardening headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["X-XSS-Protection"] = "0"  # superseded by CSP; explicit off avoids legacy quirks
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
        "style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


def _wants_json():
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if _wants_json():
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            if _wants_json():
                return jsonify({"error": "Admin privileges required."}), 403
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def anonymous_only(view):
    """Prevents already-authenticated users from re-hitting login/signup."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("user_id") or session.get("role") == "admin":
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)
    return wrapped
