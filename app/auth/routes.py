from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app.auth.forms import RegisterForm, LoginForm
from app.models import User
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
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Account created. Log in to continue.', 'success')
        # session['prefill_email'] = user.email
        return redirect(url_for('auth.login'))
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
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page)
        else url_for('student.dashboard'))
        flash('Incorrect email or password.', 'danger')
    return render_template('auth/login.html', form=form, title=title)


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))