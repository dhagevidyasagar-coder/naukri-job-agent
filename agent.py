#!/usr/bin/env python3
"""
Naukri Job Finder & Auto-Apply Agent
Run:
    python agent.py --login       (First-time interactive login)
    python agent.py --status      (Check if current login session is active)
    python agent.py --dry-run     (Find matching remote jobs without applying)
    python agent.py --run         (Automatically search and apply)
"""

import os
import sys
import yaml
import argparse
import logging
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from naukri_bot import NaukriBot

load_dotenv()
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
# Silence verbose playwright logs
logging.getLogger("playwright").setLevel(logging.WARNING)


def load_config(config_path: str = "config.yaml") -> dict:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        console.print(f"[bold red]Configuration file not found:[/bold red] {config_path}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error reading {config_path}:[/bold red] {e}")
        sys.exit(1)


def display_welcome_banner():
    banner = r"""[bold cyan]
  _   _             _          _     _       _       _                    _   
 | \ | | __ _ _   _| | ___ __ (_)   | | ___ | |__   / \   __ _  ___ _ __ | |_ 
 |  \| |/ _` | | | | |/ / '__|| |   | |/ _ \| '_ \ / _ \ / _` |/ _ \ '_ \| __|
 | |\  | (_| | |_| |   <| |   | |_ _| | (_) | |_) / ___ \ (_| |  __/ | | | |_ 
 |_| \_|\__,_|\__,_|_|\_\_|   |_(_(_)_|\___/|_.__//_/   \_\__, |\___|_| |_|\__|
                                                          |___/                
    [/bold cyan]
    [bold green]Naukri Remote Job Finder & Auto-Apply AI Agent[/bold green]
    """
    console.print(banner)


def run_login(bot: NaukriBot):
    email = os.getenv("NAUKRI_EMAIL", "")
    info_msg = (
        f"[bold cyan]Connecting using saved account: {email}[/bold cyan]\n\n"
        "1. A browser window will open and auto-fill your credentials.\n"
        "2. If Naukri sends an OTP to your phone or shows a captcha, complete it in the browser.\n"
        "3. Once logged in, your session is saved locally in ./user_data forever."
    ) if email else (
        "1. A browser window will open now.\n"
        "2. Log in using your Naukri Email/Password, OTP, or Google Account.\n"
        "3. Once you reach your profile/dashboard, the agent will detect it and save your session.\n"
        "4. Your credentials stay 100% private and local on your machine."
    )
    console.print(Panel(
        f"[bold yellow]{info_msg}[/bold yellow]",
        title="[bold green]Naukri Authentication & Session Setup[/bold green]"
    ))
    
    success = bot.interactive_login()
    if success:
        console.print("[bold green]✓ Session successfully saved! You can now run the bot.[/bold green]")
    else:
        console.print("[bold red]✗ Login was not completed or timed out. Please try again.[/bold red]")
    bot.close()


def run_status_check(bot: NaukriBot):
    console.print("[bold yellow]Checking login status...[/bold yellow]")
    logged_in = bot.is_logged_in()
    bot.close()
    
    if logged_in:
        console.print("[bold green]✓ You are logged in and ready to apply for jobs![/bold green]")
    else:
        console.print("[bold red]✗ Not currently logged in. Run `python agent.py --login` first.[/bold red]")


def run_pipeline(bot: NaukriBot, dry_run: bool = False):
    config = bot.config
    search_cfg = config.get("search", {})
    keywords = search_cfg.get("keywords", ["Python Developer"])
    max_apps = search_cfg.get("max_applications_per_run", 20)
    max_pages = search_cfg.get("max_pages_per_search", 2)
    work_mode = search_cfg.get("work_mode", "Remote")
    
    mode_text = "[bold yellow]DRY RUN (Preview Only)[/bold yellow]" if dry_run else "[bold green]LIVE APPLY[/bold green]"
    console.print(f"\n[bold]Starting Naukri Job Search in {mode_text} mode...[/bold]")
    console.print(f"Target Keywords: [cyan]{', '.join(keywords)}[/cyan]")
    console.print(f"Filter Work Mode: [cyan]{work_mode}[/cyan]")
    console.print(f"Strict Remote Only: [bold green]ENABLED (100% Remote / WFH Only)[/bold green]")
    console.print(f"Max Applications Limit: [cyan]{max_apps}[/cyan]\n")

    bot.start_browser()
    
    # Check login first if not in dry-run
    if not dry_run and not bot.is_logged_in():
        console.print("[bold red]✗ You are not logged in! Please run `python agent.py --login` first.[/bold red]")
        bot.close()
        return

    applied_ids = bot.get_applied_job_ids()
    total_applied = 0
    results_summary = []

    try:
        for kw in keywords:
            if total_applied >= max_apps:
                console.print(f"[bold yellow]Reached maximum application limit ({max_apps}) for this run.[/bold yellow]")
                break
                
            console.print(f"\n[bold cyan]=== Searching for: '{kw}' (Work Mode: {work_mode}) ===[/bold cyan]")
            
            for page in range(1, max_pages + 1):
                if total_applied >= max_apps:
                    break
                    
                console.print(f"Scanning page {page} for '{kw}'...")
                jobs = bot.search_jobs(kw, page_num=page)
                
                if not jobs:
                    console.print(f"[yellow]No jobs found on page {page}. Moving to next keyword.[/yellow]")
                    break
                    
                console.print(f"Found [bold]{len(jobs)}[/bold] job listings on page {page}.")
                
                for job in jobs:
                    if total_applied >= max_apps:
                        break
                        
                    jid = job.get("id")
                    title = job.get("title")
                    company = job.get("company")
                    
                    # 1. Check if already in history
                    if jid and jid in applied_ids:
                        console.print(f"  [dim]- Skipping '{title}' at {company} (Already processed in history)[/dim]")
                        continue
                        
                    # 2. Check title / company exclusions
                    matches, reason = bot.matches_filter(job)
                    if not matches:
                        console.print(f"  [yellow]- Skipping '{title}' at {company} ({reason})[/yellow]")
                        bot.record_job_history(job, status="SKIPPED_FILTER", notes=reason)
                        applied_ids.add(jid)
                        continue
                        
                    # 3. Apply or simulate apply
                    console.print(f"  [bold]» Processing:[/bold] [bold blue]{title}[/bold blue] at [bold]{company}[/bold] ({job.get('location')})")
                    outcome = bot.apply_to_job(job, dry_run=dry_run)
                    status = outcome["status"]
                    notes = outcome["notes"]
                    
                    bot.record_job_history(job, status=status, notes=notes)
                    applied_ids.add(jid)
                    
                    if status == "APPLIED":
                        console.print(f"    [bold green]✓ Applied successfully![/bold green]")
                        total_applied += 1
                    elif status == "EXTERNAL":
                        console.print(f"    [bold magenta]ℹ External application required (Company site):[/bold magenta] {job.get('url')}")
                    elif status == "ALREADY_APPLIED":
                        console.print(f"    [dim]ℹ Already applied on Naukri portal[/dim]")
                    elif status == "DRY_RUN":
                        console.print(f"    [bold cyan]✓ Matches criteria (Dry-run: ready to apply)[/bold cyan]")
                        total_applied += 1
                    else:
                        console.print(f"    [yellow]! Status: {status} - {notes}[/yellow]")
                        
                    results_summary.append({
                        "title": title,
                        "company": company,
                        "location": job.get("location"),
                        "status": status,
                        "url": job.get("url")
                    })
                    
                    bot._sleep_random(1.0)

    finally:
        bot.close()

    # Print summary table
    print_summary_table(results_summary, dry_run)


def print_summary_table(results: list, dry_run: bool):
    table = Table(title="[bold green]Job Processing Summary[/bold green]")
    table.add_column("Title", style="cyan", no_wrap=False)
    table.add_column("Company", style="white")
    table.add_column("Location", style="yellow")
    table.add_column("Status", style="bold")

    status_color_map = {
        "APPLIED": "[bold green]APPLIED[/bold green]",
        "DRY_RUN": "[bold cyan]MATCHED[/bold cyan]",
        "EXTERNAL": "[bold magenta]EXTERNAL[/bold magenta]",
        "ALREADY_APPLIED": "[dim]ALREADY APPLIED[/dim]",
        "SKIPPED_NOT_REMOTE": "[bold yellow]NOT REMOTE[/bold yellow]",
        "FAILED": "[bold red]FAILED[/bold red]"
    }

    for item in results:
        status_disp = status_color_map.get(item["status"], item["status"])
        table.add_row(item["title"][:40], item["company"][:25], item["location"][:20], status_disp)

    console.print("\n")
    console.print(table)
    console.print("\n[bold]Log saved to:[/bold] [underline]applied_jobs.csv[/underline]\n")


def run_profile_update(bot: NaukriBot, resume_path: str = None, headline: str = None):
    console.print(Panel(
        "[bold cyan]Refreshing your Naukri Profile...[/bold cyan]\n"
        "• Modifying and saving your Resume Headline to boost recruiter search ranking.\n"
        "• Uploading fresh resume file (if provided).\n"
        "• This ensures recruiters see your profile as [bold green]'Updated Today'[/bold green].",
        title="[bold green]Naukri Profile Daily Refresh[/bold green]"
    ))
    bot.start_browser()
    try:
        res = bot.update_profile(resume_path=resume_path, custom_headline=headline)
        if res.get("success"):
            console.print(f"[bold green]✓ {res.get('message')}[/bold green]")
            if res.get("headline_updated"):
                console.print(f"  [cyan]Headline:[/cyan] {res.get('headline')}")
            if res.get("resume_uploaded"):
                console.print(f"  [cyan]Resume Uploaded:[/cyan] Successfully attached new resume file.")
        else:
            console.print(f"[bold red]✗ Failed to update profile:[/bold red] {res.get('message')}")
    finally:
        bot.close()


def run_daily_scheduler(bot: NaukriBot):
    import time
    from datetime import datetime
    
    prof_cfg = bot.config.get("profile_update", {})
    sched_time = prof_cfg.get("daily_schedule_time", "09:30")
    
    console.print(Panel(
        f"[bold cyan]Daily Automation Daemon Active[/bold cyan]\n"
        f"• Target time: [bold yellow]{sched_time}[/bold yellow] every day.\n"
        "• Actions performed daily:\n"
        "   1. Refresh Resume Headline & Resume (marks profile as 'Updated Today').\n"
        "   2. Search & Auto-Apply to matching 100% Remote jobs.\n\n"
        "[dim]Press Ctrl+C to stop the daemon at any time.[/dim]",
        title="[bold green]Naukri Daily Job & Profile Automation[/bold green]"
    ))
    
    last_run_date = None
    while True:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today_date = now.strftime("%Y-%m-%d")
        
        if current_time_str == sched_time and last_run_date != today_date:
            console.print(f"\n[bold green]⏰ Triggering daily scheduled automation for {today_date}...[/bold green]")
            
            # 1. Update Profile
            try:
                run_profile_update(bot)
            except Exception as e:
                console.print(f"[bold red]Error during profile update:[/bold red] {e}")
                
            # 2. Run Job Application
            try:
                run_pipeline(bot, dry_run=False)
            except Exception as e:
                console.print(f"[bold red]Error during job applications:[/bold red] {e}")
                
            last_run_date = today_date
            console.print(f"\n[bold cyan]✓ Daily cycle complete for {today_date}. Next run tomorrow at {sched_time}.[/bold cyan]\n")
            
        time.sleep(30)


def main():
    display_welcome_banner()
    
    parser = argparse.ArgumentParser(description="Naukri Remote Job Auto-Apply & Daily Profile Refresh Agent")
    parser.add_argument("--login", action="store_true", help="Launch interactive browser to log into Naukri")
    parser.add_argument("--status", action="store_true", help="Check current login status")
    parser.add_argument("--dry-run", action="store_true", help="Find matching remote jobs without submitting applications")
    parser.add_argument("--run", action="store_true", help="Run automated remote job search and auto-apply")
    parser.add_argument("--update-profile", action="store_true", help="Refresh profile headline and attach resume to rank #1 in recruiter search")
    parser.add_argument("--resume", help="Optional path to a new resume file (PDF/DOCX) to upload")
    parser.add_argument("--headline", help="Optional custom headline to set on Naukri")
    parser.add_argument("--schedule-daily", action="store_true", help="Run in background and execute profile refresh + remote apply every morning")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    bot = NaukriBot(config)

    if args.login:
        run_login(bot)
    elif args.status:
        run_status_check(bot)
    elif args.update_profile:
        run_profile_update(bot, resume_path=args.resume, headline=args.headline)
    elif args.schedule_daily:
        run_daily_scheduler(bot)
    elif args.dry_run:
        run_pipeline(bot, dry_run=True)
    elif args.run:
        run_pipeline(bot, dry_run=False)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
