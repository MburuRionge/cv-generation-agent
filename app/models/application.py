from app import db
from datetime import datetime
import uuid

class Application(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    job_id = db.Column(db.String(36), db.ForeignKey('job_posting.id'), nullable=False)
    
    #Application details
    status = db.Column(db.String(50), default='applied') # applied, interview, rejected, offered
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    cv_path = db.Column(db.String(500))
    cover_letter_path = db.Column(db.String(500))
    notes = db.Column(db.Text)
    
    # Tracking
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'job_title': self.job.title,
            'company': self.job.company,
            'status': self.status,
            'applied_date': self.applied_date.isoformat(),
            'match_score': self.job.match_score,
            'last_updated': self.last_updated.isoformat()
        }