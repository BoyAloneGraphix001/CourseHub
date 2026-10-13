import click
from app.extensions import db
from app.models import User, Category


def register_commands(app):
    @app.cli.command("create-admin")        # this line makes "flask create-admin" a real command
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username, email, password):
        ...
        user = User(username=username, email=email, is_admin=True, is_instructor=True)
        user.set_password(password)         # stores a hash, never the plain password
        db.session.add(user)
        db.session.commit()