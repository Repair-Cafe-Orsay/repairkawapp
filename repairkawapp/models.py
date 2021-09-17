from flask_login import UserMixin
from sqlalchemy.sql import func
from . import db

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

class Category(db.Model):
    __tablename__ = 'category'
    id = db.Column(db.Integer, primary_key=True)
    rm_icon_id = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<Category %r>' % self.name

class Brand(db.Model):
    __tablename__ = 'brand'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<Brand %r>' % self.name

class State(db.Model):
    __tablename__ = 'state'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return '<State %r>' % self.label


repair_user = db.Table('association_repair_user', db.Model.metadata,
                       db.Column('repair_id', db.ForeignKey('repair.id')),
                       db.Column('user_id', db.ForeignKey('user.id'))
)

class Repair(db.Model):
    __tablename__ = 'repair'
    id = db.Column(db.Integer, primary_key=True)
    display_id = db.Column(db.String(11), unique=True)
    created = db.Column(db.Date(), nullable=False)
    registered = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    name = db.Column(db.String(200))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    age = db.Column(db.Integer)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship("Category")
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'), nullable=False)
    brand = db.relationship("Brand")
    initial_state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
    initial_state = db.relationship("State", foreign_keys=[initial_state_id])
    current_state_id = db.Column(db.Integer, db.ForeignKey('state.id'), nullable=False)
    current_state = db.relationship("State", foreign_keys=[current_state_id])
    otype = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(50), nullable=False)
    serial_number = db.Column(db.String(50))
    year = db.Column(db.Integer)
    value = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    description = db.Column(db.Text)
    validated = db.Column(db.Boolean)
    users = db.relationship("User",
                            secondary=repair_user)
    close_status_id = db.Column(db.Integer, db.ForeignKey('closestatus.id'), nullable=False, default=1)
    close_status = db.relationship("CloseStatus", foreign_keys=[close_status_id])
    location = db.Column(db.String(50), default="Local")


class Note(db.Model):
    __tablename__ = 'note'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(db.Integer, db.ForeignKey('repair.id'), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])

class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship("User")
    date = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    content = db.Column(db.Text)
    repair_id = db.Column(db.Integer, db.ForeignKey('repair.id'), nullable=False)
    repair = db.relationship("Repair", foreign_keys=[repair_id])

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
