from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import Optional, Length


class SearchForm(FlaskForm):
    """Catalog search and filters. Submitted with GET, so CSRF is switched off
    (a search changes nothing on the server)."""

    class Meta:
        csrf = False

    q = StringField('Search', validators=[Optional(), Length(max=100)],
                    filters=[lambda v: v.strip() if v else v])
    category = StringField('Category', validators=[Optional(), Length(max=80)])
    level = SelectField('Level', validators=[Optional()], choices=[
        ('', 'Any level'),
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ])