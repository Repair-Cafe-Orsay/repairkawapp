#!/usr/bin/env python3
"""Applique un mapping (ID -> Nouveau type / Nouvelle catégorie) à partir de
data/migration.txt.

Usage:
    python scripts/apply_migration_mapping.py --dry   (par défaut)
    python scripts/apply_migration_mapping.py --apply

Le fichier data/migration.txt doit contenir 3 colonnes tab (ID, New Type, New
Category) avec une ligne d'en-tête. Actions réalisées pour chaque ligne:
    - Recherche de la fiche Repair via display_id (colonne ID du fichier)
    - Création ou récupération d'un ObjectType (New Type) dans la Category ciblée
        (New Category)
    - Mise à jour repair.object_type_id et repair.category_id
    - Effacement du champ textuel legacy otype (mise à "")

En mode --dry aucune modification n'est commit ; un résumé est affiché.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata

from repairkawapp import create_app, db
from repairkawapp.models import Category, Log, ObjectType, Repair, User

CATEGORY_PREFIX_RE = re.compile(r"^[A-Z] - ")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--apply",
        action="store_true",
        help=("Effectuer réellement les modifications " "(sinon dry run)"),
    )
    p.add_argument(
        "--dry",
        action="store_true",
        help="Alias explicite du mode dry run (par défaut)",
    )
    p.add_argument(
        "--file",
        default="data/migration.txt",
        help=("Chemin du fichier mapping (défaut: data/migration.txt)"),
    )
    return p.parse_args()


def load_mapping(path: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = True
        for parts in reader:
            if header:
                header = False
                continue
            if not parts or len(parts) < 3:
                continue
            rid, ntype, ncat = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if not rid:
                continue
            rows.append((rid, ntype, ncat))
    return rows


def get_category(label: str, cache: dict[str, Category]) -> Category | None:
    cat = cache.get(label)
    if cat is not None:
        return cat
    cat = Category.query.filter_by(name=label).first()
    if cat:
        cache[label] = cat
    return cat


def get_object_type(
    name: str,
    category: Category,
    cache: dict[tuple[str, int], ObjectType],
) -> ObjectType | None:
    key = (name, category.id or 0)
    ot = cache.get(key)
    if ot is not None:
        return ot
    if category.id:
        ot = ObjectType.query.filter_by(name=name, category_id=category.id).first()
        if ot:
            cache[key] = ot
            return ot
    return None


def main():
    args = parse_args()
    app = create_app()
    with app.app_context():
        mapping = load_mapping(args.file)
        total = len(mapping)
        updated = 0
        # Compteurs
        equal_type_count = 0  # otype legacy == nouveau type (après normalisation étendue)
        category_changed_count = 0
        type_changed_count = 0
        missing_repairs: list[str] = []
        missing_categories: list[tuple[str, str]] = []  # (display_id, category_label)
        missing_types: list[tuple[str, str, str]] = []  # (display_id, type_name, category_label)
        cat_cache: dict[str, Category] = {}
        ot_cache: dict[tuple[str, int], ObjectType] = {}

        # ID utilisateur pour journalisation (Jean Senellart)
        # Recherche directe par email exact fourni
        owner_user = User.query.filter_by(email="jean@repaircafe-orsay.org").first()
        if not owner_user:
            # Fallback éventuel : ancienne heuristique floue si l'email n'existe pas encore
            owner_user = (
                db.session.query(User)
                .filter(User.email.ilike("%jean%"))
                .order_by(User.id.asc())
                .first()
            )
        owner_user_id = owner_user.id if owner_user else 1  # fallback 1

        for display_id, new_type_name, new_cat_label in mapping:
            r: Repair | None = Repair.query.filter_by(display_id=display_id).first()
            if not r:
                missing_repairs.append(display_id)
                continue
            cat = get_category(new_cat_label, cat_cache)
            if cat is None:
                missing_categories.append((display_id, new_cat_label))
                continue
            ot = get_object_type(new_type_name, cat, ot_cache)
            if ot is None:
                missing_types.append((display_id, new_type_name, new_cat_label))
                continue
            old_otype = (r.otype or "").strip()

            def _strip_accents(txt: str) -> str:
                nkfd = unicodedata.normalize("NFD", txt or "")
                return "".join(c for c in nkfd if unicodedata.category(c) != "Mn")

            def _norm(s: str) -> str:
                s2 = _strip_accents(s or "").lower()
                s2 = re.sub(r"[\s\-]+", "", s2)
                return s2

            norm_old = _norm(old_otype)
            norm_new = _norm(new_type_name)
            type_changed = bool(old_otype) and norm_old != norm_new
            if not type_changed:
                equal_type_count += 1
            category_changed = r.category_id != cat.id

            old_category_name = r.category.name if r.category else None
            # Appliquer structuration
            r.category = cat
            r.object_type = ot
            r.otype = ""  # toujours effacé
            updated += 1
            if category_changed:
                category_changed_count += 1
            if type_changed:
                type_changed_count += 1
            if args.apply:
                if category_changed:
                    db.session.add(
                        Log(
                            user_id=owner_user_id,
                            repair_id=r.id,
                            content=f"Migration: category '{old_category_name}' -> '{cat.name}'",
                        )
                    )
                if type_changed:
                    db.session.add(
                        Log(
                            user_id=owner_user_id,
                            repair_id=r.id,
                            content=f"Migration: type '{old_otype}' -> '{new_type_name}'",
                        )
                    )
        if not args.apply:
            db.session.rollback()
        else:
            db.session.commit()

        print(f"Rows in file: {total}")
        print(f"Repairs found: {updated}")
        print(f"Missing repairs: {len(missing_repairs)}")
        if missing_repairs:
            print("Missing repairs IDs (first 50):", ", ".join(missing_repairs[:50]))
        print(f"Missing categories (will need to be created manually): {len(missing_categories)}")
        if missing_categories:
            for did, cat_label in missing_categories[:10]:
                print(f"  - {did}: category '{cat_label}' not found")
        print(f"Missing object types (not applied): {len(missing_types)}")
        if missing_types:
            for did, tname, cat_label in missing_types[:15]:
                print(f"  - {did}: type '{tname}' in category '{cat_label}' not found")
        print(
            "New type equals legacy otype (ignore casse/espaces/tirets/accents): "
            f"{equal_type_count}"
        )
        print(f"Category changed: {category_changed_count}")
        print(f"Type changed (significatif): {type_changed_count}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY'}")


if __name__ == "__main__":
    main()
