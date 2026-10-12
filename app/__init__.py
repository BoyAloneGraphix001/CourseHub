from flask import Flask
from config import Config
from app.extensions import db, migrate,csrf, login_manager, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

    mail.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    

    from app.main.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from app.auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    return app
