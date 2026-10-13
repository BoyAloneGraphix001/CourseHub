from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError

from app.utils import to_embed_url

LEVELS = [("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")]


class CourseForm(FlaskForm):
    title = StringField("Course title", validators=[DataRequired(), Length(min=3, max=150)])
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    level = SelectField("Level", choices=LEVELS, validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])
    thumbnail = FileField("Course thumbnail", validators=[
        Optional(), FileAllowed(["png", "jpg", "jpeg", "webp"], "Images only.")])
    submit = SubmitField("Save course")


class SectionForm(FlaskForm):
    title = StringField("Section title", validators=[DataRequired(), Length(min=2, max=150)])
    submit = SubmitField("Add section")


class LessonForm(FlaskForm):
    title = StringField("Lesson title", validators=[DataRequired(), Length(min=2, max=150)])
    video_url = StringField("Video link", validators=[Optional(), Length(max=300)])
    body = TextAreaField("Lesson text", validators=[Optional(), Length(max=10000)])
    submit = SubmitField("Save lesson")

    def validate_video_url(self, field):
        if field.data and field.data.strip() and to_embed_url(field.data) is None:
            raise ValidationError("Use a YouTube or Vimeo link.")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        if ok and not (self.video_url.data or "").strip() and not (self.body.data or "").strip():
            self.body.errors = list(self.body.errors) + ["Add a video link or some text for this lesson."]
            return False
        return ok