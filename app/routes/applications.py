from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file, flash
from flask_login import login_required, current_user
from app import db
from app.models import Application, JobPosting, UserProfile
from datetime import datetime, timedelta
import json
import os
import csv
import io
from sqlalchemy import desc, func

applications_bp = Blueprint('applications', __name__, url_prefix='/appliactions')

@applications_bp('/')
@login_required
def list_applications():
    """Display paginated list of user's applications with filtering"""
    try:
        #Get query parameters
        page = request.args.get('page', 1, type=int)
        status_filter = request.args.get('status', 'all')
        search_query = request.args.get('search', '')
        sort_by = request.args.get('sort', 'applied_date')
        sort_order = request.args.get('order', 'desc')
        
        #Base query
        query = Application.query.fiter_by(user_id=current_user.id)
        
        #Apply filters
        if status_filter != 'all':
            query = query.filter(Application.status == status_filter)
            
        if search_query:
            query = query.join(JobPosting).filter(
                (JobPosting.title.ilike(f'%{search_query}')) |
                (JobPosting.company.ilike(f'%{search_query}%'))
            )
            
        #Apply sorting
        if sort_by == 'company':
            query = query.join(JobPosting)
            if sort_order == 'asc':
                query = query.order_by(JobPosting.company.asc())
            else:
                query = query.order_by(JobPosting.company.desc())
        elif sort_by == 'applied_date':
            if sort_order == 'asc':
                query = query.order_by(Application.applied_date.asc())
            else:
                query = query.order_by(Application.applied_date.desc())
        elif sort_by == 'status':
            if sort_order == 'asc':
                query = query.order_by(Application.status.asc())
            else:
                query = query.order_by(Application.status.desc())
                
        #Pagination
        per_page = 10
        application_page = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Render template  et statistics from the dashboard
        stats = get_application_stats(current_user.id)
        
        return render_template('applications/list.html',
                               applications=application_page,
                               stats=stats,
                               current_status=status_filter,
                               search_query=search_query,
                               sort_by=sort_by,
                               sort_order=sort_order)
    except Exception as e:
        flash('An error occurred while fetching applications.', 'error')
        return redirect(url_for('main.dashboard'))
    
@applications_bp.route('/api/applications')
@login_required
def api_list_applictions():
    """JSON API endpoint for applications(for AJAX requests)"""
    try:
        applications = Application.query.filter_by(user_id=current_user.id).all()
        
        applications_data = [app.to_dict() for app in applications]
        
        return jsonify({
            'success': True,
            'applications': applications_data,
            'count': len(applications_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
@applications_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_application():
    """Cretate a new job application manually"""
    if request.method == 'POST':
        try:
            # Get form data
            company = request.form.get('company')
            job_title = request.form.get('job_title')
            job_url = request.form.get('job_url')
            job_description = request.form.get('job_description')
            status = request.form.get('status', 'applied')
            notes = request.form.get('notes', '')
            
            # Validate required fields
            if not company or not job_title:
                flash('Company and Job Title are required.', 'error')
                return render_template('applications/create.html')
            
            # Create JobPosting record
            job_posting = JobPosting(
                title=job_title,
                company=company,
                url=job_url,
                description=job_description,
                source='manual'
            )
            db.session.add(job_posting)
            db.session.flush() # To get job_posting.id without committting
            
            # Create Application record
            application = Application(
                user_id=current_user.id,
                job_id=job_posting.id,
                status=status,
                notes=notes,
                applied_date=datetime.utcnow()
            )
            db.session.add(application)
            db.session.commit()
            
            flash('Application created successfully.', 'success')
            return redirect(url_for('applications.list_applications'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating application: {str(e)}', 'error')
            return render_template('applications/create.html')
        
    return render_template('applications/create.html')

@applications_bp.route('/<application_id>')
@login_required
def view_application(application_id):
    """View details of a specific application"""
    try:
        application = Application.query.filter_by(
            id=application_id,
            user_id=current_user.id
        ).first_or_404()
        
    except Exception as e:
        flash('An error occurred while fetching the application.', 'error')
        return redirect(url_for('applications.list_applications'))
    
@applications_bp.route('/<application_id>/update', methods=['POST'])
@login_required
def update_application(application_id):
    """Update an existing application status and notes"""
    try:
        application = Application.query.filter_by(
            id=application_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Get form data
        data = request.get_json()
        
        # Update fields
        if 'status' in data:
            application.status = data['status']
        if 'notes' in data:
            application.notes = data['notes']
            
        application.last_updated = datetime.utcnow()
        db.session.commit()
        
        flash('Application updated successfully.', 'success')
        return jsonify({
            'success': True,
            'message': 'Application updated successfully.',
            'application': application.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
@applications_bp.route('/<application_id>/delete', methods=['POST'])
@login_required
def delete_application(application_id):
    """Delete an application"""
    try:
        application = Application.query.filter_by(
            id=application_id,
            user_id=current_user.id
        ).first_or_404()
        
        db.session.delete(application)
        db.session.commit()
        
        flash('Application deleted successfully.', 'success')
        return jsonify({
            'success': True,
            'message': 'Application deleted successfully.'
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
@applications_bp.route('/stats')
@login_required
def application_stats():
    """Get application statistics for dashboard"""
    try:
        stats = get_application_stats(current_user.id)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
def get_application_stats(user_id):
    """Get application statistics for a user"""
    total = Application.query.filter_by(user_id=user_id).count()
    interviews = Application.query.filter_by(user_id=user_id, status='interview').count()
    offers = Application.query.filter_by(user_id=user_id, status='offer').count()
    rejected = Application.query.filetr_by(user_id=user_id, status='rejected').count()
    
    return {
        'total': total,
        'interviews': interviews,
        'offers':offers,
        'rejected': rejected
    }