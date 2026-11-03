import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app, render_template, url_for
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadSignature
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, mail

RESET_SALT = "password-reset"
RESET_MAX_AGE = 30 * 60            # the link works for 30 minutes
OTP_MAX_AGE = 10 * 60
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_RESEND_MAX_PER_HOUR = 5


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _send_otp_email(user, otp):
    minutes = OTP_MAX_AGE // 60

    if not current_app.config.get("MAIL_USERNAME") or not current_app.config.get("MAIL_PASSWORD"):
        if current_app.debug:
            current_app.logger.warning("Mail is not configured. Verification code for %s: %s", user.email, otp)
        else:
            current_app.logger.error("Mail is not configured, so the verification email was not sent.")
        return False

    msg = Message(subject="Verify your CourseHub email", recipients=[user.email])
    msg.body = render_template("emails/verify_email.txt", user=user, otp=otp, minutes=minutes)
    msg.html = render_template("emails/verify_email.html", user=user, otp=otp, minutes=minutes)
    try:
        mail.send(msg)
        current_app.logger.info("Email verification OTP sent to %s", user.email)
        return True
    except Exception:
        current_app.logger.exception("Could not send verification OTP to %s", user.email)
        return False


def _issue_otp(user):
    now = _utc_now()
    otp = f"{secrets.randbelow(1000000):06d}"
    user.otp_hash = generate_password_hash(otp)
    user.otp_expires_at = now + timedelta(seconds=OTP_MAX_AGE)
    user.otp_sent_at = now
    user.otp_attempts = 0
    sent = _send_otp_email(user, otp)
    db.session.commit()
    return sent


def issue_email_otp(user):
    if user.email_verified:
        return False
    now = _utc_now()
    window_start = user.otp_resend_window_start
    if window_start is None or now - window_start >= timedelta(hours=1):
        user.otp_resend_count = 0
        user.otp_resend_window_start = now
    user.otp_resend_count = (user.otp_resend_count or 0) + 1
    return _issue_otp(user)


def resend_email_otp(user):
    now = _utc_now()
    window_start = user.otp_resend_window_start
    if window_start is None or now - window_start >= timedelta(hours=1):
        user.otp_resend_count = 0
        user.otp_resend_window_start = now

    if user.otp_sent_at and now - user.otp_sent_at < timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
        remaining = OTP_RESEND_COOLDOWN_SECONDS - int((now - user.otp_sent_at).total_seconds())
        return False, f"Please wait {remaining} seconds before requesting another code."

    if user.otp_resend_count >= OTP_RESEND_MAX_PER_HOUR:
        return False, "You have reached the resend limit. Try again in about an hour."

    user.otp_resend_count += 1
    if _issue_otp(user):
        return True, "A new verification code has been sent."
    return False, "The code could not be sent. Check the mail configuration and try again."


def verify_email_otp(user, otp):
    now = _utc_now()
    if user.email_verified:
        return True, "Email already verified."
    if user.otp_expires_at is None or now > user.otp_expires_at:
        return False, "That code has expired. Request a new one."
    if user.otp_attempts >= 5:
        return False, "Too many incorrect attempts. Request a new code."
    if not user.otp_hash or not otp.isdigit() or not check_password_hash(user.otp_hash, otp):
        user.otp_attempts = (user.otp_attempts or 0) + 1
        return False, "The verification code is incorrect."

    user.email_verified = True
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    return True, "Your email has been verified."


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def _fingerprint(user):
    """Changes whenever the password changes, which makes each link single-use."""
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:20]


def make_reset_token(user):
    return _serializer().dumps({"id": user.id, "h": _fingerprint(user)})


def verify_reset_token(token):
    """Return the user for a valid, unexpired, unused token, otherwise None."""
    from app.models import User
    try:
        data = _serializer().loads(token, max_age=RESET_MAX_AGE)
    except BadSignature:                       # also covers expired tokens
        return None
    user = db.session.get(User, data.get("id"))
    if not user or not user.is_active_account or data.get("h") != _fingerprint(user):
        return None
    return user


def send_reset_email(user):
    link = url_for("auth.reset_password", token=make_reset_token(user), _external=True)
    minutes = RESET_MAX_AGE // 60

    if not current_app.config.get("MAIL_USERNAME") or not current_app.config.get("MAIL_PASSWORD"):
        if current_app.debug:
            current_app.logger.warning("Mail is not configured. Reset link for %s: %s", user.email, link)
        else:
            current_app.logger.error("Mail is not configured, so no reset email was sent.")
        return False

    msg = Message(subject="Reset your CourseHub password", recipients=[user.email])
    msg.body = render_template("emails/reset_password.txt", user=user, link=link, minutes=minutes)
    msg.html = render_template("emails/reset_password.html", user=user, link=link, minutes=minutes)
    try:
        mail.send(msg)
        current_app.logger.info("Password reset email sent to %s", user.email)
        return True
    except Exception:
        current_app.logger.exception("Could not send the password reset email to %s", user.email)
        return False