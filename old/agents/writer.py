from langchain_groq import ChatGroq
from pydantic import BaseModel
from utils.profile import profile
from agents.researcher import JobAnalysis
import os
from dotenv import load_dotenv

load_dotenv()

class CoverLetter(BaseModel):
    subject: str      # email subject line
    body: str         # the actual cover letter

def write_cover_letter(
    job_title: str,
    company_name: str,
    job_description: str,
    analysis: JobAnalysis
) -> CoverLetter:

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY")
    ).with_structured_output(CoverLetter)

    prompt = f"""
    Write a concise, genuine cover letter for {profile['name']} applying to this job.
    
    Job: {job_title} at {company_name}
    Description: {job_description}
    
    Candidate profile:
    - {profile['summary']}
    - Key skills: {', '.join(profile['skills'][:10])}
    - Education: {profile['education'][0]}
    
    Strategy from researcher agent:
    - Fit score: {analysis.fit_score}/100
    - Angle to use: {analysis.cover_letter_angle}
    - Sector identified: {analysis.sector}
    
    Rules:
    - Maximum 3 short paragraphs
    - Do NOT use generic phrases like "I am excited to apply"
    - Be specific about his research and experience
    - Mention he is based in Brazil, working remotely
    - Sound human, not like a bot wrote it
    - End with his email: {profile['email']}
    """

    return llm.invoke(prompt)