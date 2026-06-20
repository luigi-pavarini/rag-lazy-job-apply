from agents.researcher import research_job

# Test with a fake job listing
result = research_job(
    job_title="Data Scientist",
    company_name="Acme Health Tech",
    job_description="""
    We are looking for a Data Scientist to join our remote team.
    You will build predictive models for patient outcomes using Python and SQL.
    Experience with machine learning and statistical modeling required.
    MSc preferred. Salary range: $40k-$60k/year. Fully remote, open to international candidates.
    """
)

print("=== JOB ANALYSIS ===")
print(f"Fit Score: {result.fit_score}/100")
print(f"Fit Reason: {result.fit_reason}")
print(f"Sector: {result.sector}")
print(f"Salary to put: ${result.salary_to_put:,}")
print(f"Salary Reason: {result.salary_reason}")
print(f"Should Apply: {result.should_apply}")
print(f"Cover Letter Angle: {result.cover_letter_angle}")