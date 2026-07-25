from langchain_groq import ChatGroq
from pydantic import BaseModel
from tools.browser import fill_job_application
from agents.researcher import JobAnalysis
from agents.writer import CoverLetter
from utils.profile import profile
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

class ApplicationResult(BaseModel):
    status: str        # "applied", "skipped", "error"
    reason: str        # why
    url: str           # job url

async def apply_to_job(
    job_url: str,
    analysis: JobAnalysis,
    letter: CoverLetter
) -> ApplicationResult:

    print(f"🤖 Applier agent starting...")
    
    # Open the browser and read the page
    content = await fill_job_application(
        job_url=job_url,
        salary=analysis.salary_to_put,
        cover_letter=letter.body,
        profile=profile
    )

    # Agent reads the page and decides what to do
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY")
    ).with_structured_output(ApplicationResult)

    prompt = f"""
    You are helping Luigi apply to a job.
    
    You just opened this job page: {job_url}
    
    The page content starts with:
    {content[:2000]}
    
    Based on what you see, report:
    - status: "applied" if the page has an apply form, "skipped" if login required, "error" if page didn't load
    - reason: brief explanation of what you found
    - url: {job_url}
    """

    result = llm.invoke(prompt)
    return result