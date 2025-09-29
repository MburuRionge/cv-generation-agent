import os
import json
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import webbrowser
import pytz
from bs4 import BeautifulSoup
import feedparser
import openai  # For AI-powered content generation
from PyPDF2 import PdfReader  # For parsing existing resumes
import docx  # For parsing Word documents
from dotenv import load_dotenv
# Load environment variables from .env
load_dotenv()

# Configuration
CONFIG = {
    "user_profile": os.getenv("USER_PROFILE", "profile.json"),
    "applications_db": os.getenv("APPLICATIONS_DB", "applications.db"),
    "output_folder": os.getenv("OUTPUT_FOLDER", "generated_applications"),
    "job_sources": {
        "indeed": "https://rss.indeed.com/rss?q={query}&l={location}",
        "linkedin": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
        "glassdoor": "https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={query}&sc.keyword={query}&locT=C&locId={location}"
    },
    "email_alerts": {
        "enabled": os.getenv("EMAIL_ALERTS_ENABLED", "True").lower() == "true",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "email": os.getenv("EMAIL_USER",),
        "password": os.getenv("EMAIL_PASSWORD")
    },
    "openai_api_key": os.getenv("OPEN_API_KEY"),
}

@dataclass
class JobPosting:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: str
    match_score: float = 0.0

@dataclass
class UserProfile:
    name: str
    email: str
    phone: str
    skills: List[str]
    experience: List[Dict]
    education: List[Dict]
    preferences: Dict
    cv_files: List[str]
    cover_letter_templates: List[str]

class CVGenerationAgent:
    def __init__(self):
        self.user_profile = self.load_user_profile()
        self.setup_openai()
        self.ensure_output_folder()
        
    def setup_openai(self):
        """Initialize OpenAI API"""
        openai.api_key = os.getenv("OPEN_API_KEY")
        
    def ensure_output_folder(self):
        """Create output folder if it doesn't exist"""
        if not os.path.exists(CONFIG["output_folder"]):
            os.makedirs(CONFIG["output_folder"])
    
    def load_user_profile(self) -> UserProfile:
        """Load user profile from JSON file"""
        try:
            with open(CONFIG["user_profile"], 'r') as f:
                data = json.load(f)
                return UserProfile(
                    name=data["name"],
                    email=data["email"],
                    phone=data["phone"],
                    skills=data["skills"],
                    experience=data["experience"],
                    education=data["education"],
                    preferences=data["preferences"],
                    cv_files=data.get("cv_files", []),
                    cover_letter_templates=data.get("cover_letter_templates", [])
                )
        except FileNotFoundError:
            print("Profile not found. Please create a profile first.")
            return self.create_new_profile()
    
    def create_new_profile(self) -> UserProfile:
        """Create a new user profile interactively"""
        print("Creating a new user profile...")
        name = input("Full name: ")
        email = input("Email: ")
        phone = input("Phone: ")
        
        print("\nEnter your skills (comma separated): ")
        skills = [s.strip() for s in input().split(",")]
        
        experience = []
        while True:
            print("\nAdd work experience (leave company name blank to finish):")
            company = input("Company name: ")
            if not company:
                break
            title = input("Job title: ")
            start_date = input("Start date (MM/YYYY): ")
            end_date = input("End date (MM/YYYY) or 'Present': ")
            description = input("Description: ")
            experience.append({
                "company": company,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "description": description
            })
        
        education = []
        while True:
            print("\nAdd education (leave institution blank to finish):")
            institution = input("Institution: ")
            if not institution:
                break
            degree = input("Degree: ")
            field = input("Field of study: ")
            graduation_year = input("Graduation year: ")
            education.append({
                "institution": institution,
                "degree": degree,
                "field": field,
                "graduation_year": graduation_year
            })
        
        preferences = {
            "job_titles": input("\nPreferred job titles (comma separated): ").split(","),
            "locations": input("Preferred locations (comma separated): ").split(","),
            "remote_preference": input("Remote preference (Remote, Hybrid, Onsite, Any): "),
            "salary_expectations": input("Salary expectations: "),
            "industries": input("Preferred industries (comma separated): ").split(",")
        }
        
        profile = UserProfile(
            name=name,
            email=email,
            phone=phone,
            skills=skills,
            experience=experience,
            education=education,
            preferences=preferences,
            cv_files=[],
            cover_letter_templates=[]
        )
        
        self.save_profile(profile)
        return profile
    
    def save_profile(self, profile: UserProfile):
        """Save user profile to JSON file"""
        data = {
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "skills": profile.skills,
            "experience": profile.experience,
            "education": profile.education,
            "preferences": profile.preferences,
            "cv_files": profile.cv_files,
            "cover_letter_templates": profile.cover_letter_templates
        }
        
        with open(CONFIG["user_profile"], 'w') as f:
            json.dump(data, f, indent=2)
    
    def fetch_job_alerts(self) -> List[JobPosting]:
        """Fetch job alerts from various sources"""
        jobs = []
        query = "+".join(self.user_profile.preferences["job_titles"])
        location = "+".join(self.user_profile.preferences["locations"])
        
        # Fetch from Indeed RSS
        indeed_url = CONFIG["job_sources"]["indeed"].format(query=query, location=location)
        indeed_jobs = self.parse_rss_feed(indeed_url, "indeed")
        jobs.extend(indeed_jobs)
        
        # TODO: Add other job sources with proper parsing
        
        # Score and filter jobs
        scored_jobs = [self.score_job_match(job) for job in jobs]
        filtered_jobs = [job for job in scored_jobs if job.match_score >= 0.5]
        
        return sorted(filtered_jobs, key=lambda x: x.match_score, reverse=True)
    
    def parse_rss_feed(self, url: str, source: str) -> List[JobPosting]:
        """Parse RSS feed from job sites"""
        feed = feedparser.parse(url)
        jobs = []
        
        for entry in feed.entries:
            job = JobPosting(
                title=entry.title,
                company=self.extract_company_from_title(entry.title),
                location=self.extract_location(entry),
                description=entry.description,
                url=entry.link,
                source=source,
                posted_date=entry.published
            )
            jobs.append(job)
        
        return jobs
    
    def extract_company_from_title(self, title: str) -> str:
        """Extract company name from job title if in format 'Job at Company'"""
        if " at " in title:
            return title.split(" at ")[1]
        return "Unknown Company"
    
    def extract_location(self, entry) -> str:
        """Extract location from RSS entry"""
        if hasattr(entry, 'location'):
            return entry.location
        return "Location not specified"
    
    def score_job_match(self, job: JobPosting) -> JobPosting:
        """Score how well a job matches the user's profile"""
        score = 0.0
        
        # Check title match
        title_keywords = " ".join(self.user_profile.preferences["job_titles"]).lower()
        if any(keyword in job.title.lower() for keyword in title_keywords.split()):
            score += 0.3
        
        # Check skills match
        description = job.description.lower()
        matched_skills = sum(1 for skill in self.user_profile.skills if skill.lower() in description)
        if matched_skills > 0:
            score += 0.2 * (matched_skills / len(self.user_profile.skills))
        
        # Check location preference
        preferred_locations = [loc.lower() for loc in self.user_profile.preferences["locations"]]
        if any(loc in job.location.lower() for loc in preferred_locations):
            score += 0.2
        elif "remote" in job.location.lower() and self.user_profile.preferences["remote_preference"].lower() in ["remote", "any"]:
            score += 0.15
        
        # Check company/industry (simplified)
        # TODO: Implement more sophisticated industry matching
        
        job.match_score = min(1.0, score)  # Cap at 1.0
        return job
    
    def generate_application_materials(self, job: JobPosting):
        """Generate CV, cover letter, and other materials for a job application"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{job.company.replace(' ', '_')}_{job.title.replace(' ', '_')}_{timestamp}"
        
        # Select the most relevant CV template
        cv_template = self.select_cv_template(job)
        
        # Generate tailored CV
        tailored_cv = self.tailor_cv(cv_template, job)
        cv_filename = os.path.join(CONFIG["output_folder"], f"{base_filename}_CV.pdf")
        self.save_as_pdf(tailored_cv, cv_filename)
        
        # Generate cover letter
        cover_letter = self.generate_cover_letter(job)
        cl_filename = os.path.join(CONFIG["output_folder"], f"{base_filename}_CoverLetter.docx")
        self.save_as_docx(cover_letter, cl_filename)
        
        # Record application
        self.record_application(job, cv_filename, cl_filename)
        
        return {
            "cv": cv_filename,
            "cover_letter": cl_filename
        }
    
    def select_cv_template(self, job: JobPosting) -> str:
        """Select the most appropriate CV template for the job"""
        if not self.user_profile.cv_files:
            raise ValueError("No CV templates available. Please add CV templates to your profile.")
        
        # Simple implementation - just use the first template
        # TODO: Implement more sophisticated template selection
        return self.user_profile.cv_files[0]
    
    def tailor_cv(self, cv_template: str, job: JobPosting) -> str:
        """Tailor a CV template to a specific job"""
        # Parse existing CV
        cv_content = self.parse_cv_file(cv_template)
        
        # Use AI to tailor the CV
        prompt = f"""
        Tailor this CV for a {job.title} position at {job.company}. 
        The job description is: {job.description[:1000]}...
        
        Here's the current CV:
        {cv_content}
        
        Focus on highlighting relevant skills and experience. Return the tailored CV in Markdown format.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional CV writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    def parse_cv_file(self, filepath: str) -> str:
        """Parse CV file content based on file type"""
        if filepath.endswith('.pdf'):
            return self.parse_pdf(filepath)
        elif filepath.endswith('.docx'):
            return self.parse_docx(filepath)
        elif filepath.endswith('.txt'):
            with open(filepath, 'r') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file format: {filepath}")
    
    def parse_pdf(self, filepath: str) -> str:
        """Extract text from PDF"""
        with open(filepath, 'rb') as f:
            reader = PdfReader(f)
            text = "\n".join(page.extract_text() for page in reader.pages)
            return text
    
    def parse_docx(self, filepath: str) -> str:
        """Extract text from Word document"""
        doc = docx.Document(filepath)
        return "\n".join(para.text for para in doc.paragraphs)
    
    def generate_cover_letter(self, job: JobPosting) -> str:
        """Generate a tailored cover letter for a job"""
        prompt = f"""
        Write a professional cover letter for {self.user_profile.name} applying for the {job.title} 
        position at {job.company}. Here are the key details:
        
        Job Description: {job.description[:1000]}...
        
        Applicant Skills: {', '.join(self.user_profile.skills)}
        
        Applicant Experience: {json.dumps(self.user_profile.experience, indent=2)}
        
        The cover letter should be concise (3-4 paragraphs), highlight relevant experience, 
        and express enthusiasm for the position. Use a professional tone.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional cover letter writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    def save_as_pdf(self, content: str, filename: str):
        """Save content as PDF (simplified - would use a proper PDF library in production)"""
        # TODO: Implement proper PDF generation with formatting
        with open(filename.replace('.pdf', '.txt'), 'w') as f:
            f.write(content)
        print(f"PDF saved as {filename} (placeholder - actual PDF generation would be implemented)")
    
    def save_as_docx(self, content: str, filename: str):
        """Save content as Word document"""
        doc = docx.Document()
        for paragraph in content.split('\n'):
            doc.add_paragraph(paragraph)
        doc.save(filename)
    
    def record_application(self, job: JobPosting, cv_path: str, cl_path: str):
        """Record a job application in the database"""
        application = {
            "job_title": job.title,
            "company": job.company,
            "date_applied": datetime.now().isoformat(),
            "status": "Applied",
            "job_description": job.description,
            "job_url": job.url,
            "cv_used": cv_path,
            "cover_letter_used": cl_path,
            "source": job.source,
            "match_score": job.match_score
        }
        
        # Load existing applications
        applications = []
        if os.path.exists(CONFIG["applications_db"]):
            with open(CONFIG["applications_db"], 'r') as f:
                try:
                    applications = json.load(f)
                except json.JSONDecodeError:
                    applications = []
        
        # Add new application
        applications.append(application)
        
        # Save back to file
        with open(CONFIG["applications_db"], 'w') as f:
            json.dump(applications, f, indent=2)
    
    def send_alert(self, subject: str, message: str):
        """Send email alert about job applications"""
        if not CONFIG["email_alerts"]["enabled"]:
            print("Email alerts are disabled in configuration.")
            return
        
        msg = MIMEMultipart()
        msg['From'] = CONFIG["email_alerts"]["email"]
        msg['To'] = self.user_profile.email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        try:
            server = smtplib.SMTP(CONFIG["email_alerts"]["smtp_server"], CONFIG["email_alerts"]["smtp_port"])
            server.starttls()
            server.login(CONFIG["email_alerts"]["email"], CONFIG["email_alerts"]["password"])
            server.send_message(msg)
            server.quit()
            print("Alert email sent successfully.")
        except Exception as e:
            print(f"Failed to send alert email: {e}")
    
    def monitor_applications(self):
        """Monitor status of sent applications"""
        if not os.path.exists(CONFIG["applications_db"]):
            print("No applications found to monitor.")
            return
        
        with open(CONFIG["applications_db"], 'r') as f:
            applications = json.load(f)
        
        pending = [app for app in applications if app["status"] in ["Applied", "Under Review"]]
        if pending:
            message = "Pending applications:\n\n"
            for app in pending:
                days_pending = (datetime.now() - datetime.fromisoformat(app["date_applied"])).days
                message += f"- {app['job_title']} at {app['company']} ({days_pending} days ago)\n"
            
            self.send_alert("Pending Job Applications Update", message)
    
    def run(self, auto_apply: bool = False):
        """Run the CV generation agent"""
        print(f"Starting CV Generation Agent for {self.user_profile.name}")
        
        # Step 1: Fetch job alerts
        print("\nFetching job alerts...")
        jobs = self.fetch_job_alerts()
        
        if not jobs:
            print("No matching jobs found.")
            return
        
        print(f"\nFound {len(jobs)} matching jobs:")
        for i, job in enumerate(jobs[:5]):  # Show top 5
            print(f"{i+1}. {job.title} at {job.company} ({job.location}) - Match: {job.match_score:.0%}")
        
        # Step 2: Process jobs
        for job in jobs[:3]:  # Limit to top 3 for demo
            print(f"\nProcessing: {job.title} at {job.company}")
            
            if auto_apply or input("Apply for this job? (y/n): ").lower() == 'y':
                # Step 3: Generate application materials
                print("Generating application materials...")
                try:
                    materials = self.generate_application_materials(job)
                    print(f"Generated CV: {materials['cv']}")
                    print(f"Generated Cover Letter: {materials['cover_letter']}")
                    
                    # Step 4: Submit application (placeholder)
                    print(f"Would submit application to {job.url} in a real implementation")
                    
                    # Step 5: Send alert
                    alert_msg = f"""
                    New job application submitted:
                    
                    Position: {job.title}
                    Company: {job.company}
                    Location: {job.location}
                    
                    Application materials generated:
                    - CV: {materials['cv']}
                    - Cover Letter: {materials['cover_letter']}
                    
                    Good luck!
                    """
                    self.send_alert(f"Application Submitted: {job.title} at {job.company}", alert_msg)
                except Exception as e:
                    print(f"Failed to process job {job.title}: {e}")
        
        # Monitor existing applications
        print("\nChecking status of existing applications...")
        self.monitor_applications()
        
        print("\nCV Generation Agent completed successfully.")

if __name__ == "__main__":
    agent = CVGenerationAgent()
    agent.run(auto_apply=False)  # Set to True for automatic application without prompts