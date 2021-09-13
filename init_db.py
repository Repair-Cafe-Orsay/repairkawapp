from repairkawapp import db, create_app
from repairkawapp.models import Category, Brand, User, State, Repair, CloseStatus
from werkzeug.security import generate_password_hash
from datetime import datetime

with create_app().app_context():
    db.create_all()

    db.session.add(User(email="jean@senellart.com",
                        name="Jean S",
                        password=generate_password_hash("password", method='sha256')))
    db.session.add(User(email="agathe@senellart.com",
                        name="Agathe S",
                        password=generate_password_hash("password", method='sha256')))
    db.session.add(User(email="-1",
                        name="Arnaud B",
                        password=generate_password_hash("password", method='sha256')))
    db.session.add(User(email="-2",
                        name="Bertrand R",
                        password=generate_password_hash("password", method='sha256')))

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

    db.session.add(CloseStatus(id=0, label="🛠 En cours..."))
    db.session.add(CloseStatus(id=1, label="😊 Réparé !"))
    db.session.add(CloseStatus(id=2, label="😬 Partiellement/Conseil"))
    db.session.add(CloseStatus(id=3, label="😓 Non..."))

    with open("data/brand.txt") as f:
        for line in f:
            line = line.strip()
            db.session.add(Brand(name=line))

    db.session.add(Repair(
    		id="210911-001",
    		created=datetime(2021, 9, 11, 10, 00),
    		name="Jean Senellart",
		    category_id = 1,
		    brand_id=Brand.query.filter_by(name="PHILIPS")[0].id,
		    initial_state_id=1,
		    current_state_id=1,
		    otype="Perceuse",
		    model="XM-3",
		    description="ne fonctionne pas"))

    db.session.commit()