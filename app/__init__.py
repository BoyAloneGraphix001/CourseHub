import re
from flask import Flask
from config import Config
from app.extensions import db, migrate,csrf, login_manager, mail
from datetime import datetime, timezone


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

    mail.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    

    from app.main.routes import main
    app.register_blueprint(main)
    from app.auth.routes import auth
    app.register_blueprint(auth)
    from app.admin.routes import admin
    app.register_blueprint(admin, url_prefix="/admin")
    from app.student.routes import student
    app.register_blueprint(student, url_prefix="/student")
    from app.instructor.routes import instructor
    app.register_blueprint(instructor, url_prefix="/instructor")
    from app.handlers import register_error_handlers
    register_error_handlers(app)
    from app.commands import register_commands
    register_commands(app)  


    @app.template_filter("initials")
    def initials(value):
        words = [w for w in re.split(r"[\s._-]+", value or "") if w]
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return (words[0][:2] if words else "?").upper()

    @app.context_processor
    def inject_year():
        return {"current_year": datetime.now(timezone.utc).year}
    
    return app
