from fastapi import FastAPI, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Dict, Any
import json
import os
from dotenv import load_dotenv
import google.generativeai as genai
#fastapi\Scripts\activate

# Load environment variables from .env file
load_dotenv()

# Settings from .env
class Settings(BaseSettings):
    gemini_api_key: str = Field(..., env='GEMINI_API_KEY')
    dataset_path: str = Field(..., env='DATASET_PATH')

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_configured(self) -> bool:
        return bool(self.gemini_api_key and self.dataset_path)

settings = Settings()
print("GEMINI_API_KEY =", os.getenv("GEMINI_API_KEY"))
print("DATASET_PATH =", os.getenv("DATASET_PATH"))

# Ensure configuration is valid
if not settings.is_configured:
    raise ValueError(
        "Missing required environment variables. Please ensure both "
        "GEMINI_API_KEY and DATASET_PATH are set in your .env file."
    )

app = FastAPI()

# Load the dataset
def load_dataset(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found at {file_path}.")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Get matching profiles for a role
def get_profiles_for_role(role: str, dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matching_profiles = []
    for profile in dataset:
        experiences = profile.get("Experiences", {})
        for experience in experiences.values():
            if isinstance(experience, dict) and experience.get("Role", "").strip().lower() == role.lower():
                matching_profiles.append(profile)
                break
    return matching_profiles

# Extract skills and projects
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

# Generate summary using Gemini

def generate_summary_with_gemini(skills_summary: str) -> str:
    genai.configure(api_key=settings.gemini_api_key)

    # ✅ Use a supported model: gemini-2.0-flash
    model = genai.GenerativeModel('models/gemini-2.0-flash')

    prompt = f"""
    Based on industry data, most professionals in this role have the following skills: {skills_summary}.
    Please generate a brief summary of the key skills and technologies commonly learned by professionals in this field.
    """

    response = model.generate_content(prompt)
    
    return response.text if hasattr(response, "text") else (
        response.parts[0].text if hasattr(response, "parts") and response.parts else "No summary available."
    )



# API endpoint
@app.get("/job-summary/")
def job_summary(role: str):
    role = role.strip().lower()  # Normalize role input

    try:
        dataset = load_dataset(settings.dataset_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    profiles = get_profiles_for_role(role, dataset)
    if not profiles:
        return {"message": f"No matching profiles found for '{role}'."}
    
    details = extract_details_from_profiles(profiles)
    try:
        gemini_summary = generate_summary_with_gemini(details["skills_summary"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")
    
    return {
        "role": role,
        "skills_summary": details["skills_summary"],
        "gemini_summary": gemini_summary,
        "projects": details["projects"]
    }
