from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError

from app.models import Category


class CategoryForm(FlaskForm):
    name = StringField('Category name', validators=[DataRequired(), Length(min=2, max=80)])
    submit = SubmitField('Add category')

    def __init__(self, *args, exclude_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exclude_id = exclude_id          # set when renaming, so a category can keep its own name

    def validate_name(self, field):
        query = Category.query.filter(func.lower(Category.name) == field.data.strip().lower())
        if self.exclude_id:
            query = query.filter(Category.id != self.exclude_id)
        if query.first():
            raise ValidationError('That category already exists.')