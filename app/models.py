from app.extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

class FishSpecimen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    chinese_name = db.Column(db.String(100), nullable=False)
    scientific_name = db.Column(db.String(150), nullable=False)
    kingdom = db.Column(db.String(50), nullable=False)
    phylum = db.Column(db.String(50), nullable=False)
    class_ = db.Column(db.String(50), nullable=False)
    order = db.Column(db.String(50), nullable=False)
    family = db.Column(db.String(50), nullable=False)
    genus = db.Column(db.String(50), nullable=False)
    species = db.Column(db.String(50), nullable=False)
    collector = db.Column(db.String(100))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)
    location = db.Column(db.String(200))
    category = db.Column(db.String(50))
    image_urls = db.Column(db.JSON)
    qr_code_url = db.Column(db.String(200))