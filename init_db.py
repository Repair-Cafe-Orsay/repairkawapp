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
    # Icône mise à jour: 'lightning' (anciennement 'plug') pour mieux représenter l'électroménager
    db.session.add(Category(rm_icon_id=1678, icon_name="lightning", name="A - Électroménager"))
    db.session.add(
        Category(rm_icon_id=5343, icon_name="basket", name="B - Article ménager non électrique")
    )
    db.session.add(Category(rm_icon_id=1693, icon_name="puzzle", name="C - Jouet non électrique"))
    db.session.add(Category(rm_icon_id=1692, icon_name="controller", name="D - Jouet électrique"))
    db.session.add(
        Category(rm_icon_id=1689, icon_name="camera-video", name="E - Matériel d'image et de son")
    )
    db.session.add(
        Category(rm_icon_id=1677, icon_name="pc", name="F - Matériel informatique/téléphones")
    )
    db.session.add(Category(rm_icon_id=1691, icon_name="wrench", name="G - Outil non électrique"))
    db.session.add(Category(rm_icon_id=1690, icon_name="tools", name="H - Outil électrique"))
    db.session.add(Category(rm_icon_id=1683, icon_name="collection", name="I - Meuble"))
    db.session.add(Category(rm_icon_id=18707, icon_name="gem", name="J - Bijou"))
    db.session.add(
        Category(rm_icon_id=18706, icon_name="alarm", name="K - Pendule, horloge ou réveil")
    )
    db.session.add(Category(rm_icon_id=1684, icon_name="thread", name="L - Textile"))
    db.session.add(Category(rm_icon_id=1679, icon_name="bicycle", name="M - Vélo"))
    db.session.add(Category(rm_icon_id=1685, icon_name="question-circle", name="N - Autre"))
    db.session.add(Category(rm_icon_id=1685, icon_name="lightbulb", name="O - Éclairage"))
    db.session.add(
        Category(rm_icon_id=1685, icon_name="thermometer-half", name="P - Chauffage/Climatisation")
    )
    db.session.add(
        Category(rm_icon_id=1685, icon_name="shield-lock", name="Q - Sécurité/Domotique")
    )

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

    objects_data = [
        ("A - Électroménager", "Adoucisseur d'eau", [], []),
        ("A - Électroménager", "Appareil à manucure/pédicure", [], []),
        ("A - Électroménager", "Appareil anti-cellulite", [], []),
        ("A - Électroménager", "Appareil croque monsieur", [], []),
        ("A - Électroménager", "Appareil gazeifier", ["Fontaine à eau"], []),
        ("A - Électroménager", "Appareil à raclette", [], []),
        ("A - Électroménager", "Aspirateur", [], []),
        ("A - Électroménager", "Autocuiseur", ["Cuiseur vapeur"], []),
        ("A - Électroménager", "Babycook", ["Cuiseur mixeur bébé"], []),
        ("A - Électroménager", "Bain marie", [], []),
        ("A - Électroménager", "Balance", [], []),
        ("A - Électroménager", "Barbecue", ["Grill Barbecue"], []),
        ("A - Électroménager", "Batteurs électriques", [], []),
        ("A - Électroménager", "Blendeur", [], []),
        ("A - Électroménager", "Bouilloire", [], []),
        ("A - Électroménager", "Brosse à dents électrique", [], []),
        ("A - Électroménager", "Brosse nettoyante", [], []),
        ("A - Électroménager", "Broyeur café", [], []),
        ("A - Électroménager", "Câble d'alimentation", [], []),
        ("A - Électroménager", "Cave à vin", [], []),
        ("A - Électroménager", "Centrale vapeur", [], []),
        ("A - Électroménager", "Centrifugeur", [], []),
        ("A - Électroménager", "Chargeur", [], []),
        ("A - Électroménager", "Chauffe-biberon", [], []),
        ("A - Électroménager", "Chocolatière", [], []),
        ("A - Électroménager", "Cireuse", [], []),
        ("A - Électroménager", "Congélateur", [], []),
        ("A - Électroménager", "Couverture chauffante", [], []),
        ("A - Électroménager", "Crêpière", [], []),
        ("A - Électroménager", "Cuiseur sous-vide", [], []),
        ("A - Électroménager", "Cuiseur à riz", ["Rice cooker"], []),
        ("A - Électroménager", "Cuisinière", [], []),
        ("A - Électroménager", "Défroisseur", [], []),
        ("A - Électroménager", "Déshydrateur alimentaire", [], []),
        ("A - Électroménager", "Déshumidificateur", [], []),
        ("A - Électroménager", "Diffuseur", [], []),
        ("A - Électroménager", "Dynamiseur d'eau", [], []),
        ("A - Électroménager", "Épilateur", [], []),
        ("A - Électroménager", "Épilateur lumière pulsée", [], []),
        ("A - Électroménager", "Extracteur d'air", [], []),
        ("A - Électroménager", "Extracteur de jus", [], []),
        ("A - Électroménager", "Fauteuil massant", [], []),
        ("A - Électroménager", "Fer à lisser", [], []),
        ("A - Électroménager", "Fer à repasser", [], []),
        ("A - Électroménager", "Four", [], []),
        ("A - Électroménager", "Four à micro-ondes", ["Four micro-onde"], []),
        ("A - Électroménager", "Friteuse", [], []),
        ("A - Électroménager", "Frigo", ["Réfrigérateur"], []),
        ("A - Électroménager", "Gaufrier", [], []),
        ("A - Électroménager", "Générateur bulles savon", [], []),
        ("A - Électroménager", "Générateur ozone", [], []),
        ("A - Électroménager", "Grille-pain", [], []),
        ("A - Électroménager", "Hachoir", [], []),
        ("A - Électroménager", "Hotte", [], []),
        ("A - Électroménager", "Humidificateur", [], []),
        ("A - Électroménager", "Hydropulseur dentaire", [], []),
        ("A - Électroménager", "Jet dentaire hydropropulseur", [], []),
        ("A - Électroménager", "Lave-glace", [], []),
        ("A - Électroménager", "Lave-vaisselle", [], []),
        ("A - Électroménager", "Lave-vitre", [], []),
        ("A - Électroménager", "Machine à café", ["Cafetière"], ["Espresso", "Filtre", "Moka"]),
        ("A - Électroménager", "Machine à coudre", [], []),
        ("A - Électroménager", "Machine à glaçons", [], []),
        ("A - Électroménager", "Machine à laver", ["Lave-linge"], []),
        ("A - Électroménager", "Machine à pain", [], []),
        ("A - Électroménager", "Machine à pâtes", [], []),
        ("A - Électroménager", "Machine à pop-corn", [], []),
        ("A - Électroménager", "Masseur", [], []),
        ("A - Électroménager", "Matelas chauffant", [], []),
        ("A - Électroménager", "Mixeur", [], []),
        ("A - Électroménager", "Moulin café", [], []),
        ("A - Électroménager", "Mousseur lait", [], []),
        ("A - Électroménager", "Multicuiseur", [], []),
        ("A - Électroménager", "Nettoyeur vapeur", [], []),
        ("A - Électroménager", "Pierrade", [], []),
        ("A - Électroménager", "Plancha", [], []),
        (
            "A - Électroménager",
            "Plaque de cuisson",
            [],
            ["Induction", "Vitrocéramique", "Électrique", "Gaz"],
        ),
        ("A - Électroménager", "Presse-agrumes", ["Presse Citron"], []),
        ("A - Électroménager", "Purificateur d'air", [], []),
        ("A - Électroménager", "Râpe", [], []),
        ("A - Électroménager", "Rasoir électrique", ["Tondeuse Barbe"], []),
        ("A - Électroménager", "Robot aspirateur", [], []),
        ("A - Électroménager", "Robot batteur", [], []),
        ("A - Électroménager", "Robot cuiseur", [], []),
        ("A - Électroménager", "Robot de cuisine", [], []),
        ("A - Électroménager", "Rôtissoire", [], []),
        ("A - Électroménager", "Sanibroyeur", [], []),
        ("A - Électroménager", "Sauna facial", [], []),
        ("A - Électroménager", "Sèche-cheveux", [], []),
        ("A - Électroménager", "Shampouineuse", [], []),
        ("A - Électroménager", "Sorbetière", [], []),
        ("A - Électroménager", "Stérilisateur biberon", [], []),
        ("A - Électroménager", "Surjetteuse", [], []),
        ("A - Électroménager", "Tajine électrique", [], []),
        ("A - Électroménager", "Tapis chauffant", [], []),
        ("A - Électroménager", "Tire-lait électrique", [], []),
        ("A - Électroménager", "Tireuse bière", [], []),
        ("A - Électroménager", "Tondeuse à barbe", [], []),
        ("A - Électroménager", "Turbine à glace", [], []),
        ("A - Électroménager", "Ventilateur", [], []),
        ("A - Électroménager", "Wok électrique", [], []),
        ("A - Électroménager", "Yaourtière", [], []),
        ("B - Article ménager non électrique", "Casserole", [], []),
        ("B - Article ménager non électrique", "Passoire", [], []),
        ("B - Article ménager non électrique", "Plateau", [], []),
        ("B - Article ménager non électrique", "Vase", [], []),
        ("C - Jouet non électrique", "Jouet", [], []),
        ("D - Jouet électrique", "Console de jeux", [], []),
        ("D - Jouet électrique", "Jouet électrique", [], []),
        ("E - Matériel d'image et de son", "Accordeur électronique", [], []),
        ("E - Matériel d'image et de son", "Ampli tuner", [], []),
        ("E - Matériel d'image et de son", "Amplificateur", [], []),
        ("E - Matériel d'image et de son", "Appareil photo", [], []),
        ("E - Matériel d'image et de son", "Babyphone", [], []),
        ("E - Matériel d'image et de son", "Barre son", [], []),
        ("E - Matériel d'image et de son", "Batterie électronique", [], []),
        ("E - Matériel d'image et de son", "Câble", [], []),
        (
            "E - Matériel d'image et de son",
            "Caméra",
            ["Action cam", "Dashcam", "Caméra de surveillance"],
            ["Digitale", "Analogique"],
        ),
        ("E - Matériel d'image et de son", "Caméscope", [], []),
        ("E - Matériel d'image et de son", "Casque audio", ["Écouteurs"], []),
        ("E - Matériel d'image et de son", "Chaîne hi-fi", [], []),
        ("E - Matériel d'image et de son", "Piano électrique", ["Clavier numérique", "Synthé"], []),
        ("E - Matériel d'image et de son", "Compresseur audio", [], []),
        ("E - Matériel d'image et de son", "Dictaphone", [], []),
        ("E - Matériel d'image et de son", "Drone", [], []),
        ("E - Matériel d'image et de son", "Écran interphone", [], []),
        ("E - Matériel d'image et de son", "Écran photo numérique", [], []),
        ("E - Matériel d'image et de son", "Égaliseur", [], []),
        ("E - Matériel d'image et de son", "Électrophone", [], []),
        ("E - Matériel d'image et de son", "Enceinte", [], []),
        ("E - Matériel d'image et de son", "Flash photo", [], []),
        ("E - Matériel d'image et de son", "Guitare électrique", [], []),
        ("E - Matériel d'image et de son", "Karaoké", [], []),
        ("E - Matériel d'image et de son", "Lecteur livres audios", [], []),
        ("E - Matériel d'image et de son", "Machine fumée", [], []),
        ("E - Matériel d'image et de son", "Magnétophone", [], []),
        ("E - Matériel d'image et de son", "Magnétoscope", [], []),
        ("E - Matériel d'image et de son", "Métronome électronique", [], []),
        ("E - Matériel d'image et de son", "Micro-casque", [], []),
        ("E - Matériel d'image et de son", "Objectif photo", [], []),
        ("E - Matériel d'image et de son", "Oreillette bluetooth", [], []),
        ("E - Matériel d'image et de son", "Pied télévision", [], []),
        ("E - Matériel d'image et de son", "Platine CD", [], []),
        ("E - Matériel d'image et de son", "Platine laser", [], []),
        ("E - Matériel d'image et de son", "Platine vinyle", [], []),
        ("E - Matériel d'image et de son", "Préamplificateur", [], []),
        ("E - Matériel d'image et de son", "Préampli micro", [], []),
        ("E - Matériel d'image et de son", "Radio", ["Transistor"], []),
        ("E - Matériel d'image et de son", "Radio CD", [], []),
        ("E - Matériel d'image et de son", "Radio cassette", [], []),
        ("E - Matériel d'image et de son", "Scanner aviation", [], []),
        ("E - Matériel d'image et de son", "Scanner photo/diapos", [], []),
        ("E - Matériel d'image et de son", "Sonnette", [], []),
        ("E - Matériel d'image et de son", "Stabilisateur", [], []),
        ("E - Matériel d'image et de son", "Système son surround", [], []),
        ("E - Matériel d'image et de son", "Table mixage", [], []),
        ("E - Matériel d'image et de son", "Télécommande", ["HIFI/TV"], []),
        ("E - Matériel d'image et de son", "Téléviseur", [], []),
        ("E - Matériel d'image et de son", "Trépied", [], []),
        ("E - Matériel d'image et de son", "Tuner", [], []),
        ("E - Matériel d'image et de son", "Vidéo-projecteur", [], []),
        ("E - Matériel d'image et de son", "Visionneuse", ["Visionneuse diapo"], []),
        ("E - Matériel d'image et de son", "Visiophone", [], []),
        ("E - Matériel d'image et de son", "Webcam", [], []),
        ("F - Matériel informatique/téléphones", "Alimentation", [], []),
        ("F - Matériel informatique/téléphones", "Baladeur", [], []),
        ("F - Matériel informatique/téléphones", "Broyeur papier", [], []),
        ("F - Matériel informatique/téléphones", "Carte graphique", [], []),
        ("F - Matériel informatique/téléphones", "Carte mère", [], []),
        ("F - Matériel informatique/téléphones", "Carte réseau", [], []),
        ("F - Matériel informatique/téléphones", "Chargeur batterie", [], []),
        ("F - Matériel informatique/téléphones", "Clavier", [], []),
        ("F - Matériel informatique/téléphones", "Clé wifi", [], []),
        ("F - Matériel informatique/téléphones", "Combiné téléphonique", [], []),
        ("F - Matériel informatique/téléphones", "Disque dur", [], []),
        ("F - Matériel informatique/téléphones", "Docking station", [], []),
        ("F - Matériel informatique/téléphones", "Écran d'ordinateur", [], []),
        ("F - Matériel informatique/téléphones", "Haut-parleurs", [], []),
        ("F - Matériel informatique/téléphones", "Hub USB", [], []),
        ("F - Matériel informatique/téléphones", "Imprimante", [], []),
        ("F - Matériel informatique/téléphones", "KVM switch", [], []),
        ("F - Matériel informatique/téléphones", "Liseuse", [], []),
        ("F - Matériel informatique/téléphones", "Manette jeu", ["Joystick"], []),
        ("F - Matériel informatique/téléphones", "Mémoire RAM", [], []),
        ("F - Matériel informatique/téléphones", "Modem", [], []),
        ("F - Matériel informatique/téléphones", "NAS", [], []),
        ("F - Matériel informatique/téléphones", "Navigateur GPS", [], []),
        ("F - Matériel informatique/téléphones", "Onduleur informatique", [], []),
        ("F - Matériel informatique/téléphones", "Ordinateur Portable", [], []),
        ("F - Matériel informatique/téléphones", "Ordinateur tour", [], []),
        ("F - Matériel informatique/téléphones", "Roue crantée", [], []),
        (
            "F - Matériel informatique/téléphones",
            "Routeur",
            ["Box internet", "Répéteur WiFi", "Point d'accès WiFi"],
            [],
        ),
        ("F - Matériel informatique/téléphones", "Souris", [], []),
        ("F - Matériel informatique/téléphones", "Switch", [], []),
        ("F - Matériel informatique/téléphones", "Tablette", [], []),
        (
            "F - Matériel informatique/téléphones",
            "Téléphone",
            ["Smartphone", "téléphone sans fil"],
            [],
        ),
        ("F - Matériel informatique/téléphones", "Trackpad", ["Pavé tactile"], []),
        ("F - Matériel informatique/téléphones", "Transformateur", [], []),
        ("F - Matériel informatique/téléphones", "Ventilateur PC", [], []),
        ("G - Outil non électrique", "Outil manuel", [], []),
        ("H - Outil électrique", "Agrapheuse", [], []),
        ("H - Outil électrique", "Alimentation laboratoire", ["Générateur tension"], []),
        ("H - Outil électrique", "Alternateur", [], []),
        ("H - Outil électrique", "Bétonnière", [], []),
        ("H - Outil électrique", "Broyeur Bois", [], []),
        ("H - Outil électrique", "Broyeur déchets", [], []),
        ("H - Outil électrique", "Compresseur", [], []),
        ("H - Outil électrique", "Coupe-bordure", [], []),
        ("H - Outil électrique", "Débroussailleur", [], []),
        ("H - Outil électrique", "Décapeur thermique", [], []),
        ("H - Outil électrique", "Découpoir plasma", [], []),
        ("H - Outil électrique", "Défonceuse", [], []),
        ("H - Outil électrique", "Dégrippant ultrason", [], []),
        ("H - Outil électrique", "Disqueuse", [], []),
        ("H - Outil électrique", "Fendeuse bûches", [], []),
        ("H - Outil électrique", "Fer à souder", [], []),
        ("H - Outil électrique", "Générateur fumée", [], []),
        ("H - Outil électrique", "Graveur", [], []),
        ("H - Outil électrique", "Groupe électrogène", [], []),
        ("H - Outil électrique", "Meuleuse", [], []),
        ("H - Outil électrique", "Multimètre", [], []),
        ("H - Outil électrique", "Nettoyeur haute pression", [], []),
        ("H - Outil électrique", "Onduleur", [], []),
        ("H - Outil électrique", "Oscilloscope", [], []),
        ("H - Outil électrique", "Perceuse", [], []),
        ("H - Outil électrique", "Pince ampèremétrique", [], []),
        ("H - Outil électrique", "Pistolet à peinture", [], []),
        ("H - Outil électrique", "Pistolet colle", [], []),
        ("H - Outil électrique", "Plastifieuse", [], []),
        (
            "H - Outil électrique",
            "Ponceuse",
            [],
            ["Ponceuse à bande", "ponceuse circulaire", "autre"],
        ),
        ("H - Outil électrique", "Rabot", [], []),
        (
            "H - Outil électrique",
            "Scie",
            [],
            ["Scie à onglet", "Scie circulaire", "Scie sabre", "Scie sauteuse", "autre"],
        ),
        ("H - Outil électrique", "Sécateur", [], []),
        ("H - Outil électrique", "Station de soudage", [], []),
        ("H - Outil électrique", "Surpresseur", [], []),
        ("H - Outil électrique", "Taille-bordure", [], []),
        ("H - Outil électrique", "Taille-haie", [], []),
        ("H - Outil électrique", "Testeur électrique", [], []),
        ("H - Outil électrique", "Thermomètre", [], []),
        ("H - Outil électrique", "Tondeuse", [], []),
        ("H - Outil électrique", "Tronçonneuse", [], []),
        ("H - Outil électrique", "Visseuse", [], []),
        ("I - Meuble", "Meuble", [], []),
        ("J - Bijou", "Bijou", [], []),
        ("K - Pendule, horloge ou réveil", "Horloge", [], []),
        ("K - Pendule, horloge ou réveil", "Montre", [], []),
        ("K - Pendule, horloge ou réveil", "Réveil", [], []),
        ("L - Textile", "Barrette cheveux", [], []),
        ("L - Textile", "Chaussure", [], []),
        ("L - Textile", "Chemise", [], []),
        ("L - Textile", "Pantalon", [], []),
        ("L - Textile", "Tour cou", [], []),
        ("L - Textile", "Veste", [], []),
        ("M - Vélo", "Vélo", [], ["électrique", "manuel"]),
        ("M - Vélo", "Vélo d'appartement", [], []),
        ("N - Autre", "Appareil massage jambes", [], []),
        ("N - Autre", "Diffuseur", [], []),
        ("N - Autre", "Moteur", [], []),
        ("N - Autre", "Multiprise", [], []),
        ("N - Autre", "Parapluie", [], []),
        ("N - Autre", "Pompe", [], []),
        ("N - Autre", "Poussette", [], []),
        ("N - Autre", "Presse badges", [], []),
        ("N - Autre", "Rétroviseur", [], []),
        ("N - Autre", "Tapis marche", [], []),
        ("N - Autre", "Télécommande", [], ["Portail", "Volet Roulant", "Autre"]),
        ("N - Autre", "Trottinette", [], []),
        ("N - Autre", "Valise", [], []),
        ("N - Autre", "Vitrail", [], []),
        ("O - Éclairage", "Ampoule", [], []),
        ("O - Éclairage", "Applique", [], []),
        ("O - Éclairage", "Éclairage jardin", [], []),
        ("O - Éclairage", "Éclairage piscine", [], []),
        ("O - Éclairage", "Guirlande", [], []),
        ("O - Éclairage", "Interrupteur", [], []),
        ("O - Éclairage", "Lampadaire", ["Lampe", "Luminaire"], []),
        ("O - Éclairage", "Plafonnier", [], []),
        ("O - Éclairage", "Projecteur LED", [], []),
        ("O - Éclairage", "Ruban LED", [], []),
        ("O - Éclairage", "Spot", [], []),
        ("O - Éclairage", "Suspension", [], []),
        ("P - Chauffage/Climatisation", "Chaudière électrique", [], []),
        ("P - Chauffage/Climatisation", "Chauffage d'appoint", [], []),
        ("P - Chauffage/Climatisation", "Chauffage soufflant", [], []),
        ("P - Chauffage/Climatisation", "Climatisation mobile", [], []),
        ("P - Chauffage/Climatisation", "Climatiseur", [], []),
        ("P - Chauffage/Climatisation", "Convecteur", [], []),
        ("P - Chauffage/Climatisation", "Pompe à chaleur", [], []),
        ("P - Chauffage/Climatisation", "Programmateur chauffage", [], []),
        ("P - Chauffage/Climatisation", "Radiateur", [], []),
        ("P - Chauffage/Climatisation", "Radiateur à inertie", [], []),
        ("P - Chauffage/Climatisation", "Sèche-linge", [], []),
        ("P - Chauffage/Climatisation", "Sèche-serviette", [], []),
        ("P - Chauffage/Climatisation", "Thermostat extérieur", [], []),
        ("P - Chauffage/Climatisation", "VMC", ["Ventilation"], []),
        ("Q - Sécurité/Domotique", "Alarme", [], []),
        ("Q - Sécurité/Domotique", "Caméra IP", [], []),
        ("Q - Sécurité/Domotique", "Central domotique", [], []),
        ("Q - Sécurité/Domotique", "Détecteur fumée", [], []),
        ("Q - Sécurité/Domotique", "Détecteur gaz", [], []),
        ("Q - Sécurité/Domotique", "Détecteur mouvement", [], []),
        ("Q - Sécurité/Domotique", "Interphone", [], []),
        ("Q - Sécurité/Domotique", "Interrupteur connecté", [], []),
        ("Q - Sécurité/Domotique", "Portier vidéo", [], []),
        ("Q - Sécurité/Domotique", "Prise connectée", [], []),
        ("Q - Sécurité/Domotique", "Serrure connectée", [], []),
    ]

    db.session.commit()
