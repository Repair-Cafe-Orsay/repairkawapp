"""Migration ad hoc: ajoute des noms d'icônes libres aux catégories existantes.

Exécution: `python scripts/migrate_icons.py`
Pré-requis: variable d'environnement FLASK_APP correctement définie si nécessaire.
"""

from repairkawapp import create_app, db
from repairkawapp.models import Category

# Mapping provisoire vers Bootstrap Icons (https://icons.getbootstrap.com/)
ICON_MAP = {
    # A - Électroménager
    "A - Électroménager": "lightning",
    # B - Article ménager non électrique
    "B - Article ménager non électrique": "basket",
    # C - Jouet non électrique
    "C - Jouet non électrique": "puzzle",
    # D - Jouet électrique
    "D - Jouet électrique": "controller",
    # E - Matériel d'image et de son
    "E - Matériel d'image et de son": "camera-video",
    # F - Matériel informatique/téléphones
    "F - Matériel informatique/téléphones": "pc",
    # G - Outil non électrique
    "G - Outil non électrique": "wrench",
    # H - Outil électrique
    "H - Outil électrique": "tools",
    # I - Meuble
    "I - Meuble": "collection",
    # J - Bijou
    "J - Bijou": "gem",
    # K - Pendule, horloge ou réveil
    "K - Pendule, horloge ou réveil": "alarm",
    # L - Textile
    "L - Textile": "thread",
    # M - Vélo
    "M - Vélo": "bicycle",
    # N - Autre
    "N - Autre": "question-circle",
    # O - Éclairage
    "O - Éclairage": "lightbulb",
    # P - Chauffage/Climatisation
    "P - Chauffage/Climatisation": "thermometer-half",
    # Q - Sécurité/Domotique
    "Q - Sécurité/Domotique": "shield-lock",
}

app = create_app()
with app.app_context():
    changed = 0
    for c in Category.query.all():
        if not c.icon_name and c.name in ICON_MAP:
            c.icon_name = ICON_MAP[c.name]
            changed += 1
    if changed:
        db.session.commit()
        print(f"Icon names définis pour {changed} catégories.")
    else:
        print("Aucun changement (déjà migré ?)")
