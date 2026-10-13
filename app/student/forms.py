from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from sqlalchemy import func
from wtforms import StringField, TextAreaField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, EqualTo, Regexp, ValidationError

from app.models import User


class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(), Length(min=3, max=30),
        Regexp(r'^[A-Za-z0-9_.-]+$', message='Use letters, numbers, dots, dashes or underscores.')])
    headline = StringField('Headline', validators=[Optional(), Length(max=150)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=1000)])
    picture = FileField('Profile picture', validators=[
        Optional(), FileAllowed(['png', 'jpg', 'jpeg', 'webp'], 'Images only.')])
    submit = SubmitField('Save changes')

    def validate_username(self, field):
        taken = User.query.filter(func.lower(User.username) == field.data.strip().lower(),
                                  User.id != current_user.id).first()
        if taken:
            raise ValidationError('That username is taken.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current password', validators=[DataRequired()])
    new_password = PasswordField('New password', validators=[
        DataRequired(), Length(min=8, message='Use at least 8 characters.')])
    confirm = PasswordField('Confirm new password', validators=[
        DataRequired(), EqualTo('new_password', message='Passwords do not match.')])
    submit = SubmitField('Update password')


class ReportForm(FlaskForm):
    reason = TextAreaField('What is wrong with this course?', validators=[
        DataRequired(), Length(min=10, max=1000,
                               message='Please write between 10 and 1000 characters.')])
    submit = SubmitField('Send report')