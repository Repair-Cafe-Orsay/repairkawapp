from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_thumbnails import Thumbnail
import os

db = SQLAlchemy()
thumb = None

def create_app():
# init SQLAlchemy so we can use it later in our models
    app = Flask(__name__)

    global thumb

    app.config['SECRET_KEY'] = 'secret-key-goes-here'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    app.config['PAGE_SIZE'] = 10
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = ['jpg', 'jpeg', 'png']
    app.config['UPLOAD_FOLDER'] = os.getcwd()+'/uploads'
    app.config['THUMBNAIL_MEDIA_ROOT'] = os.getcwd()+'/uploads'
    app.config['THUMBNAIL_MEDIA_THUMBNAIL_ROOT'] = os.getcwd()+'/uploads/cache'
    app.config['THUMBNAIL_MEDIA_URL'] = '/media/'
    app.config['THUMBNAIL_MEDIA_THUMBNAIL_URL'] = '/media/cache/'

    thumb = Thumbnail(app)
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