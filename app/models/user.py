from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json
import uuid

class User(UserMixin, db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Profile relationship
    profile = db.relationship('UserProfile', backref='user', uselist=False, lazy=True)
    applications = db.relationship('Application', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

class UserProfile(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    skills = db.Column(db.JSON)  # Store as JSON array
    experience = db.Column(db.JSON)  # Store as JSON array of objects
    education = db.Column(db.JSON)  # Store as JSON array of objects
    preferences = db.Column(db.JSON)  # Store as JSON object
    cv_files = db.Column(db.JSON)  # Store file paths as JSON array
    cover_letter_templates = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.user.email,
            'phone': self.phone,
            'skills': self.skills or [],
            'experience': self.experience or [],
            'education': self.education or [],
            'preferences': self.preferences or {},
            'cv_files': self.cv_files or [],
            'cover_letter_templates': self.cover_letter_templates or []
        }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)