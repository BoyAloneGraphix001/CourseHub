import click
from sqlalchemy import func

from app.extensions import db
from app.models import User


def register_commands(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username, email, password):
        username = username.strip()
        email = email.lower().strip()
        if User.query.filter(func.lower(User.email) == email).first():
            raise click.ClickException("A user with that email already exists.")
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            raise click.ClickException("A user with that username already exists.")

        user = User(username=username, email=email, is_admin=True, is_instructor=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin account for {email}")