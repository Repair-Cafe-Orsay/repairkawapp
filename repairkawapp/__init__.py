from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_thumbnails import Thumbnail
from flask_mail import Mail
from itsdangerous import URLSafeSerializer
import os
import json

db = SQLAlchemy()
thumb = None
mail = None
serializer = None

def create_app():
# init SQLAlchemy so we can use it later in our models
    app = Flask(__name__)

    with open("config.json") as json_file:
        config_json = json.load(json_file)
        for k, v in config_json.items():
            app.config[k] = v

    global serializer
    serializer = URLSafeSerializer(app.config['URL_SERIALIZER_SECRET'], salt="chpassword")

    global thumb
    thumb = Thumbnail(app)


    global mail
    mail = Mail(app) 

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprints
    from .auth import auth as auth_blueprint
    from .api import api as api_blueprint
    from .main import main as main_blueprint
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint)

    return app