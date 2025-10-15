from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.services.cv_generator import CVGenerationService
from app.models import JobPosting, Application
from app import db, cache
import json

jobs_bp = Blueprint('jobs', __name__)
cv_service = CVGenerationService()

@jobs_bp.route('/')
@login_required
def search():
    return render_template('jobs/search.html')

@jobs_bp.route('/api/search')
@login_required
@cache.cached(timeout=3600, query_string=True)  # Cache search results
def api_search():
    try:
        jobs = cv_service.fetch_jobs(current_user.profile)
        return jsonify({'success': True, 'jobs': jobs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@jobs_bp.route('/<job_id>/apply', methods=['POST'])
@login_required
def apply(job_id):
    try:
        data = request.get_json()
        job_data = data.get('job')
        
        # Generate cover letter
        cover_letter = cv_service.generate_cover_letter(current_user.profile, job_data)
        
        # Create application record
        application = Application(
            user_id=current_user.id,
            job_id=job_id,  # You might want to store job details differently
            status='applied',
            notes=cover_letter[:500]  # Store first 500 chars as preview
        )
        
        db.session.add(application)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Application submitted successfully',
            'cover_letter': cover_letter
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500