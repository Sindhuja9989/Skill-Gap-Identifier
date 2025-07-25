from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Dict, Any
import json
import os
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai

# Import your resume_parser
from resume_parser import parse_resume

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    gemini_api_key: str = Field(..., env='GEMINI_API_KEY')
    dataset_path: str = Field(..., env='DATASET_PATH')

    #model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_configured(self) -> bool:
        return bool(self.gemini_api_key and self.dataset_path)

settings = Settings()

if not settings.is_configured:
    raise ValueError("Missing required environment variables. Please set GEMINI_API_KEY and DATASET_PATH.")

# Initialize FastAPI
app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can later replace "*" with ["http://localhost:5500"] or wherever your frontend runs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_dataset(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at {file_path}.")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_profiles_for_role(role: str, dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matching_profiles = []
    for profile in dataset:
        experiences = profile.get("Experiences", {})
        for experience in experiences.values():
            if isinstance(experience, dict) and experience.get("Role", "").strip().lower() == role.lower():
                matching_profiles.append(profile)
                break
    return matching_profiles

def extract_details_from_profiles(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    skill_counts = {}
    projects = []
    for profile in profiles:
        skills = profile.get("Skills", {})
        for skill in skills.values():
            skill_counts[skill] = skill_counts.get(skill, 0) + 1
        projects.extend(profile.get("Projects", {}).values())
    sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
    skills_summary = ", ".join([f"{skill} ({count})" for skill, count in sorted_skills])
    return {"skills_summary": skills_summary, "projects": projects}

def generate_summary_with_gemini(prompt: str) -> str:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel('models/gemini-2.0-flash')
    response = model.generate_content(prompt)
    return response.text if hasattr(response, "text") else (
        response.parts[0].text if hasattr(response, "parts") and response.parts else "No summary available."
    )

# Route 1: Summarize by job role only
@app.post("/summarize-role/")
async def summarize_by_job_role(job_role: str = Form(...)):
    try:
        dataset = load_dataset(settings.dataset_path)
        profiles = get_profiles_for_role(job_role, dataset)
        if not profiles:
            return {"message": f"No matching profiles found in dataset for job role '{job_role}'."}

        details = extract_details_from_profiles(profiles)

        prompt = f"""
        Based on industry data, most professionals in this role have the following skills: {details['skills_summary']}.
        Please generate a brief summary of the key skills and technologies commonly learned by professionals in this field.
        """

        gemini_summary = generate_summary_with_gemini(prompt)

        return {
            "job_role": job_role,
            "dataset_skills_summary": details["skills_summary"],
            "gemini_summary": gemini_summary,
            "matched_projects": details["projects"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Route 2: Upload resume + get personalized analysis
@app.post("/upload-resume/")
async def upload_resume(job_role: str = Form(...), resume: UploadFile = File(...)):
    try:
        # Step 1: Parse the uploaded resume
        resume_content = await resume.read()
        resume_file = BytesIO(resume_content)
        resume_data = parse_resume(resume_file)

        resume_skills = resume_data.get('skills', [])

        if not resume_skills:
            return {"message": "Could not extract skills from the uploaded resume."}

        # Step 2: Load professional dataset
        dataset = load_dataset(settings.dataset_path)
        profiles = get_profiles_for_role(job_role, dataset)
        if not profiles:
            return {"message": f"No matching profiles found for job role '{job_role}'."}

        details = extract_details_from_profiles(profiles)

        # Step 3: Create personalized prompt for Gemini
        prompt = f"""
        A user uploaded their resume with the following extracted skills: {', '.join(resume_skills)}.
        Based on the dataset, professionals in the role '{job_role}' commonly have these skills: {details['skills_summary']}.
        Compare the user's skills with industry professionals. Identify skill gaps, overlapping strengths, and suggest areas of improvement.
        """

        gemini_summary = generate_summary_with_gemini(prompt)

        return {
            "job_role": job_role,
            "extracted_resume_data": resume_data,
            "dataset_skills_summary": details["skills_summary"],
            "gemini_summary": gemini_summary,
            "matched_projects": details["projects"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
