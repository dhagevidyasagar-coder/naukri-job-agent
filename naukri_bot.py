"""
Naukri Job Automation Bot using Playwright
Handles persistent sessions, remote job search, and auto-applying.
"""

import os
import csv
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError

load_dotenv()
logger = logging.getLogger("NaukriBot")

class NaukriBot:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.search_cfg = config.get("search", {})
        self.filters_cfg = config.get("filters", {})
        self.questionnaire_cfg = config.get("questionnaire", {})
        self.settings = config.get("settings", {})
        
        self.user_data_dir = os.path.abspath(self.settings.get("user_data_dir", "./user_data"))
        self.headless = self.settings.get("headless", False)
        self.action_delay_ms = self.settings.get("action_delay_ms", 1500)
        self.strict_remote_only = self.search_cfg.get("strict_remote_only", True)
        self.history_file = "applied_jobs.csv"
        
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self._init_history_file()

    def _init_history_file(self):
        """Ensure applied_jobs.csv exists with header."""
        if not os.path.exists(self.history_file):
            with open(self.history_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Applied_At",
                    "Job_ID",
                    "Title",
                    "Company",
                    "Location",
                    "Status",
                    "URL",
                    "Notes"
                ])

    def get_applied_job_ids(self) -> set:
        """Read all previously applied or skipped job IDs to avoid duplicate actions."""
        applied_ids = set()
        if not os.path.exists(self.history_file):
            return applied_ids
            
        try:
            with open(self.history_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    jid = row.get("Job_ID", "").strip()
                    if jid:
                        applied_ids.add(jid)
        except Exception as e:
            logger.warning(f"Error reading history file: {e}")
        return applied_ids

    def record_job_history(self, job: Dict[str, Any], status: str, notes: str = ""):
        """Record the outcome of a job application in the CSV log."""
        try:
            with open(self.history_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    job.get("id", ""),
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    status,
                    job.get("url", ""),
                    notes
                ])
        except Exception as e:
            logger.error(f"Failed to record job history: {e}")

    def _sleep_random(self, factor: float = 1.0):
        """Randomized human-like pause to avoid bot detection."""
        base_sec = (self.action_delay_ms / 1000.0) * factor
        jitter = random.uniform(0.5, 1.5)
        time.sleep(base_sec * jitter)

    def start_browser(self, headless_override: Optional[bool] = None):
        """Launch Chromium browser using a persistent context to retain user session."""
        if self.context:
            return

        is_headless = self.headless if headless_override is None else headless_override
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        self.playwright = sync_playwright().start()
        
        # Launch persistent context
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=is_headless,
            channel="chrome" if os.path.exists("/Applications/Google Chrome.app") else None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox"
            ],
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        
        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

    def close(self):
        """Close browser context cleanly."""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")
        finally:
            self.context = None
            self.page = None
            self.playwright = None

    def interactive_login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Opens Naukri login page in a browser window.
        If email and password are provided (or found in .env), it auto-fills them.
        Monitors for successful login, CAPTCHA, or OTP challenges.
        Session is saved persistently to user_data_dir.
        """
        email = email or os.getenv("NAUKRI_EMAIL")
        password = password or os.getenv("NAUKRI_PASSWORD")

        print("\n[+] Launching browser for secure Naukri login...")
        self.start_browser(headless_override=False)
        self.page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded")
        self._sleep_random(1.5)

        # Check if already logged in
        if "mnjuser/homepage" in self.page.url or self.page.query_selector("div.nI-gNb-drawer, a.nI-gNb-header__profile-link"):
            print("\n[✓] Already logged in with active session!")
            return True

        if email and password:
            print(f"[*] Auto-filling credentials for: {email}")
            try:
                # Find username input
                user_input = self.page.wait_for_selector(
                    "input#usernameField, input[placeholder*='Username'], input[placeholder*='Email']",
                    timeout=8000
                )
                if user_input:
                    user_input.click()
                    user_input.fill("")
                    user_input.type(email, delay=random.randint(50, 100))
                    self._sleep_random(0.5)

                # Find password input
                pwd_input = self.page.wait_for_selector(
                    "input#passwordField, input[type='password']",
                    timeout=5000
                )
                if pwd_input:
                    pwd_input.click()
                    pwd_input.fill("")
                    pwd_input.type(password, delay=random.randint(50, 100))
                    self._sleep_random(0.5)

                # Find and click login button
                login_btn = self.page.query_selector("button[type='submit'], button:has-text('Login')")
                if login_btn:
                    print("[*] Submitting login form...")
                    login_btn.click()
                    self._sleep_random(2)
            except Exception as e:
                print(f"[!] Note while filling credentials: {e}")

        print("[*] Monitoring login progress...")
        print("[*] (If Naukri sends an OTP to your phone/email or shows a CAPTCHA, please complete it in the browser window)")

        start_time = time.time()
        timeout_seconds = 300  # 5 minutes for user / OTP resolution
        otp_prompted = False

        logged_in = False
        while time.time() - start_time < timeout_seconds:
            try:
                current_url = self.page.url
                if "naukri.com/mnjuser/homepage" in current_url or "naukri.com/mnjuser/profile" in current_url:
                    logged_in = True
                    break

                # Check for profile drawer or avatar
                if self.page.query_selector("div.nI-gNb-drawer, a.nI-gNb-header__profile-link, .view-profile-wrapper"):
                    logged_in = True
                    break

                # Check for OTP challenge
                otp_field = self.page.query_selector("input#otpField, input[placeholder*='OTP'], input[name*='otp'], text=Enter OTP, text=verification code")
                if otp_field and not otp_prompted:
                    print("\n[!] >> OTP / Verification detected! Please check your mobile or email and enter the OTP in the opened browser window <<\n")
                    otp_prompted = True

                # Check for invalid credentials error
                err_el = self.page.query_selector(".err-msg, .server-err")
                if err_el:
                    err_text = err_el.inner_text().strip()
                    if err_text:
                        print(f"[!] Login Notice: {err_text}")

                time.sleep(2)
            except Exception:
                time.sleep(2)

        if logged_in:
            print("\n[✓] Login successfully verified! Your session is saved in ./user_data")
            self._sleep_random(2)
            return True
        else:
            print("\n[-] Login timed out or not completed.")
            return False

    def is_logged_in(self) -> bool:
        """Check if current persistent session is authenticated."""
        if not self.page:
            self.start_browser()
            
        try:
            self.page.goto("https://www.naukri.com/mnjuser/homepage", timeout=15000, wait_until="domcontentloaded")
            self._sleep_random(1)
            
            # Check for redirect to login page
            if "nlogin/login" in self.page.url:
                return False
                
            # Check for user avatar or profile elements
            profile_el = self.page.query_selector(".nI-gNb-drawer, a.nI-gNb-header__profile-link, .user-name, .view-profile-wrapper")
            return profile_el is not None or "mnjuser/homepage" in self.page.url
        except Exception as e:
            logger.debug(f"Login check exception: {e}")
            return False

    def build_search_url(self, keyword: str, page: int = 1) -> str:
        """
        Constructs Naukri search URL with Work from Home / Remote filter.
        Naukri parameter:
        - wfhType=0 (Work from home / Remote)
        - wfhType=2 (Hybrid)
        - wfhType=0%2C2 (Remote or Hybrid)
        """
        # Convert keyword to slug
        slug = keyword.strip().replace(" ", "-").lower()
        work_mode = str(self.search_cfg.get("work_mode", "Remote")).lower()
        exp = self.search_cfg.get("experience_years", "")
        
        base_url = f"https://www.naukri.com/{slug}-jobs"
        if page > 1:
            base_url = f"https://www.naukri.com/{slug}-jobs-{page}"
            
        params = []
        if "remote" in work_mode:
            params.append("wfhType=0")  # Remote on Naukri
        elif "hybrid" in work_mode:
            params.append("wfhType=2")  # Hybrid on Naukri
        elif "any" not in work_mode:
            params.append("wfhType=0")
            
        if exp is not None and str(exp).strip():
            params.append(f"experience={exp}")
            
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url

    def _ensure_remote_filter_applied(self):
        """Click the Remote filter on Naukri if not already selected."""
        try:
            # Find the Remote filter checkbox or label in sidebar
            remote_filter = self.page.query_selector('span[title="Remote"], p:has(span[title="Remote"])')
            if remote_filter:
                # Check if it has active styling or if we need to click
                parent_p = remote_filter.query_selector("xpath=ancestor-or-self::p") or remote_filter
                class_attr = parent_p.get_attribute("class") or ""
                # Click to activate Remote filter
                logger.info("Applying 'Remote' filter on search results...")
                remote_filter.click()
                self._sleep_random(1.8)
        except Exception as e:
            logger.debug(f"Note applying remote filter: {e}")

    def search_jobs(self, keyword: str, page_num: int = 1) -> List[Dict[str, Any]]:
        """Scrape job cards from a Naukri search result page."""
        url = self.build_search_url(keyword, page_num)
        logger.info(f"Navigating to search page: {url}")
        
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self._sleep_random(1.5)
            
            # If strict remote is enabled, ensure the Remote filter checkbox is clicked on Naukri
            if self.strict_remote_only:
                self._ensure_remote_filter_applied()

            # Scroll down to load all lazy-loaded cards
            self.page.evaluate("window.scrollBy(0, 1000);")
            self._sleep_random(0.8)
            self.page.evaluate("window.scrollBy(0, 1000);")
            self._sleep_random(0.8)
        except Exception as e:
            logger.warning(f"Error loading search URL {url}: {e}")
            return []

        jobs = []
        # Modern Naukri job tuple containers
        card_selectors = [
            "div.srp-jobtuple-wrapper",
            "article.jobTuple",
            "div.cust-job-tuple"
        ]
        
        cards = []
        for sel in card_selectors:
            cards = self.page.query_selector_all(sel)
            if cards:
                break

        for card in cards:
            try:
                # Job ID
                job_id = card.get_attribute("data-job-id") or ""
                card_text = card.inner_text().strip()
                
                # Title & link
                title_el = card.query_selector("a.title, .job-title a")
                title = title_el.inner_text().strip() if title_el else ""
                job_url = title_el.get_attribute("href") if title_el else ""
                
                # If job_id not in attribute, try extracting from URL
                if not job_id and job_url:
                    parts = job_url.split("-")
                    if parts:
                        last_part = parts[-1].split("?")[0]
                        if last_part.isalnum():
                            job_id = last_part

                # Company
                comp_el = card.query_selector("a.comp-name, a.subTitle, .company-name")
                company = comp_el.inner_text().strip() if comp_el else "Unknown"

                # Experience
                exp_el = card.query_selector("span.expwdth, li.experience, span.exp-wrap")
                experience = exp_el.inner_text().strip() if exp_el else ""

                # Location
                loc_el = card.query_selector("span.locWdth, li.location, span.loc-wrap")
                location = loc_el.inner_text().strip() if loc_el else ""

                if title and job_url:
                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "experience": experience,
                        "location": location,
                        "card_text": card_text,
                        "url": job_url
                    })
            except Exception as e:
                logger.debug(f"Error parsing job card: {e}")
                continue

        return jobs

    def matches_filter(self, job: Dict[str, Any]) -> tuple[bool, str]:
        """Verify whether the job satisfies title, company, and strict remote filters."""
        title = job.get("title", "").lower()
        company = job.get("company", "").lower()
        location = job.get("location", "").lower()
        card_text = job.get("card_text", "").lower()
        
        # 1. STRICT REMOTE ONLY FILTER
        if self.strict_remote_only:
            # Explicitly reject hybrid or in-office
            if "hybrid" in location or "hybrid" in card_text:
                return False, f"Job is Hybrid, not strictly Remote (Location: '{job.get('location')}')"
            if "work from office" in location or "in office" in location:
                return False, f"Job is In-Office (Location: '{job.get('location')}')"
                
            # Must explicitly match Remote or Work From Home
            is_remote = (
                "remote" in location or 
                "work from home" in location or 
                "wfh" in location or 
                "permanent remote" in card_text or
                "remote" in title
            )
            if not is_remote:
                return False, f"Not a remote job (Location is '{job.get('location')}')"

        # 2. Check exclude title keywords
        exclude_keywords = [k.lower() for k in self.filters_cfg.get("exclude_title_keywords", [])]
        for kw in exclude_keywords:
            if kw in title:
                return False, f"Title contains excluded keyword: '{kw}'"
                
        # 3. Check excluded companies
        exclude_companies = [c.lower() for c in self.filters_cfg.get("exclude_companies", [])]
        for comp in exclude_companies:
            if comp in company:
                return False, f"Company '{company}' is blacklisted"
                
        return True, "OK"

    def apply_to_job(self, job: Dict[str, Any], dry_run: bool = False) -> Dict[str, str]:
        """
        Open job details and attempt applying.
        Returns a dict: {"status": "APPLIED"|"ALREADY_APPLIED"|"EXTERNAL"|"FAILED"|"SKIPPED", "notes": "..."}
        """
        if dry_run:
            return {"status": "DRY_RUN", "notes": "Simulated apply (dry-run mode)"}

        job_page = None
        try:
            # Open job link in a new tab
            job_page = self.context.new_page()
            job_page.goto(job["url"], timeout=30000, wait_until="domcontentloaded")
            self._sleep_random(1.2)

            # Strict remote verification on the job detail page
            if self.strict_remote_only:
                try:
                    page_text = job_page.inner_text("body").lower()
                    if "work from office" in page_text or "on-site" in page_text:
                        if "remote" not in page_text and "work from home" not in page_text:
                            return {"status": "SKIPPED_NOT_REMOTE", "notes": "Job page specifies In-Office"}
                    if "hybrid" in page_text and "remote" not in job.get("location", "").lower():
                        return {"status": "SKIPPED_NOT_REMOTE", "notes": "Job page specifies Hybrid work mode"}
                except Exception as ex:
                    logger.debug(f"Detail page text check exception: {ex}")

            # Check if already applied
            already_applied_el = job_page.query_selector(".already-applied, span:has-text('Already Applied'), div:has-text('You have already applied')")
            if already_applied_el:
                return {"status": "ALREADY_APPLIED", "notes": "Job already applied previously"}

            # Check for External apply button (e.g. "Apply on company site")
            external_button = job_page.query_selector("button:has-text('Apply on company site'), button:has-text('Company site'), a:has-text('Apply on company site')")
            if external_button:
                return {"status": "EXTERNAL", "notes": "Redirects to external company career page"}

            # Internal apply button
            apply_button = job_page.query_selector("button#apply-button, button.apply-button, button:has-text('Apply'), button:has-text('Apply on Naukri')")
            
            if not apply_button:
                # Check again if applied indicator appeared
                if job_page.query_selector("span:has-text('Applied')"):
                    return {"status": "ALREADY_APPLIED", "notes": "Already applied"}
                return {"status": "FAILED", "notes": "Apply button not found or expired"}

            # Click Apply
            apply_button.click()
            self._sleep_random(1.5)

            # Handle possible questionnaire chatbot or modal
            self._handle_application_modal(job_page)
            
            # Verify if application was confirmed
            self._sleep_random(1.0)
            success_indicators = [
                "text=successfully applied",
                "text=Application submitted",
                "text=Applied successfully",
                ".apply-message",
                "span:has-text('Already Applied')"
            ]
            
            is_success = False
            for ind in success_indicators:
                if job_page.query_selector(ind):
                    is_success = True
                    break

            if is_success or not job_page.query_selector("button#apply-button"):
                return {"status": "APPLIED", "notes": "Successfully applied via Naukri"}
            else:
                return {"status": "APPLIED_UNCONFIRMED", "notes": "Apply button clicked, please verify in Naukri portal"}

        except Exception as e:
            logger.error(f"Error applying to job {job.get('id')}: {e}")
            return {"status": "FAILED", "notes": str(e)[:100]}
        finally:
            if job_page:
                try:
                    job_page.close()
                except Exception:
                    pass

    def _handle_application_modal(self, page: Page):
        """Handle optional chatbot questionnaires (Notice period, CTC, etc.)."""
        try:
            # Check for chatbot questions container
            chatbot_frame = page.query_selector(".chatbot-container, .chatbot_drawer, div[class*='chatbot']")
            if not chatbot_frame:
                return

            # Check for common question: Notice period
            notice_period = str(self.questionnaire_cfg.get("notice_period_days", 0))
            notice_inputs = page.query_selector_all("input[placeholder*='Notice'], input[name*='notice']")
            for inp in notice_inputs:
                inp.fill(notice_period)
                page.keyboard.press("Enter")
                self._sleep_random(0.5)

            # Check for submit/save button in modal
            submit_btn = page.query_selector("button:has-text('Submit'), button:has-text('Save'), button:has-text('Apply without update')")
            if submit_btn:
                submit_btn.click()
                self._sleep_random(0.8)
        except Exception as e:
            logger.debug(f"Questionnaire handler note: {e}")

    def update_profile(self, resume_path: Optional[str] = None, custom_headline: Optional[str] = None) -> Dict[str, Any]:
        """
        Refreshes candidate profile on Naukri by:
        1. Updating the Resume Headline (triggers 'Profile last updated: Today').
        2. Uploading a new resume file (if provided).
        This elevates recruiter ranking and views significantly.
        """
        logger.info("Starting Naukri profile refresh...")
        if not self.page:
            self.start_browser()

        result = {
            "success": False,
            "headline_updated": False,
            "resume_uploaded": False,
            "message": ""
        }

        try:
            self.page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=30000)
            self._sleep_random(2)

            # Check if logged in
            if "nlogin/login" in self.page.url:
                result["message"] = "Not logged in. Please run `python agent.py --login` first."
                return result

            # 1. Resume File Upload (if file provided)
            prof_cfg = self.config.get("profile_update", {})
            resume_file = resume_path or prof_cfg.get("resume_path", "")
            
            if resume_file and os.path.isfile(resume_file):
                abs_resume = os.path.abspath(resume_file)
                logger.info(f"Uploading resume from: {abs_resume}")
                try:
                    # Find attach CV input
                    file_input = self.page.query_selector("input#attachCV, input[type='file']")
                    if file_input:
                        file_input.set_input_files(abs_resume)
                        self._sleep_random(3)
                        result["resume_uploaded"] = True
                        logger.info("Resume file successfully uploaded!")
                    else:
                        logger.warning("Resume file input (input#attachCV) not found.")
                except Exception as ex:
                    logger.error(f"Error uploading resume: {ex}")

            # 2. Update Resume Headline (Essential for 'Updated Today' recruiter badge)
            headline_to_set = custom_headline or prof_cfg.get("custom_headline", "")
            
            edit_btn = self.page.query_selector('span.edit.icon[aria-label="Edit resume headline"]')
            if not edit_btn:
                edit_btn = self.page.query_selector('.resumeHeadline .editOneTheme, .widgetHead:has-text("Resume headline") .editOneTheme')

            if edit_btn:
                logger.info("Opening Resume Headline editor...")
                edit_btn.click()
                self._sleep_random(1.2)

                textarea = self.page.query_selector("textarea#resumeHeadlineTxt, form textarea")
                if textarea:
                    current_headline = textarea.input_value().strip()
                    
                    if headline_to_set and headline_to_set.strip():
                        # If user specified headline, toggle minor punctuation if identical to trigger change
                        target_text = headline_to_set.strip()
                        if target_text == current_headline:
                            target_text = target_text[:-1] if target_text.endswith(".") else target_text + "."
                    else:
                        # Auto-toggle punctuation on existing headline
                        target_text = current_headline[:-1] if current_headline.endswith(".") else current_headline + "."

                    textarea.click()
                    textarea.fill("")
                    textarea.fill(target_text)
                    self._sleep_random(0.5)

                    save_btn = self.page.query_selector('button.btn-dark-ot:text-is("Save"), form:has(#resumeHeadlineTxt) button[type="submit"]')
                    if not save_btn:
                        save_btn = self.page.query_selector("button:text-is('Save')")
                    if save_btn:
                        save_btn.click()
                        self._sleep_random(2)
                        result["headline_updated"] = True
                        result["headline"] = target_text
                        logger.info("Resume headline updated and saved successfully!")
                else:
                    logger.warning("Resume headline textarea not found.")
            else:
                logger.warning("Resume headline edit button not found.")

            result["success"] = result["headline_updated"] or result["resume_uploaded"]
            result["message"] = "Profile refreshed successfully! Naukri now marks your profile as 'Updated Today'."
            return result

        except Exception as e:
            logger.error(f"Error during profile update: {e}")
            result["message"] = str(e)
            return result
