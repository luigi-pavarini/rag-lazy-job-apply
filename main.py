from agents.researcher import research_job
from agents.writer import write_cover_letter

# Test job listing
job_title = "Data Scientist"
company_name = "Acme Health Tech"
job_description = """
We are looking for a Data Scientist to join our remote team.
You will build predictive models for patient outcomes using Python and SQL.
Experience with machine learning and statistical modeling required.
MSc preferred. Salary range: $40k-$60k/year. Fully remote, open to international candidates.
"""

# Step 1 — researcher thinks
print("🔍 Researching job...")
analysis = research_job(job_title, job_description, company_name)

print(f"\n=== JOB ANALYSIS ===")
print(f"Fit Score: {analysis.fit_score}/100")
print(f"Sector: {analysis.sector}")
print(f"Salary to put: ${analysis.salary_to_put:,}")
print(f"Should Apply: {analysis.should_apply}")

# Step 2 — writer crafts the cover letter
if analysis.should_apply:
    print("\n✍️  Writing cover letter...")
    letter = write_cover_letter(job_title, company_name, job_description, analysis)
    
    print(f"\n=== COVER LETTER ===")
    print(f"Subject: {letter.subject}")
    print(f"\n{letter.body}")
else:
    print("\n❌ Agent decided not to apply for this job.")