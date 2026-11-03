from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app.auth.forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm, VerifyOtpForm
from app.models import User, ProfileUpdate
from app.emails import send_reset_email, verify_reset_token, issue_email_otp, resend_email_otp, verify_email_otp
from app.extensions import db
from app.utils import is_safe_redirect

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
    form = RegisterForm()
    title = "Registration | CourseHub"
    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.lower().strip(),
            password_hash=form.password.data,
            is_instructor=form.teach.data,
            email_verified=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        session['pending_verification_user_id'] = user.id
        if issue_email_otp(user):
            flash('Account created. Check your email for the verification code.', 'success')
        else:
            flash('Account created, but the verification email could not be sent. Try resending it.', 'warning')
        return redirect(url_for('auth.verify_email'))
    return render_template('auth/register.html', form=form, title=title)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
    form = LoginForm()
    title = "Login | CourseHub"
    if request.method == 'GET':
        form.email.data = session.pop('prefill_email', None)   # filled in after registering

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('This account has been suspended.', 'danger')
                return render_template('auth/login.html', form=form)
            if not user.email_verified:
                session['pending_verification_user_id'] = user.id
                if user.otp_sent_at is None or user.otp_expires_at is None:
                    issue_email_otp(user)
                flash('Verify your email address before logging in.', 'info')
                return redirect(url_for('auth.verify_email'))
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page)
        else url_for('student.dashboard'))
        flash('Incorrect email or password.', 'danger')
    return render_template('auth/login.html', form=form, title=title)


@auth.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    user_id = session.get('pending_verification_user_id')
    user = db.session.get(User, user_id) if user_id else None
    if not user:
        flash('Start by registering or logging into an unverified account.', 'warning')
        return redirect(url_for('auth.login'))
    if user.email_verified:
        session.pop('pending_verification_user_id', None)
        return redirect(url_for('auth.login'))

    form = VerifyOtpForm()
    if form.validate_on_submit():
        success, message = verify_email_otp(user, form.otp.data.strip())
        db.session.commit()
        if success:
            session.pop('pending_verification_user_id', None)
            login_user(user)
            flash(message, 'success')
            return redirect(url_for('student.dashboard'))
        flash(message, 'danger')

    return render_template('auth/verify_email.html', form=form, user=user, title='Verify your email | CourseHub')


@auth.route('/verify-email/resend', methods=['POST'])
def resend_verification():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    user_id = session.get('pending_verification_user_id')
    user = db.session.get(User, user_id) if user_id else None
    if not user:
        flash('Your verification session has expired. Log in again.', 'warning')
        return redirect(url_for('auth.login'))
    if user.email_verified:
        session.pop('pending_verification_user_id', None)
        return redirect(url_for('auth.login'))

    success, message = resend_email_otp(user)
    db.session.commit()
    flash(message, 'success' if success else 'warning')
    return redirect(url_for('auth.verify_email'))


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    title = "Forgotten Password || CourseHub"
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.is_active_account:
            send_reset_email(user)
        # The same message either way, so nobody can use this form to find out who has an account
        flash("If that email is registered, we've sent a link to reset your password. "
              "Check your inbox and your spam folder.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form, title=title)


@auth.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))

    user = verify_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.add(ProfileUpdate(user_id=user.id, summary="Password reset"))
        db.session.commit()
        flash("Your password has been updated. Log in with your new password.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)