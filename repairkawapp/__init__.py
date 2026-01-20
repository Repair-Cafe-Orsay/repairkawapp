import json
import os

from flask import Flask, redirect, request
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_thumbnails import Thumbnail
from itsdangerous import URLSafeSerializer

db = SQLAlchemy()

# thumbnail engine used for all uploaded images
thumb = None
# mail server
mail = None
# url serializer
serializer = None


def create_app(config_override=None):
    app = Flask(__name__)

    # Version applicative (fichier VERSION à la racine ou valeur par défaut)
    try:
        version_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "VERSION"))
        if os.path.exists(version_path):
            with open(version_path) as vf:
                app.config["APP_VERSION"] = vf.read().strip()
        else:
            app.config["APP_VERSION"] = "0.1.0-dev"
    except Exception:  # pragma: no cover
        app.config["APP_VERSION"] = "0.1.0-dev"

    # Chargement config: si config.json absent, créer depuis le template en remplaçant PATHTO
    cfg_path = "config.json"
    if not os.path.exists(cfg_path):
        template_path = "config-template.json"
        if os.path.exists(template_path):
            repo_root = os.path.abspath(os.path.dirname(__file__) + "/..")
            with open(template_path) as f:
                raw = f.read().replace("PATHTO", repo_root)
            with open(cfg_path, "w") as out:
                out.write(raw)
        else:
            raise RuntimeError(
                "Configuration manquante: ni config.json ni config-template.json trouvés."
            )
    with open(cfg_path) as json_file:
        config_json = json.load(json_file)
        for k, v in config_json.items():
            app.config[k] = v
    # allow tests to override configuration
    if config_override:
        app.config.update(config_override)

    # utilities
    global serializer
    serializer = URLSafeSerializer(app.config["URL_SERIALIZER_SECRET"], salt="chpassword")

    global thumb
    thumb = Thumbnail(app)

    global mail
    mail = Mail(app)

    # initialization of database
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    from .models import RepairCafe, User

    # Import léger pour éviter boucle (AppSetting peut ne pas exister avant migration)
    try:
        from .models import AppSetting  # type: ignore
    except Exception:  # table ou modèle absent
        AppSetting = None  # type: ignore

    @login_manager.user_loader
    def load_user(user_id):
        """Charge le réparateur par son identifiant primaire."""
        return User.query.get(int(user_id))

    class RepairCafePrefixMiddleware:
        """WSGI middleware to support /<code>/ prefix for RepairCafe pages."""

        def __init__(self, wsgi_app):
            self.wsgi_app = wsgi_app

        def __call__(self, environ, start_response):
            path = environ.get("PATH_INFO", "") or ""
            parts = path.split("/")
            if len(parts) > 2 and parts[1]:
                code = parts[1]
                try:
                    with app.app_context():
                        cafe = RepairCafe.query.filter_by(code=code).first()
                    if cafe:
                        environ["SCRIPT_NAME"] = f"/{code}"
                        environ["PATH_INFO"] = "/" + "/".join(parts[2:])
                        environ["REPAIRCAFE_CODE"] = code
                except Exception:
                    pass
            return self.wsgi_app(environ, start_response)

    app.wsgi_app = RepairCafePrefixMiddleware(app.wsgi_app)

    # blueprints
    from .admin import admin as admin_blueprint
    from .api import api as api_blueprint
    from .auth import auth as auth_blueprint
    from .docs_blueprint import docs as docs_blueprint
    from .main import main as main_blueprint

    # Filtres Jinja
    @app.template_filter("local_dt")
    def local_dt(value, fmt="%d/%m/%Y %H:%M"):
        """Formate un datetime (stocké en UTC naïf) en heure locale Europe/Paris.

        Les datetimes stockés sont considérés comme UTC (naïfs)."""
        if not value:
            return ""
        try:
            import pytz

            tz = pytz.timezone("Europe/Paris")
            if value.tzinfo is None:
                value = pytz.utc.localize(value)
            return value.astimezone(tz).strftime(fmt)
        except Exception:
            return str(value)

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint)
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(docs_blueprint)

    @app.before_request
    def enforce_repaircafe_prefix():
        """Redirect to prefixed URLs for authenticated users."""
        if app.config.get("TESTING"):
            return None
        if request.path.startswith("/static"):
            return None
        if request.path.startswith("/login") or request.path.startswith("/logout"):
            return None
        if request.path.startswith("/forgot_password") or request.path.startswith(
            "/change_password"
        ):
            return None
        if request.path.startswith("/init_password"):
            return None
        if request.path.startswith("/admin/repaircafes"):
            return None
        try:
            from flask_login import current_user as cu

            if not cu.is_authenticated:
                return None
            if getattr(cu, "super_admin", False):
                return None
            from .services.tenant_service import get_active_repaircafe

            active_cafe = get_active_repaircafe(cu)
            if not active_cafe or not active_cafe.code:
                return None
            if request.environ.get("SCRIPT_NAME") == f"/{active_cafe.code}":
                return None
            target = f"/{active_cafe.code}{request.path}"
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return redirect(target)
            return redirect(target, code=308)
        except Exception:
            return None

    # Contexte global: statut cotisation (pour bannière dans layout)
    @app.context_processor
    def inject_membership_status():
        from datetime import date as _date

        def _current_academic_start(today: _date) -> int:
            return today.year if today.month >= 9 else today.year - 1

        if hasattr(app, "login_manager"):
            try:
                from flask_login import current_user as cu

                if cu.is_authenticated:
                    today = _date.today()
                    from .services.tenant_service import (
                        get_active_repaircafe,
                        get_allowed_memberships,
                        get_user_cafe_membership,
                    )

                    cafe = get_active_repaircafe(cu)
                    if not cafe:
                        return {"membership_up_to_date": True}
                    last = get_user_cafe_membership(cu.id, cafe.id)
                    ok = last in get_allowed_memberships(today)
                    return {"membership_up_to_date": ok}
            except Exception:
                pass
        return {"membership_up_to_date": True}

    # Contexte maintenance (affiché sur page login uniquement)
    @app.context_processor
    def inject_maintenance_flag():
        maintenance = False
        maintenance_until = None
        if AppSetting is None:
            return {"MAINTENANCE_MODE": False}
        try:
            from sqlalchemy import text as _text

            # Requête directe pour éviter cache de session si migration pas encore appliquée
            with app.app_context():
                conn = db.session.connection()
                # Vérifie présence table rapidement
                res = conn.execute(_text("SHOW TABLES LIKE 'app_setting'"))
                if res.fetchone():
                    row = conn.execute(
                        _text(
                            "SELECT maintenance_mode, maintenance_until FROM app_setting WHERE id=1"
                        )
                    )
                    r = row.fetchone()
                    if r:
                        maintenance = bool(r[0])
                        maintenance_until = r[1]
        except Exception:
            maintenance = False
        return {"MAINTENANCE_MODE": maintenance, "MAINTENANCE_UNTIL": maintenance_until}

    # Contexte global icône catégorie
    @app.context_processor
    def inject_icon_helper():
        try:
            from flask_login import current_user

            from .icon_utils import render_category_icon
            from .services.tenant_service import get_active_repaircafe, is_cafe_admin

            active_cafe = get_active_repaircafe()
            cafe_admin = False
            try:
                if active_cafe and hasattr(current_user, "is_authenticated"):
                    cafe_admin = bool(is_cafe_admin(current_user, active_cafe.id))
            except Exception:
                cafe_admin = False
            return {
                "render_category_icon": render_category_icon,
                "APP_VERSION": app.config.get("APP_VERSION"),
                "active_repaircafe": active_cafe,
                "repaircafe_code": active_cafe.code if active_cafe else None,
                "is_cafe_admin": cafe_admin,
            }
        except Exception:
            return {"APP_VERSION": app.config.get("APP_VERSION")}

    # Version accessible partout (fallback si autre context processors sautent)
    @app.context_processor
    def inject_version():  # pragma: no cover - simple mapping
        return {"APP_VERSION": app.config.get("APP_VERSION")}

    return app
