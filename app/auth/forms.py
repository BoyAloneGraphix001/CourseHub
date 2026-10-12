from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
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
        user = User.query.filter_by(
            username = username.data).first()
        if user:
            raise ValidationError('This username is taken, please enter a different one')

    def validate_email(self, email):
            user = User.query.filter_by(
                email = email.data.lower().strip()).first()
            if user:
                raise ValidationError('That email is already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Log in')