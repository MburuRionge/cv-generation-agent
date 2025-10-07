from app import db
from  datetime import datetime
import uuid

class JobPosting(db.Model):
    id =db.Column(db.String(36), primary_key=True, default=lambda: str(uuid, uuid4()))
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500))
    source = db.Column(db.String(59))
    posted_date = db.Column(db.DateTime)
    match_score = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = db.relationsip('Application', backref='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'description': self.description,
            'url': self.url,
            'source': self.source,
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'match_score': self.match_score,
            'created_at': self.created_at.isoformat()
        }