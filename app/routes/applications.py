from flask import Blueprint, render_template, request, jsonify
from app.models import Application

applications_bp = Blueprint('applications', __name__)

@applications_bp('/applications')
def list_applications():
    applications = Application.query.all()
    return jsonify("message": "List of applications")