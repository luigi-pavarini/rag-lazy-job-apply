import asyncio
from playwright.async_api import async_playwright

async def save_session():
    async with async_playwright() as p:
        # Use your real Chrome browser instead of Playwright's Chromium
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="/Users/luigipavarini/Library/Application Support/Google/Chrome",
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            args=["--profile-directory=Default"]
        )

        page = await browser.new_page()

        print("🌐 Opening Wellfound...")
        await page.goto("https://wellfound.com/login", wait_until="domcontentloaded")
        
        print("👤 Please log in manually in the browser window.")
        print("⏳ Waiting for you to finish... (you have 120 seconds)")
        
        # Wait for you to log in and land on jobs page
        await page.wait_for_url("**/jobs**", timeout=120000)
        
        # Save session
        await browser.storage_state(path="session.json")
        print("✅ Session saved to session.json!")
        
        await browser.close()

asyncio.run(save_session())