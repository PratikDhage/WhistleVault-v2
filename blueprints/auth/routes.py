import re
import hashlib
import secrets
import hmac
from datetime import datetime

from flask import render_template, request, redirect, url_for, session, flash, current_app, jsonify
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash

from extensions import db, bcrypt, limiter
from models import User, OTP
from utils.email import email_service
from utils.security import anonymous_only
from . import auth_bp

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_signup(username, email, password):
    errors = []
    if not USERNAME_RE.match(username or ""):
        errors.append("Username must be 3-32 characters: letters, numbers, underscores only.")
    if not EMAIL_RE.match(email or ""):
        errors.append("Enter a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    return errors


def _password_reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="password-reset")


@auth_bp.route("/api/check-availability")
@limiter.limit("60 per minute")
def check_availability():
    field = (request.args.get("field") or "").strip()
    value = (request.args.get("value") or "").strip()
    if field == "username":
        valid = bool(USERNAME_RE.match(value))
        exists = valid and db.session.query(User.id).filter(
            func.lower(User.username) == value.lower()
        ).first() is not None
    elif field == "email":
        value = value.lower()
        valid = bool(EMAIL_RE.match(value))
        exists = valid and db.session.query(User.id).filter(User.email == value).first() is not None
    else:
        return jsonify({"error": "Invalid availability field."}), 400

    response = jsonify({"available": valid and not exists, "valid": valid})
    response.headers["Cache-Control"] = "no-store"
    return response


@auth_bp.route("/signup", methods=["GET", "POST"])
@anonymous_only
@limiter.limit("10 per hour")
def signup():
    if request.method == "GET":
        return render_template("auth/signup.html")

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    errors = _validate_signup(username, email, password)
    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("auth/signup.html", username=username, email=email), 400

    existing = User.query.filter(
        or_(func.lower(User.username) == username.lower(), User.email == email)
    ).first()
    if existing:
        flash("An account with that username or email already exists.", "error")
        return render_template("auth/signup.html", username=username, email=email), 409

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(username=username, email=email, password_hash=pw_hash, is_verified=False)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("That username or email was just registered. Please choose another.", "error")
        return render_template("auth/signup.html", username=username, email=email), 409

    _issue_otp(user)

    session["pending_verification_user_id"] = user.id
    flash("Account created. Enter the verification code we sent to your email.", "success")
    return redirect(url_for("auth.verify_otp"))


def _issue_otp(user: User):
    code = OTP.generate_code(current_app.config["OTP_LENGTH"])
    otp = OTP(
        user_id=user.id,
        code_hash=bcrypt.generate_password_hash(code).decode("utf-8"),
        expires_at=OTP.new_expiry(current_app.config["OTP_EXPIRY_MINUTES"]),
    )
    db.session.add(otp)
    db.session.commit()
    email_service.send_otp_email(user.email, code)


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def verify_otp():
    user_id = session.get("pending_verification_user_id")
    if not user_id:
        flash("Start by creating an account first.", "error")
        return redirect(url_for("auth.signup"))

    user = User.query.get(user_id)
    if not user or user.is_verified:
        session.pop("pending_verification_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "GET":
        return render_template("auth/verify_otp.html", email=user.email)

    code = (request.form.get("code") or "").strip()
    otp = (
        OTP.query.filter_by(user_id=user.id, consumed=False)
        .order_by(OTP.created_at.desc())
        .first()
    )

    if not otp or otp.is_expired():
        flash("That code expired. Request a new one.", "error")
        return render_template("auth/verify_otp.html", email=user.email), 400

    if otp.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        flash("Too many incorrect attempts. Request a new code.", "error")
        return render_template("auth/verify_otp.html", email=user.email), 429

    if not bcrypt.check_password_hash(otp.code_hash, code):
        otp.attempts += 1
        db.session.commit()
        flash("Incorrect code. Please try again.", "error")
        return render_template("auth/verify_otp.html", email=user.email), 400

    otp.consumed = True
    user.is_verified = True
    db.session.commit()
    session.pop("pending_verification_user_id", None)

    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-otp", methods=["POST"])
@limiter.limit("5 per hour")
def resend_otp():
    user_id = session.get("pending_verification_user_id")
    user = User.query.get(user_id) if user_id else None
    if not user or user.is_verified:
        return redirect(url_for("auth.login"))
    _issue_otp(user)
    flash("A new verification code has been sent.", "success")
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/login", methods=["GET", "POST"])
@anonymous_only
@limiter.limit("15 per hour")
def login():
    if request.method == "GET":
        return render_template("auth/login.html", next=request.args.get("next", ""))

    identifier = (request.form.get("identifier") or "").strip()
    password = request.form.get("password") or ""
    next_url = request.form.get("next") or url_for("main.dashboard")

    # --- Single hardcoded admin account (RBAC: admin role) ---
    admin_username = current_app.config["ADMIN_USERNAME"]
    admin_password = current_app.config["ADMIN_PASSWORD"]
    admin_password_hash = current_app.config.get("ADMIN_PASSWORD_HASH")
    admin_password_valid = (
        check_password_hash(admin_password_hash, password)
        if admin_password_hash
        else hmac.compare_digest(password, admin_password or "")
    )
    if hmac.compare_digest(identifier, admin_username) and admin_password_valid:
        session.clear()
        session.permanent = True
        session["role"] = "admin"
        session["display_name"] = admin_username
        flash("Welcome back, admin.", "success")
        return redirect(url_for("admin.dashboard"))

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        flash("Invalid credentials.", "error")
        return render_template("auth/login.html", next=next_url), 401

    if not user.is_active:
        flash("This account has been disabled.", "error")
        return render_template("auth/login.html", next=next_url), 403

    if not user.is_verified:
        session["pending_verification_user_id"] = user.id
        flash("Please verify your email before logging in.", "error")
        return redirect(url_for("auth.verify_otp"))

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["role"] = "user"
    session["display_name"] = user.username
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    return redirect(next_url if next_url.startswith("/") else url_for("main.dashboard"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@anonymous_only
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot_password.html")

    email = (request.form.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first() if EMAIL_RE.match(email) else None
    if user:
        nonce = secrets.token_urlsafe(32)
        user.password_reset_token_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        db.session.commit()
        token = _password_reset_serializer().dumps({"user_id": user.id, "nonce": nonce})
        reset_url = url_for("auth.reset_password", token=token, _external=True)
        email_service.send_password_reset_email(user.email, reset_url)

    flash("If an account exists for that email, a password reset link has been sent.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@anonymous_only
@limiter.limit("10 per hour")
def reset_password(token):
    try:
        payload = _password_reset_serializer().loads(
            token, max_age=current_app.config["PASSWORD_RESET_EXPIRY_MINUTES"] * 60
        )
    except (BadSignature, SignatureExpired):
        flash("That password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.get(payload.get("user_id"))
    nonce = payload.get("nonce") or ""
    nonce_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
    if not user or not user.is_active or not user.password_reset_token_hash or not secrets.compare_digest(
        user.password_reset_token_hash, nonce_hash
    ):
        flash("That password reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "GET":
        return render_template("auth/reset_password.html", token=token)

    password = request.form.get("password") or ""
    confirmation = request.form.get("confirmation") or ""
    if len(password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return render_template("auth/reset_password.html", token=token), 400
    if password != confirmation:
        flash("Passwords do not match.", "error")
        return render_template("auth/reset_password.html", token=token), 400

    user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user.password_reset_token_hash = None
    db.session.commit()
    flash("Your password has been reset. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.feed"))
