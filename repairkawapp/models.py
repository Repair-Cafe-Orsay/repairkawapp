"""
Modèles SQLAlchemy pour RepairKawapp.
Nettoyage global : imports organisés, PEP8, docstrings, harmonisation du style.
"""

import enum

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

from . import db


class User(UserMixin, db.Model):
    """Définition du modèle réparateur (hérite de UserMixin pour l'authentification)."""

    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    # user information
    email = db.Column(db.String(100), unique=True, nullable=False)
    # Longueur augmentée (255) car les hash pbkdf2:sha256 récents peuvent dépasser 100 caractères
    password = db.Column(db.String(255))
    name = db.Column(db.String(100))
    # admin field
    admin = db.Column(db.Boolean, default=False)
    # Dernière année de cotisation ; None (pas False) pour éviter 0 lors de conversions.
    last_membership = db.Column(db.Integer, default=None)
    # incremental user id - used for authentication
    seqid = db.Column(db.Integer, default=0)
    # rôle éventuel au sein du bureau (président, trésorier, secrétaire, vice-président)
    board_title = db.Column(db.String(30))
    # biographie / description courte modifiable par le réparateur
    biography = db.Column(db.Text)
    # photo de profil (nom de fichier stocké dans UPLOAD_FOLDER)
    photo_filename = db.Column(db.String(200))
    # visibilité dans le trombinoscope public (colonne legacy public_trombi)
    visibility_public_trombi = db.Column(
        "public_trombi", db.Boolean, nullable=False, server_default="1"
    )
    # téléphone optionnel (interne / non public)
    phone = db.Column(db.String(30))
    # membre fondateur
    founder = db.Column(db.Boolean, nullable=False, server_default="0")
    # dernière connexion réussie (mise à jour à chaque login)
    last_connection = db.Column(db.DateTime(timezone=True))


class Category(db.Model):
    """Catégorie telle que définie sur RepairMonitor."""

    __tablename__ = "category"
    id = db.Column(db.Integer, primary_key=True)
    rm_icon_id = db.Column(db.Integer, nullable=True)
    # Nouveau: nom d'icône libre (ex: classe Bootstrap Icons ou Font Awesome)
    icon_name = db.Column(db.String(50), nullable=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return "<Category %r>" % self.name


class ObjectType(db.Model):
    """Type d'objet d'une catégorie (ex: 'Machine à café').

    Sert de référentiel optionnel pour qualifier plus finement la réparation.
    """

    __tablename__ = "object_type"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Catégorie parente
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    category = db.relationship("Category", backref=db.backref("object_types", lazy=True))

    # Variantes (synonymes / alias d'affichage)
    variants = db.relationship(
        "ObjectVariant",
        backref="object_type",
        lazy=True,
        cascade="all, delete-orphan",
    )

    # Sous-types (granularité supplémentaire)
    subtypes = db.relationship(
        "ObjectSubtype",
        backref="object_type",
        lazy=True,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("idx_object_type_category", "category_id"),
        UniqueConstraint("name", "category_id", name="uix_object_type_name_category"),
    )

    def __repr__(self):
        return "<ObjectType %r>" % self.name


class ObjectVariant(db.Model):
    """Variante / alias d'un type d'objet (ex: 'Cafetière', 'Machine Espresso')."""

    __tablename__ = "object_variant"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    object_type_id = db.Column(db.Integer, db.ForeignKey("object_type.id"), nullable=False)

    def __repr__(self):
        return "<ObjectVariant %r>" % self.name


class ObjectSubtype(db.Model):
    """Sous-type d'un type d'objet (ex: pour 'Machine à café' : 'Expresso', 'Filtre')."""

    __tablename__ = "object_subtype"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    object_type_id = db.Column(db.Integer, db.ForeignKey("object_type.id"), nullable=False)

    def __repr__(self):
        return "<ObjectSubtype %r>" % self.name


class Brand(db.Model):
    """Stockage des marques."""

    __tablename__ = "brand"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return "<Brand %r>" % self.name


class State(db.Model):
    """Etat d'un objet - défini lors de l'initialisation de la base."""

    __tablename__ = "state"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return "<State %r>" % self.label


# many2many association between a user (repairer) and an object in the database
repair_user = db.Table(
    "association_repair_user",
    db.Model.metadata,
    db.Column("repair_id", db.ForeignKey("repair.id")),
    db.Column("user_id", db.ForeignKey("user.id")),
)


class Repair(db.Model):
    # the main repair form
    __tablename__ = "repair"
    id = db.Column(db.Integer, primary_key=True)
    # is generated with date and incremental ID
    display_id = db.Column(db.String(11), unique=True)
    # creation date
    created = db.Column(db.Date(), nullable=False)
    # register date
    registered = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    # user information - they are not stored in separate base to avoid tracing visitors
    # no field is required
    name = db.Column(db.String(200))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    age = db.Column(db.Integer)
    # the category - required
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    category = db.relationship("Category")
    # the brand - required
    brand_id = db.Column(db.Integer, db.ForeignKey("brand.id"), nullable=False)
    brand = db.relationship("Brand")
    # initial and current state
    initial_state_id = db.Column(db.Integer, db.ForeignKey("state.id"), nullable=False)
    initial_state = db.relationship("State", foreign_keys=[initial_state_id])
    current_state_id = db.Column(db.Integer, db.ForeignKey("state.id"), nullable=False)
    current_state = db.relationship("State", foreign_keys=[current_state_id])
    # description of the object, model, serial, value, weight
    otype = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(50))
    year = db.Column(db.Integer)
    value = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    # description of the problem
    description = db.Column(db.Text)
    validated = db.Column(db.Boolean)
    users = db.relationship("User", secondary=repair_user)
    # status of the form - can be uploaded in Repair Monitor
    close_status_id = db.Column(
        db.Integer, db.ForeignKey("closestatus.id"), nullable=False, default=1
    )
    close_status = db.relationship("CloseStatus", foreign_keys=[close_status_id])
    # where is the object
    location = db.Column(db.String(50), default="Local")
    # session auquel la réparation est rattachée (optionnel)
    session_id = db.Column(db.Integer, db.ForeignKey("session.id"), nullable=True)
    # Références facultatives vers le référentiel objet
    object_type_id = db.Column(db.Integer, db.ForeignKey("object_type.id"), nullable=True)
    object_type = db.relationship("ObjectType")
    object_subtype_id = db.Column(db.Integer, db.ForeignKey("object_subtype.id"), nullable=True)
    object_subtype = db.relationship("ObjectSubtype")


# association many2many entre session et user (participants)
session_user = db.Table(
    "association_session_user",
    db.Model.metadata,
    db.Column("session_id", db.ForeignKey("session.id")),
    db.Column("user_id", db.ForeignKey("user.id")),
)


class Session(db.Model):
    """Session de réparation (événement: lieu + créneau + participants)."""

    __tablename__ = "session"
    id = db.Column(db.Integer, primary_key=True)
    # Localisation normalisée via table Location (migration remplace ancien champ string).
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"), nullable=True)
    location = db.relationship("Location", foreign_keys=[location_id])
    opened_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at = db.Column(db.DateTime(timezone=True))
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])
    comment = db.Column(db.Text)
    participants = db.relationship("User", secondary=session_user, backref="sessions")
    repairs = db.relationship("Repair", backref="session")


class Location(db.Model):
    """Lieu d'une session (normalisation)."""

    __tablename__ = "location"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)


class Note(db.Model):
    """Note attachée à chaque fiche réparation."""

    __tablename__ = "note"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(
        db.Integer, db.ForeignKey("repair.id", ondelete="CASCADE"), nullable=False
    )
    repair = db.relationship("Repair", foreign_keys=[repair_id])


class Log(db.Model):
    """Historique des modifications de la fiche - toute transformation doit être loggée."""

    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(
        db.Integer, db.ForeignKey("repair.id", ondelete="CASCADE"), nullable=False
    )
    repair = db.relationship("Repair", foreign_keys=[repair_id])


class NotificationType(enum.Enum):
    todo = 1
    mention = 2


class Notification(db.Model):
    """Système de notification."""

    __tablename__ = "notification"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User")
    deadline = db.Column(db.DateTime(timezone=True))
    note_id = db.Column(db.Integer, db.ForeignKey("note.id", ondelete="CASCADE"), nullable=False)
    note = db.relationship("Note")
    notification_type = db.Column(db.Enum(NotificationType))


class MembershipLog(db.Model):
    """Historique des modifications de cotisation (compliance).

    Logue chaque changement de champ last_membership d'un réparateur par un administrateur.
    """

    __tablename__ = "membershiplog"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    admin = db.relationship("User", foreign_keys=[admin_id])
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    old_value = db.Column(db.Integer)
    new_value = db.Column(db.Integer)
    note = db.Column(db.String(200), default="")


class BoardRoleLog(db.Model):
    """Historique des changements de rôle de bureau (admin uniquement)."""

    __tablename__ = "boardrolelog"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    admin = db.relationship("User", foreign_keys=[admin_id])
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", foreign_keys=[user_id])
    old_role = db.Column(db.String(30))
    new_role = db.Column(db.String(30))


class SpareStatus(db.Model):
    """Statut d'une pièce détachée."""

    __tablename__ = "sparestatus"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)


class SpareChange(db.Model):
    """Modification d'une pièce détachée liée à une réparation."""

    __tablename__ = "sparechange"
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(200))
    note = db.Column(db.Text, default="")
    spare_status_id = db.Column(
        db.Integer, db.ForeignKey("sparestatus.id"), nullable=False, default=0
    )
    spare_status = db.relationship("SpareStatus", foreign_keys=[spare_status_id])
    repair_id = db.Column(db.Integer, db.ForeignKey("repair.id"), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])


class CloseStatus(db.Model):
    """Statut de clôture d'une fiche réparation."""

    __tablename__ = "closestatus"
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)


class AppSetting(db.Model):
    """Paramètres globaux applicatifs (singleton id=1)."""

    __tablename__ = "app_setting"
    id = db.Column(db.Integer, primary_key=True)
    maintenance_mode = db.Column(db.Boolean, nullable=False, server_default="0")
    maintenance_until = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Message(db.Model):
    """Message direct (un destinataire) limité à 250 caractères.

    Optionnellement lié à une réparation ou une note pour contexte.
    """

    __tablename__ = "message"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    sender = db.relationship("User", foreign_keys=[sender_id])
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    subject = db.Column(db.String(120))
    body = db.Column(db.String(250), nullable=False)
    repair_id = db.Column(db.Integer, db.ForeignKey("repair.id"), nullable=True, index=True)
    note_id = db.Column(db.Integer, db.ForeignKey("note.id"), nullable=True, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    read_at = db.Column(db.DateTime(timezone=True))
    deleted_sender = db.Column(db.Boolean, nullable=False, server_default="0")
    deleted_recipient = db.Column(db.Boolean, nullable=False, server_default="0")

    __table_args__ = (db.Index("idx_message_recipient_unread", "recipient_id", "read_at"),)

    def mark_read(self):
        from datetime import datetime, timezone

        if not self.read_at:
            self.read_at = datetime.now(timezone.utc)
