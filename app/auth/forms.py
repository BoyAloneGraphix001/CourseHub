from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from sqlalchemy import func
from app.models import User


class RegisterForm(FlaskForm):
    username = StringField('Full name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(), Length(min=8, message='Use at least 8 characters.')])
    confirm = PasswordField('Confirm password', validators=[
        DataRequired(), EqualTo('password', message='Passwords do not match.')])
    teach = BooleanField('Become an instructor too')
    submit = SubmitField('Create account')


    def validate_username(self, username):
        user = User.query.filter(
            func.lower(User.username) == username.data.strip().lower()).first()
        if user:
            raise ValidationError('This username is taken, please enter a different one')

    def validate_email(self, email):
            user = User.query.filter(
                func.lower(User.email) == email.data.lower().strip()).first()
            if user:
                raise ValidationError('That email is already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Log in')


class VerifyOtpForm(FlaskForm):
    otp = StringField('Verification code', validators=[
        DataRequired(),
        Length(min=6, max=6, message='Enter the 6-digit code.')
    ])
    submit = SubmitField('Verify email')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send reset link')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New password', validators=[
        DataRequired(), Length(min=8, message='Use at least 8 characters.')])
    confirm = PasswordField('Confirm new password', validators=[
        DataRequired(), EqualTo('password', message='Passwords do not match.')])
    submit = SubmitField('Update password')