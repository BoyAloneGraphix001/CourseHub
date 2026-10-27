from flask import render_template
from flask_wtf.csrf import CSRFError

from app.extensions import db


def register_error_handlers(app):

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template(
            "errors/generic.html", code=413, title="That file is too large",
            message="Uploads can be up to 5 MB. Choose a smaller file and try again."), 413

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render_template(
            "errors/generic.html", code=400, title="Your session expired",
            message="For your security, this form timed out. Go back, refresh the page and try again."), 400

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()                 # leave the database in a clean state
        return render_template("errors/500.html"), 500