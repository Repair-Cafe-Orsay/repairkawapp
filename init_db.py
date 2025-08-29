from werkzeug.security import generate_password_hash

from repairkawapp import create_app, db
from repairkawapp.models import Brand, Category, CloseStatus, SpareStatus, State, User

# Initial initialization of mysql database, for database model upgrade - see alembic

with create_app().app_context():
    db.create_all()

    with open("data/users.txt") as f:
        for line in f:
            if not line.startswith("#"):
                (email, name) = line.strip().split("\t")
                db.session.add(
                    User(
                        email=email,
                        name=name,
                        password=generate_password_hash("password-rco", method="pbkdf2:sha256"),
                    )
                )

    # Icons and Category ID are matching Repair Monitor for simpler upload
    db.session.add(Category(rm_icon_id=1678, name="A - Électroménager"))
    db.session.add(Category(rm_icon_id=5343, name="B - Article ménager non électrique"))
    db.session.add(Category(rm_icon_id=1693, name="C - Jouet non électrique"))
    db.session.add(Category(rm_icon_id=1692, name="D - Jouet électrique"))
    db.session.add(Category(rm_icon_id=1689, name="E - Matériel d'image et de son"))
    db.session.add(Category(rm_icon_id=1677, name="F - Matériel informatique/téléphones"))
    db.session.add(Category(rm_icon_id=1691, name="G - Outil non électrique"))
    db.session.add(Category(rm_icon_id=1690, name="H - Outil électrique"))
    db.session.add(Category(rm_icon_id=1683, name="I - Meuble"))
    db.session.add(Category(rm_icon_id=18707, name="J - Bijou"))
    db.session.add(Category(rm_icon_id=18706, name="K - Pendule, horloge ou réveil"))
    db.session.add(Category(rm_icon_id=1684, name="L - Textile"))
    db.session.add(Category(rm_icon_id=1679, name="M - Vélo"))
    db.session.add(Category(rm_icon_id=1685, name="N - Autre"))

    db.session.add(State(id=1, label="Ne fonctionne pas du tout"))
    db.session.add(State(id=2, label="Fonctionnalités réduites"))
    db.session.add(State(id=3, label="Fonctionne avec difficulté et/ou problème sécurité"))
    db.session.add(State(id=4, label="Fonctionne bien mais problème aspect majeur"))
    db.session.add(State(id=5, label="Fonctionne bien sans problème aspect majeur"))

    db.session.add(CloseStatus(id=1, label="🛠 En cours..."))
    db.session.add(CloseStatus(id=2, label="😊 Réparé !"))
    db.session.add(CloseStatus(id=3, label="😬 Partiellement/Conseil"))
    db.session.add(CloseStatus(id=4, label="😓 Non..."))

    db.session.add(SpareStatus(id=1, label="📌 Identifié"))
    db.session.add(SpareStatus(id=2, label="🔍 En recherche"))
    db.session.add(SpareStatus(id=3, label="⏳ En attente"))
    db.session.add(SpareStatus(id=4, label="🛠 À remplacer"))
    db.session.add(SpareStatus(id=5, label="👌 Remplacé"))

    with open("data/brand.txt") as f:
        for line in f:
            line = line.strip()
            db.session.add(Brand(name=line))

    db.session.commit()
