from langchain_groq import ChatGroq
from pydantic import BaseModel
from utils.profile import profile
import os
from dotenv import load_dotenv

load_dotenv()

# The structured output the researcher will return
class JobAnalysis(BaseModel):
    fit_score: int          # 0 to 100
    fit_reason: str         # why it's a good or bad fit
    sector: str             # what sector this company is in
    salary_to_put: int      # what salary to put on the form (in USD)
    salary_reason: str      # why that salary
    should_apply: bool      # final decision
    cover_letter_angle: str # what angle to use in the cover letter

# The researcher agent
def research_job(job_title: str, job_description: str, company_name: str) -> JobAnalysis:
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY")
    ).with_structured_output(JobAnalysis)

    prompt = f"""
    You are a career advisor helping {profile['name']} decide whether to apply for a job.
    
    Here is his profile:
    - Summary: {profile['summary']}
    - Skills: {', '.join(profile['skills'])}
    - Experience: {profile['experience_years']} years
    - Education: {profile['education'][0]}
    - Target sectors: {', '.join(profile['target_sectors'])}
    - Sectors to avoid: {', '.join(profile['avoid_sectors'])}
    - Target salary: ${profile['target_salary_usd']:,} USD/year
    - Work preference: {profile['work_preference']}
    - Location: {profile['location']}
    
    Here is the job:
    - Company: {company_name}
    - Title: {job_title}
    - Description: {job_description}
    
    Analyze the fit and decide:
    1. How well does this job match his profile? (0-100)
    2. What salary should he put on the form? Be smart about it based on company size and sector.
    3. Should he apply? Only say yes if fit_score >= 60.
    4. What angle should the cover letter take to maximize chances?
    """

    return llm.invoke(prompt)