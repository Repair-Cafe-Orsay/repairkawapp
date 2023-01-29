from flask_login import UserMixin
from sqlalchemy.sql import func
from . import db
import enum

# many2many association between a user (repairer) and an object in the database
repair_user = db.Table('association_repair_user', db.Model.metadata,
                       db.Column('repair_id', db.ForeignKey('repair.id')),
                       db.Column('user_id', db.ForeignKey('user.id'))
)

repaircafe_user = db.Table('association_repaircafe_user', db.Model.metadata,
                       db.Column('repaircafe_id', db.ForeignKey('repaircafe.id')),
                       db.Column('user_id', db.ForeignKey('user.id')))

class User(UserMixin, db.Model):
    """User definition, inherit from UserMixin for authentication"""
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    # user information
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))
    # admin field
    admin = db.Column(db.Boolean, default=False)
    last_membership = db.Column(db.Integer, default=False)
    # incremental user id - used for authentication
    seqid = db.Column(db.Integer, default=0)
    repaircafes = db.relationship("RepairCafe",
                                  secondary=repaircafe_user)

class Category(db.Model):
    """Category as defined on RepairMonitor"""
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    rm_icon_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<Category %r>' % self.name

class Brand(db.Model):
    """Used for storing of all brands"""

    __tablename__ = 'brand'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<Brand %r>' % self.name

class State(db.Model):
    """State of an object - defined in database initialization"""
    __tablename__ = 'state'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<State %r>' % self.label

class Repair(db.Model):
    # the main repair form
    __tablename__ = 'repair'
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
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship("Category")
    # the brand - required
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'), nullable=False)
    brand = db.relationship("Brand")
    # initial and current state
    initial_state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
    initial_state = db.relationship("State", foreign_keys=[initial_state_id])
    current_state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
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
    users = db.relationship("User",
                            secondary=repair_user)
    # status of the form - can be uploaded in Repair Monitor
    close_status_id = db.Column(db.Integer, db.ForeignKey('closestatus.id'), nullable=False, default=1)
    close_status = db.relationship("CloseStatus", foreign_keys=[close_status_id])
    # where is the object
    location = db.Column(db.String(50), default="Local")
    repaircafe_id = db.Column(db.Integer, db.ForeignKey('repaircafe.id'), nullable=False)


class Note(db.Model):
    r"""Note attached to each form"""
    __tablename__ = 'note'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(db.Integer, db.ForeignKey('repair.id', ondelete='CASCADE'), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])

class Log(db.Model):
    r"""modification history of the form - any transformation should be logged"""
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(db.Integer, db.ForeignKey('repair.id', ondelete='CASCADE'), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])

class NotificationType(enum.Enum):
    todo = 1
    mention = 2

class Notification(db.Model):
    r"""notification system"""
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User")
    deadline = db.Column(db.DateTime(timezone=True))
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False)
    note = db.relationship("Note")
    notification_type = db.Column(db.Enum(NotificationType))

class SpareStatus(db.Model):
    __tablename__ = 'sparestatus'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)

class SpareChange(db.Model):
    __tablename__ = 'sparechange'
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(200))
    note = db.Column(db.Text, default="")
    spare_status_id = db.Column(db.Integer, db.ForeignKey('sparestatus.id'), nullable=False, default=0)
    spare_status = db.relationship("SpareStatus", foreign_keys=[spare_status_id])
    repair_id = db.Column(db.Integer, db.ForeignKey('repair.id'), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])

class CloseStatus(db.Model):
    __tablename__ = 'closestatus'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)

class RepairCafe(db.Model):
    __tablename__ = 'repaircafe'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(45), nullable=False, unique=True)
