# Autonomous AI PhD Tracker & ATS

An agent-first research discovery engine and Application Tracking System (ATS). It pairs a robust Python backend with AI agent skills, allowing you to discover, evaluate, and track PhD opportunities entirely through natural language—with zero graphical user interface (GUI) needed.

---

## Architecture: Core Engine + Agent Skills

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Natural Language Chat                           │
│     "Any new jobs today?" | "Import from portal" | "Show my pipeline"   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          Agent Skills (.agents)                        │
│   • phd-tracker: Conversational onboarding, evaluation, ATS pipeline   │
│   • portal-scraper: Resilient scraper for bespoke university portals   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Python Engine (phd_tracker.py)                    │
│   Automated scraping, bot-bypass, atomic database, CLI subcommands     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                       Local jobs_database.json
```

1. **The Brain (`phd_tracker.py`)**: A standalone CLI that scrapes academic job boards (FindAPhD, jobs.ac.uk), handles bot-bypass, persists opportunities atomically, and provides structured subcommands for extraction, updates, and querying.
2. **The Skills (`.agents/skills/`)**:
   * **`phd-tracker`**: Manages conversational profile onboarding, multi-criteria position matching, supervisor background research, and ATS pipeline tracking.
   * **`portal-scraper`**: Autonomously inspects, caches, micro-tests, and ingests bespoke university, doctoral training, or consortium portals into the database.

---

## Getting Started

### 1. Installation
Clone the repository and install dependencies into a local virtual environment:

```bash
git clone https://github.com/cristobalchumaceiro/phd-tracker.git
cd phd-tracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Conversational Setup
Launch your AI assistant inside this directory. Simply say:
> *"Set up my PhD tracker profile."*

The AI will guide you through a brief conversational interview to learn:
* Your educational background and post-PhD career goals.
* Your methodological approach and research style.
* Your preferred research themes, topics, and any dealbreakers/exclusions.
* Your hard constraints (funding requirements, fee status, geographic locations).

Your preferences are saved locally to `user_profile.md`. *(Both `user_profile.md` and `jobs_database.json` are git-ignored, keeping your personal details and application history 100% private).*

> **Tip on Terminal Permissions:**
> For a completely seamless, autonomous experience, allow your assistant to run `./.venv/bin/python phd_tracker.py *` commands without confirmation prompts (e.g. selecting *"Always Allow"* on first execution in your AI CLI). All engine operations are local, sandboxed to the project, and atomic.

---

## Interacting with the Tracker

You do not need to memorise CLI arguments or write scripts. Control the entire lifecycle by speaking to your assistant:

### 1. Discovery Mode (Job Boards)
* *"Check for new positions today."*
* *"Run the PhD tracker and give me a rundown of top matches."*

### 2. Custom Portal Ingestion
If you have a link to a university department, Doctoral Training Partnership (DTP), or research centre portal:
* *"Scrape and import projects from `https://www.example.ac.uk/phd-projects`."*
* *"Extract all PhD positions from this portal and evaluate them against my profile."*

### 3. Application Tracking (ATS)
* *"Show my current application pipeline."* (Renders a Kanban-style board of active positions).
* *"Show details for position p123."*
* *"Move position p123 to shortlisted and note that I attended the open day."*
* *"Update position p123 to contacted: Emailed lead supervisor Dr Smith."*
* *"Add note to p123: Received interview invitation for next Tuesday."*
