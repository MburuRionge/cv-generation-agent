from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import UserProfile
from app import db
import json

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/')
@login_required
def view():
    return render_template('profile/view.html', profile=current_user.profile)

@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        profile = current_user.profile
        
        # Update basic info
        profile.name = request.form.get('name')
        profile.phone = request.form.get('phone')
        
        # Update skills
        skills = request.form.get('skills', '')
        profile.skills = [skill.strip() for skill in skills.split(',') if skill.strip()]
        
        # Update preferences
        preferences = {
            'job_titles': [title.strip() for title in request.form.get('job_titles', '').split(',')],
            'locations': [loc.strip() for loc in request.form.get('locations', '').split(',')],
            'remote_preference': request.form.get('remote_preference', 'any'),
            'salary_expectations': request.form.get('salary_expectations', ''),
            'industries': [ind.strip() for ind in request.form.get('industries', '').split(',')]
        }
        profile.preferences = preferences
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile.view'))
    
    return render_template('profile/edit.html', profile=current_user.profile)

@profile_bp.route('/api/update', methods=['POST'])
@login_required
def api_update():
    try:
        data = request.get_json()
        profile = current_user.profile
        
        if 'experience' in data:
            profile.experience = data['experience']
        if 'education' in data:
            profile.education = data['education']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Profile updated'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400