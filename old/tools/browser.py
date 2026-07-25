from playwright.async_api import async_playwright
import asyncio

async def fill_job_application(
    job_url: str,
    salary: int,
    cover_letter: str,
    profile: dict
):
    async with async_playwright() as p:
        # Launch visible browser (great for demos!)
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()

        print(f"🌐 Opening: {job_url}")
        await page.goto(job_url)
        await page.wait_for_load_state("networkidle")

        # Take a screenshot of what the agent sees
        await page.screenshot(path="screenshots/job_page.png")
        print("📸 Screenshot saved")

        # Return the page content so the applier agent can read it
        content = await page.content()
        
        await browser.close()
        return content