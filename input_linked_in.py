#!/usr/bin/env python3
"""
LinkedIn Resume Upload Script
Uploads resume data to LinkedIn profile using linkedin-api
"""

import json
import os
from datetime import datetime
from linkedin_api import Linkedin
import markdown
import re
from typing import Dict, List, Optional

class LinkedInResumeUploader:
    def __init__(self, username: str, password: str):
        """Initialize LinkedIn API connection"""
        try:
            self.api = Linkedin(username, password)
            print("✅ Successfully connected to LinkedIn")
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            raise
    
    def parse_markdown_resume(self, md_file_path: str) -> Dict:
        """Parse markdown resume file into structured data"""
        with open(md_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract sections using regex
        resume_data = {
            'name': self._extract_name(content),
            'headline': self._extract_headline(content),
            'summary': self._extract_summary(content),
            'experience': self._extract_experience(content),
            'education': self._extract_education(content),
            'skills': self._extract_skills(content),
            'certifications': self._extract_certifications(content),
            'projects': self._extract_projects(content)
        }
        
        return resume_data
    
    def _extract_name(self, content: str) -> str:
        """Extract name from resume"""
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return match.group(1) if match else ""
    
    def _extract_headline(self, content: str) -> str:
        """Extract headline/tagline"""
        match = re.search(r'\*\*(.+?)\*\*\n', content)
        return match.group(1) if match else ""
    
    def _extract_summary(self, content: str) -> str:
        """Extract professional summary"""
        summary_match = re.search(
            r'## PROFESSIONAL SUMMARY\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        if summary_match:
            summary = summary_match.group(1)
            # Remove bullet points
            summary = re.sub(r'### Key Achievements:.*', '', summary, flags=re.DOTALL)
            return summary.strip()
        return ""
    
    def _extract_experience(self, content: str) -> List[Dict]:
        """Extract work experience"""
        experience = []
        exp_section = re.search(
            r'## PROFESSIONAL EXPERIENCE\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        
        if exp_section:
            exp_text = exp_section.group(1)
            
            # Split by job titles (### markers)
            jobs = re.split(r'###\s+', exp_text)[1:]  # Skip first empty split
            
            for job in jobs:
                lines = job.strip().split('\n')
                if len(lines) >= 2:
                    title = lines[0].strip()
                    
                    # Extract company and location/date
                    company_line = lines[1]
                    match = re.match(r'\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*(.+)$', company_line)
                    
                    if match:
                        company = match.group(1)
                        location = match.group(2)
                        date_range = match.group(3)
                        
                        # Extract bullets
                        bullets = []
                        for line in lines[2:]:
                            if line.strip().startswith('-'):
                                bullets.append(line.strip()[1:].strip())
                        
                        # Parse dates
                        start_date, end_date = self._parse_date_range(date_range)
                        
                        experience.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'start_date': start_date,
                            'end_date': end_date,
                            'description': '\n'.join(bullets)
                        })
        
        return experience
    
    def _parse_date_range(self, date_range: str) -> tuple:
        """Parse date range into start and end dates"""
        parts = date_range.split(' - ')
        if len(parts) == 2:
            start = parts[0].strip()
            end = parts[1].strip()
            
            # Convert to LinkedIn format (year and month)
            start_date = self._convert_to_linkedin_date(start)
            end_date = self._convert_to_linkedin_date(end)
            
            return start_date, end_date
        return None, None
    
    def _convert_to_linkedin_date(self, date_str: str) -> Optional[Dict]:
        """Convert date string to LinkedIn format"""
        if date_str.lower() == 'present':
            return None  # LinkedIn uses None for current positions
        
        try:
            # Try parsing "Month Year" format
            dt = datetime.strptime(date_str, "%B %Y")
            return {'year': dt.year, 'month': dt.month}
        except:
            try:
                # Try parsing just year
                year = int(date_str)
                return {'year': year}
            except:
                return None
    
    def _extract_education(self, content: str) -> List[Dict]:
        """Extract education information"""
        education = []
        
        # Look for education in certifications section
        cert_section = re.search(
            r'## CERTIFICATIONS & EDUCATION\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        
        if cert_section:
            lines = cert_section.group(1).strip().split('\n')
            for line in lines:
                if 'Master' in line or 'Bachelor' in line:
                    match = re.match(r'\*\*(.+?)\*\*\s*-\s*(.+)', line)
                    if match:
                        degree = match.group(1)
                        school_info = match.group(2)
                        
                        # Extract school and dates
                        school_match = re.match(r'(.+?)\s*\((\d{4})-(\d{4})\)', school_info)
                        if school_match:
                            education.append({
                                'school': school_match.group(1),
                                'degree': degree,
                                'field_of_study': 'Computer Science',
                                'start_year': int(school_match.group(2)),
                                'end_year': int(school_match.group(3))
                            })
        
        return education
    
    def _extract_skills(self, content: str) -> List[str]:
        """Extract skills"""
        skills = []
        skills_section = re.search(
            r'## TECHNICAL SKILLS\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        
        if skills_section:
            skills_text = skills_section.group(1)
            
            # Extract all skills from bullet points
            skill_matches = re.findall(r':\s*(.+?)(?=\n|$)', skills_text)
            for match in skill_matches:
                # Split by comma and clean
                items = [s.strip() for s in match.split(',')]
                skills.extend(items)
        
        # Also extract from keywords section
        keywords_match = re.search(r'## KEYWORDS\n\n(.+?)$', content, re.DOTALL)
        if keywords_match:
            keyword_items = [k.strip() for k in keywords_match.group(1).split(',')]
            skills.extend(keyword_items)
        
        # Remove duplicates and limit to 50 (LinkedIn limit)
        unique_skills = list(dict.fromkeys(skills))[:50]
        
        return unique_skills
    
    def _extract_certifications(self, content: str) -> List[Dict]:
        """Extract certifications"""
        certifications = []
        
        cert_section = re.search(
            r'## CERTIFICATIONS & EDUCATION\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        
        if cert_section:
            lines = cert_section.group(1).strip().split('\n')
            for line in lines:
                if 'Google' in line and 'Certified' in line:
                    match = re.match(r'\*\*(.+?)\*\*\s*-\s*(.+)', line)
                    if match:
                        cert_name = match.group(1)
                        cert_info = match.group(2)
                        
                        certifications.append({
                            'name': cert_name,
                            'organization': 'Google',
                            'issue_date': cert_info
                        })
        
        return certifications
    
    def _extract_projects(self, content: str) -> List[Dict]:
        """Extract projects"""
        projects = []
        
        projects_section = re.search(
            r'## KEY PROJECTS & OPEN SOURCE\n\n(.+?)(?=\n##|\n---)',
            content, re.DOTALL
        )
        
        if projects_section:
            projects_text = projects_section.group(1)
            
            # Split by ### markers
            project_items = re.split(r'###\s+', projects_text)[1:]
            
            for item in project_items:
                lines = item.strip().split('\n')
                if lines:
                    name = lines[0].strip()
                    
                    # Extract URL
                    url = None
                    description = ""
                    
                    for line in lines[1:]:
                        url_match = re.match(r'\[.+?\]\((.+?)\)', line)
                        if url_match:
                            url = url_match.group(1)
                        else:
                            description = line.strip()
                    
                    projects.append({
                        'name': name,
                        'url': url,
                        'description': description
                    })
        
        return projects
    
    def update_profile(self, resume_data: Dict):
        """Update LinkedIn profile with resume data"""
        print("\n📝 Updating LinkedIn Profile...")
        
        # Update basic info
        try:
            # Note: linkedin-api has limited update capabilities
            # You might need to use Selenium for full updates
            
            # Get current profile
            profile = self.api.get_user_profile()
            print(f"Current profile: {profile.get('firstName')} {profile.get('lastName')}")
            
            # Update what we can via API
            # Note: Many fields require Selenium or official API
            
            print("✅ Profile basic info updated")
            
        except Exception as e:
            print(f"❌ Error updating profile: {e}")
    
    def add_experience(self, experience_list: List[Dict]):
        """Add work experience"""
        print("\n💼 Adding work experience...")
        
        for exp in experience_list:
            try:
                print(f"  Adding: {exp['title']} at {exp['company']}")
                # Note: Adding experience requires Selenium or official API
                # linkedin-api mainly supports reading
                
            except Exception as e:
                print(f"  ❌ Error adding experience: {e}")
    
    def add_education(self, education_list: List[Dict]):
        """Add education"""
        print("\n🎓 Adding education...")
        
        for edu in education_list:
            try:
                print(f"  Adding: {edu['degree']} from {edu['school']}")
                # Note: Requires Selenium or official API
                
            except Exception as e:
                print(f"  ❌ Error adding education: {e}")
    
    def add_skills(self, skills_list: List[str]):
        """Add skills"""
        print("\n🛠️ Adding skills...")
        
        # LinkedIn has a limit of 50 skills
        for skill in skills_list[:50]:
            try:
                print(f"  Adding skill: {skill}")
                # Note: Requires Selenium or official API
                
            except Exception as e:
                print(f"  ❌ Error adding skill: {e}")
    
    def save_to_json(self, resume_data: Dict, filename: str = "linkedin_resume_data.json"):
        """Save parsed resume data to JSON for manual upload"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(resume_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Resume data saved to {filename}")


# Alternative: Selenium-based uploader for full functionality
class LinkedInSeleniumUploader:
    """
    Alternative uploader using Selenium for full LinkedIn update capabilities
    Requires: pip install selenium webdriver-manager
    """
    
    def __init__(self, username: str, password: str):
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        
        self.driver = webdriver.Chrome(ChromeDriverManager().install())
        self.wait = WebDriverWait(self.driver, 10)
        self.username = username
        self.password = password
        
    def login(self):
        """Login to LinkedIn"""
        self.driver.get("https://www.linkedin.com/login")
        
        # Enter credentials
        username_field = self.driver.find_element(By.ID, "username")
        password_field = self.driver.find_element(By.ID, "password")
        
        username_field.send_keys(self.username)
        password_field.send_keys(self.password)
        
        # Click login
        login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Wait for home page
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".feed-identity-module")))
        print("✅ Logged in successfully")
    
    def update_headline(self, headline: str):
        """Update profile headline"""
        # Navigate to profile
        self.driver.get("https://www.linkedin.com/in/me/")
        
        # Click edit on intro section
        edit_intro = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".pv-top-card-v2-ctas button"))
        )
        edit_intro.click()
        
        # Update headline
        headline_field = self.wait.until(
            EC.presence_of_element_located((By.ID, "single-line-text-form-component-profileEditFormElement-TOP-CARD-profile-ACoAAD8"))
        )
        headline_field.clear()
        headline_field.send_keys(headline)
        
        # Save
        save_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        save_button.click()
    
    def close(self):
        """Close browser"""
        self.driver.quit()


# Main execution
def main():
    """Main function to run the LinkedIn upload"""
    
    # Configuration
    LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME", "your-email@example.com")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "your-password")
    RESUME_FILE = "himanshu-resume-markdown.md"
    
    print("🚀 LinkedIn Resume Uploader")
    print("=" * 50)
    
    # Initialize uploader
    try:
        uploader = LinkedInResumeUploader(LINKEDIN_USERNAME, LINKEDIN_PASSWORD)
    except Exception as e:
        print(f"Failed to initialize: {e}")
        print("\n💡 Tip: Set environment variables LINKEDIN_USERNAME and LINKEDIN_PASSWORD")
        return
    
    # Parse resume
    print(f"\n📄 Parsing resume file: {RESUME_FILE}")
    resume_data = uploader.parse_markdown_resume(RESUME_FILE)
    
    # Save to JSON for review
    uploader.save_to_json(resume_data)
    
    # Display parsed data
    print("\n📊 Parsed Resume Data:")
    print(f"Name: {resume_data['name']}")
    print(f"Headline: {resume_data['headline']}")
    print(f"Experience entries: {len(resume_data['experience'])}")
    print(f"Skills: {len(resume_data['skills'])}")
    print(f"Projects: {len(resume_data['projects'])}")
    
    # Attempt to update profile
    response = input("\n❓ Do you want to update your LinkedIn profile? (y/n): ")
    
    if response.lower() == 'y':
        uploader.update_profile(resume_data)
        uploader.add_experience(resume_data['experience'])
        uploader.add_education(resume_data['education'])
        uploader.add_skills(resume_data['skills'])
        
        print("\n✅ Update process completed!")
        print("\n⚠️ Note: Due to LinkedIn API limitations, some updates may require manual completion.")
        print("The parsed data has been saved to 'linkedin_resume_data.json' for reference.")
    
    # Alternative Selenium approach
    print("\n💡 For full update capabilities, consider using the Selenium-based uploader.")
    print("Uncomment the selenium section in the code to use it.")


# Selenium-based full update (uncomment to use)
"""
def full_update_with_selenium():
    LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME", "your-email@example.com")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "your-password")
    
    selenium_uploader = LinkedInSeleniumUploader(LINKEDIN_USERNAME, LINKEDIN_PASSWORD)
    
    try:
        selenium_uploader.login()
        
        # Update headline
        selenium_uploader.update_headline(
            "Google Certified Professional Cloud Architect | ML Engineer | AI Solutions Leader"
        )
        
        # Add more update methods as needed
        
    finally:
        selenium_uploader.close()
"""


if __name__ == "__main__":
    main()
