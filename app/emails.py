import hashlib

from flask import current_app, render_template, url_for
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadSignature

from app.extensions import db, mail

RESET_SALT = "password-reset"
RESET_MAX_AGE = 30 * 60            # the link works for 30 minutes


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