import os
import json
from datetime import datetime
from typing import List, Dict, Optional
import openai
from app import db, cache
from app.models import UserProfile, JobPosting
import requests
from PyPDF2 import PdfReader
import docx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import feedparser

class CVGenerationService:
    def __init__(self):
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        openai.api_key = self.openai_api_key
    
    @cache.memoize(timeout=3600)  # Cache for 1 hour
    def fetch_jobs(self, user_profile: UserProfile) -> List[Dict]:
        """Fetch and score jobs for user profile"""
        jobs = []
        preferences = user_profile.preferences or {}
        
        query = "+".join(preferences.get('job_titles', ['developer']))
        location = "+".join(preferences.get('locations', ['remote']))
        
        # Fetch from Indeed RSS
        indeed_url = f"https://rss.indeed.com/rss?q={query}&l={location}"
        indeed_jobs = self.parse_rss_feed(indeed_url, "indeed")
        
        # Score jobs
        scored_jobs = [self.score_job_match(job, user_profile) for job in indeed_jobs]
        filtered_jobs = [job for job in scored_jobs if job['match_score'] >= 0.5]
        
        return sorted(filtered_jobs, key=lambda x: x['match_score'], reverse=True)
    
    def parse_rss_feed(self, url: str, source: str) -> List[Dict]:
        """Parse RSS feed from job sites"""
        feed = feedparser.parse(url)
        jobs = []
        
        for entry in feed.entries:
            job = {
                'title': entry.title,
                'company': self.extract_company_from_title(entry.title),
                'location': getattr(entry, 'location', 'Location not specified'),
                'description': entry.description,
                'url': entry.link,
                'source': source,
                'posted_date': entry.published
            }
            jobs.append(job)
        
        return jobs
    
    def score_job_match(self, job: Dict, user_profile: UserProfile) -> Dict:
        """Score how well a job matches the user's profile"""
        score = 0.0
        preferences = user_profile.preferences or {}
        skills = user_profile.skills or []
        
        # Check title match
        title_keywords = " ".join(preferences.get('job_titles', [])).lower()
        if any(keyword in job['title'].lower() for keyword in title_keywords.split()):
            score += 0.3
        
        # Check skills match
        description = job['description'].lower()
        matched_skills = sum(1 for skill in skills if skill.lower() in description)
        if matched_skills > 0:
            score += 0.2 * (matched_skills / len(skills))
        
        job['match_score'] = min(1.0, score)
        return job
    
    def generate_cover_letter(self, user_profile: UserProfile, job: Dict) -> str:
        """Generate a tailored cover letter using OpenAI"""
        prompt = f"""
        Write a professional cover letter for {user_profile.name} applying for the {job['title']} 
        position at {job['company']}. Here are the key details:
        
        Job Description: {job['description'][:1000]}...
        
        Applicant Skills: {', '.join(user_profile.skills or [])}
        
        The cover letter should be concise (3-4 paragraphs), highlight relevant experience, 
        and express enthusiasm for the position. Use a professional tone.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Use gpt-4 if available
                messages=[
                    {"role": "system", "content": "You are a professional cover letter writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating cover letter: {str(e)}"
    
    def tailor_resume(self, user_profile: UserProfile, job: Dict, resume_content: str) -> str:
        """Tailor resume content for specific job using AI"""
        prompt = f"""
        Tailor this resume for a {job['title']} position at {job['company']}. 
        The job description is: {job['description'][:1000]}...
        
        Here's the current resume:
        {resume_content}
        
        Focus on highlighting relevant skills and experience. Return the tailored resume in Markdown format.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional resume writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error tailoring resume: {str(e)}"
    
    def extract_company_from_title(self, title: str) -> str:
        """Extract company name from job title"""
        if " at " in title:
            return title.split(" at ")[1]
        return "Unknown Company"