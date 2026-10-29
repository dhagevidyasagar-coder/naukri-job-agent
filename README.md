# 🤖 Naukri Remote Job Auto-Apply & Daily Profile Refresh Agent

An automated, intelligent job-hunting agent designed to:
1. **Refresh your Naukri Profile daily** (updates resume headline & attaches resume so recruiters see you as **"Updated Today"**, boosting your profile views by 5-10x).
2. **Search for 100% Remote & Work-From-Home jobs** matching your profile (`Data Analyst`, `Python Developer`, `Data Engineer`, etc.).
3. **Automatically apply** to matching remote jobs while strictly filtering out in-office and hybrid roles.

---

## ⚡ Quick Features

| Feature | Command | Description |
| :--- | :--- | :--- |
| **Instant Profile Refresh** | `./venv/bin/python agent.py --update-profile` | Refreshes your resume headline and marks profile as **"Updated Today"** |
| **Upload New Resume** | `./venv/bin/python agent.py --update-profile --resume ./resume.pdf` | Uploads your latest resume PDF and updates headline |
| **Custom Headline** | `./venv/bin/python agent.py --update-profile --headline "Your Custom Headline"` | Sets custom headline on Naukri |
| **100% Remote Auto-Apply** | `./venv/bin/python agent.py --run` | Scans and applies to live remote jobs matching your profile |
| **Preview Remote Jobs** | `./venv/bin/python agent.py --dry-run` | Shows matching remote jobs without submitting |
| **Daily Auto-Schedule** | `./venv/bin/python agent.py --schedule-daily` | Runs daily at 09:30 AM: refreshes profile + auto-applies |

---

## ⚙️ Configuration (`config.yaml`)

Edit [**`config.yaml`**](file:///Users/dhagevidyasagar/Downloads/naukari/config.yaml) to customize your settings:

```yaml
# Target Roles (Aligned with your resume)
search:
  keywords:
    - "Data Analyst"
    - "Python Developer"
    - "Data Engineer"
    - "Business Intelligence Analyst"
  work_mode: "Remote"
  strict_remote_only: true       # 100% Remote only (rejects office/hybrid)
  experience_years: 2            # Years of experience
  max_applications_per_run: 25   # Daily application limit

# Profile Refresh Settings
profile_update:
  resume_path: ""                # (Optional) path to your PDF resume (e.g. "./resume.pdf")
  custom_headline: "Data Analyst | Python | SQL | Excel | Power BI | Pandas | NumPy | EDA | Matplotlib | Data Visualization"
  daily_schedule_time: "09:30"   # Every morning at 09:30 AM
```

---

## 📊 Application Log

Every application attempt and external link is saved with full details in:
- [**`applied_jobs.csv`**](file:///Users/dhagevidyasagar/Downloads/naukari/applied_jobs.csv)
