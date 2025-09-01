"""Blueprint simple pour pages de documentation utilisateur.

Permet d'ajouter facilement de nouvelles pages sans surcharger main.py.
"""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

docs = Blueprint("docs", __name__, url_prefix="/docs")


@docs.route("/")
@login_required
def index():
    return render_template(
        "docs/index.html", name=current_user.name if current_user.is_authenticated else None
    )


@docs.route("/releases")
@login_required
def releases():
    return render_template(
        "docs/releases.html", name=current_user.name if current_user.is_authenticated else None
    )


@docs.route("/guide", endpoint="guide")
@login_required
def guide_page():
    """Page du guide d'utilisation (vue synthèse historique)."""
    return render_template(
        "docs.html", name=current_user.name if current_user.is_authenticated else None
    )
