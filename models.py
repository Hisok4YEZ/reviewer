from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String, unique=True, nullable=False)
    google_id = db.Column(db.String, unique=True, nullable=False)
    credits = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    avis = db.Column(db.Text, nullable=False)
    reponse = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DemoReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    auteur = db.Column(db.String)
    note = db.Column(db.String)  # ex: "FIVE"
    texte = db.Column(db.Text)
    date = db.Column(db.String)
    reponse = db.Column(db.Text)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)


class RedemptionCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.String(200))  # email de l'utilisateur
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
