from repairkawapp import db, create_app
from repairkawapp.models import Category, Brand, User, State, Repair, CloseStatus, SpareStatus
from werkzeug.security import generate_password_hash
from datetime import datetime

with create_app().app_context():
    db.create_all()

    with open("data/users.txt") as f:
        for line in f:
            (email, name) = line.strip().split("\t")
            db.session.add(User(email=email,
                                name=name,
                                password=generate_password_hash("password-rco", method='sha256')))

    db.session.add(Category(rm_icon_id=1678, name="Électroménager"))
    db.session.add(Category(rm_icon_id=5343, name="Article ménager non électrique"))
    db.session.add(Category(rm_icon_id=1693, name="Jouet non électrique"))
    db.session.add(Category(rm_icon_id=1692, name="Jouet électrique"))
    db.session.add(Category(rm_icon_id=1689, name="Matériel d'image et de son"))
    db.session.add(Category(rm_icon_id=1677, name="Matériel informatique/téléphones"))
    db.session.add(Category(rm_icon_id=1691, name="Outil non électrique"))
    db.session.add(Category(rm_icon_id=1690, name="Outil électrique"))
    db.session.add(Category(rm_icon_id=1683, name="Meuble"))
    db.session.add(Category(rm_icon_id=18707, name="Bijou"))
    db.session.add(Category(rm_icon_id=18706, name="Pendule, horloge ou réveil"))
    db.session.add(Category(rm_icon_id=1684, name="Textile"))
    db.session.add(Category(rm_icon_id=1679, name="Vélo"))
    db.session.add(Category(rm_icon_id=1685, name="Autre"))

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