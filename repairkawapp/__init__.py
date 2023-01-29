from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_thumbnails import Thumbnail
from flask_mail import Mail
from itsdangerous import URLSafeSerializer
import json

db = SQLAlchemy()

# thumbnail engine used for all uploaded images
thumb = None
# mail server
mail = None
# url serializer
serializer = None

def create_app():
    app = Flask(__name__)

    # read the main configuration file to configure the flask application
    with open("config.json") as json_file:
        config_json = json.load(json_file)
        for k, v in config_json.items():
            app.config[k] = v

    # utilities
    global serializer
    serializer = URLSafeSerializer(app.config['URL_SERIALIZER_SECRET'], salt="chpassword")

    global thumb
    thumb = Thumbnail(app)

    global mail
    mail = Mail(app) 

    # initialization of database
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
    from .admin import admin as admin_blueprint
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(admin_blueprint)

    return app