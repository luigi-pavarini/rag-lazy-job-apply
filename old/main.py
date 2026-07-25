from agents.researcher import research_job
from agents.writer import write_cover_letter
from agents.applier import apply_to_job
import asyncio

# Test job listing
job_title = "Data Scientist"
company_name = "Acme Health Tech"
job_url = "https://wellfound.com/jobs"
job_description = """
We are looking for a Data Scientist to join our remote team.
You will build predictive models for patient outcomes using Python and SQL.
Experience with machine learning and statistical modeling required.
MSc preferred. Salary range: $40k-$60k/year. Fully remote, open to international candidates.
"""

async def run():
    # Step 1 — researcher thinks
    print("🔍 Researching job...")
    analysis = research_job(job_title, job_description, company_name)
    print(f"Fit Score: {analysis.fit_score}/100")
    print(f"Salary to put: ${analysis.salary_to_put:,}")
    print(f"Should Apply: {analysis.should_apply}")

    # Step 2 — writer crafts cover letter
    if analysis.should_apply:
        print("\n✍️  Writing cover letter...")
        letter = write_cover_letter(job_title, company_name, job_description, analysis)
        print(f"Subject: {letter.subject}")

        # Step 3 — applier opens browser
        print("\n🤖 Applying...")
        result = await apply_to_job(job_url, analysis, letter)
        print(f"\n=== APPLICATION RESULT ===")
        print(f"Status: {result.status}")
        print(f"Reason: {result.reason}")
    else:
        print("\n❌ Agent decided not to apply.")

asyncio.run(run())