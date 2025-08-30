"""Script de peuplement des tables ObjectType / ObjectVariant / ObjectSubtype.

Exécution (base configurée dans config.json) :

        python define_objecttype.py                # insertion idempotente
        python define_objecttype.py --dry-run       # simulation
        python define_objecttype.py --verbose       # détails

Le script :
    * migrations appliquées requises (object_type / object_variant / object_subtype).
    * ne recrée pas les catégories : il les recherche par leur nom exact.
    * crée les ObjectType manquants et ajoute variantes / sous-types non présents.
    * est idempotent : relancer n'ajoute pas de doublon.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable

from repairkawapp import create_app, db
from repairkawapp.models import (
    Category,
    ObjectSubtype,
    ObjectType,
    ObjectVariant,
)

# Données (catégorie, type, [variants], [sous-types])
OBJECTS_DATA: list[tuple[str, str, list[str], list[str]]] = [
    ("A - Électroménager", "Adoucisseur d'eau", [], []),
    ("A - Électroménager", "Appareil à manucure/pédicure", [], []),
    ("A - Électroménager", "Appareil anti-cellulite", [], []),
    ("A - Électroménager", "Appareil croque monsieur", [], []),
    ("A - Électroménager", "Appareil à gazeifier", ["Fontaine à eau"], []),
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
    ("F - Matériel informatique/téléphones", "Téléphone", ["Smartphone", "téléphone sans fil"], []),
    ("F - Matériel informatique/téléphones", "Trackpad", ["Pavé tactile"], []),
    ("F - Matériel informatique/téléphones", "Transformateur", [], []),
    ("F - Matériel informatique/téléphones", "Ventilateur PC", [], []),
    ("G - Outil non électrique", "Outil manuel", [], []),
    ("H - Outil électrique", "Agrapheuse", [], []),
    ("H - Outil électrique", "Alimentation laboratoire", ["Générateur tension"], []),
    ("H - Outil électrique", "Alternateur", [], []),
    ("H - Outil électrique", "Bétonnière", [], []),
    ("H - Outil électrique", "Broyeur déchets", [], []),
    ("H - Outil électrique", "Compresseur", [], []),
    ("H - Outil électrique", "Coupe-bordure", [], []),
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
    ("H - Outil électrique", "Ponceuse", [], ["Ponceuse à bande", "ponceuse circulaire", "autre"]),
    ("H - Outil électrique", "Rabot", [], []),
    ("H - Outil électrique", "Scie à onglet", [], []),
    ("H - Outil électrique", "Scie circulaire", [], []),
    ("H - Outil électrique", "Scie radiale", [], []),
    ("H - Outil électrique", "Scie sabre", [], []),
    ("H - Outil électrique", "Scie sauteuse", [], []),
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
    ("L - Textile", "Tour cou", [], []),
    ("M - Vélo", "Vélo", [], ["électrique", "manuel"]),
    ("M - Vélo", "Vélo d'appartement", [], []),
    ("N - Autre", "Ampoule", [], []),
    ("N - Autre", "Appareil massage jambes", [], []),
    ("N - Autre", "Broyeur Bois", [], []),
    ("N - Autre", "Débroussailleur", [], []),
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


def _chunk(it: Iterable, size: int):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def populate_database(dry_run: bool = False, verbose: bool = False) -> dict:
    """Peuple les tables de référence.

    Retourne un dict récapitulatif.
    """

    created_types = 0
    created_variants = 0
    created_subtypes = 0
    skipped_missing_category = 0

    # Précharger catégories par nom (case sensitive sur le nom exact utilisé partout)
    categories_by_name = {c.name: c for c in Category.query.all()}

    for cat_name, type_name, variants, subtypes in OBJECTS_DATA:
        category = categories_by_name.get(cat_name)
        if not category:
            skipped_missing_category += 1
            if verbose:
                print(f"[WARN] Catégorie introuvable '{cat_name}' – entrée ignorée.")
            continue

        # Chercher type existant (unicité par (category_id, name))
        object_type = ObjectType.query.filter_by(
            category_id=category.id, name=type_name
        ).one_or_none()
        if not object_type:
            object_type = ObjectType(name=type_name, category=category)
            db.session.add(object_type)
            created_types += 1
            if verbose:
                print(f"[TYPE] + {cat_name} :: {type_name}")
            if not dry_run:
                db.session.flush()  # ID pour FKs suivantes
        else:
            if verbose:
                print(f"[TYPE] = {cat_name} :: {type_name} (existant)")

        # Variants (unique par (object_type_id, name))
        existing_variant_names = {v.name for v in object_type.variants}
        for variant_name in variants:
            if variant_name in existing_variant_names:
                if verbose:
                    print(f"  [VAR] = {variant_name}")
                continue
            if verbose:
                print(f"  [VAR] + {variant_name}")
            if not dry_run:
                db.session.add(ObjectVariant(name=variant_name, object_type=object_type))
            created_variants += 1

        # Subtypes (unique par (object_type_id, name))
        existing_subtype_names = {s.name for s in object_type.subtypes}
        for subtype_name in subtypes:
            if subtype_name in existing_subtype_names:
                if verbose:
                    print(f"  [SUB] = {subtype_name}")
                continue
            if verbose:
                print(f"  [SUB] + {subtype_name}")
            if not dry_run:
                db.session.add(ObjectSubtype(name=subtype_name, object_type=object_type))
            created_subtypes += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "created_types": created_types,
        "created_variants": created_variants,
        "created_subtypes": created_subtypes,
        "skipped_missing_category": skipped_missing_category,
        "dry_run": dry_run,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Peupler les ObjectType / Variant / Subtype")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans commit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Affiche chaque opération")
    args = parser.parse_args(argv)

    app = create_app()
    with app.app_context():
        # Sanity check: tables existent ? (Alembic migration appliquée)
        inspector = db.inspect(db.engine)
        required_tables = {"object_type", "object_variant", "object_subtype"}
        missing = required_tables - set(inspector.get_table_names())
        if missing:
            print(
                "[ERREUR] Tables manquantes: {}. Migration requise.".format(
                    ", ".join(sorted(missing))
                )
            )
            return 2

        summary = populate_database(dry_run=args.dry_run, verbose=args.verbose)
        print(
            (
                "Résumé: {created_types} types, {created_variants} variantes, "
                "{created_subtypes} sous-types (catégories manquantes: "
                "{skipped_missing_category}) dry_run={dry_run}"
            ).format(**summary)
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
