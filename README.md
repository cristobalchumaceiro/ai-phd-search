# PhD Tracker

A tool for discovering and tracking PhD positions, inspired by [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search).

You interact with an AI assistant in chat, and the assistant runs the local Python script (`phd_tracker.py`) to scrape listings, evaluate matches, and update your application pipeline.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Chat Interface                            │
│      /setup  |  /find  |  /match  |  /research <id>  |  /summary       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Skills (.agents/)                         │
│   • phd-tracker: Profile onboarding, matching, and pipeline tracking   │
│   • phd-researcher: Project breakdown, supervisor lookup, reading lists │
│   • portal-scraper: Scraper for university and CDT project pages       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Python Engine (phd_tracker.py)                     │
│   Web scraping, description cleaner, deadline extraction, local storage│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                        jobs_database.json
```

* **The Engine (`phd_tracker.py`)**: A Python CLI that scrapes academic job boards (FindAPhD, jobs.ac.uk), strips enquiry forms and boilerplate from project descriptions, extracts application deadlines, and stores listings in a local JSON database.
* **The Skills (`.agents/skills/`)**:
  * **`phd-tracker`**: Handles profile setup, matches positions against your preferences, and manages your application pipeline.
  * **`phd-researcher`**: Researches project details, decodes technical jargon, looks up supervisor publications, and suggests preparatory reading.
  * **`portal-scraper`**: Scrapes bespoke university, CDT, or DTP project portals.

---

## Commands

| Command | Action | Description |
| :--- | :--- | :--- |
| **`/setup`** | Profile Setup | Sets up your research profile through a short chat interview (background, topics, funding, and search URLs). |
| **`/find`** | Find Positions | Scrapes new listings from configured job boards. |
| **`/match`** | Profile Matching | Evaluates unreviewed positions against your profile, categorising matches and rejections. |
| **`/research <id>`** | Project Research | Breaks down project requirements, decodes jargon, looks up supervisor publications, and suggests relevant papers to read. |
| **`/summary`** | Pipeline Summary | Shows application counts and active positions sorted by deadline. |

---

## Getting Started

### 1. Installation
Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/cristobalchumaceiro/phd-tracker.git
cd phd-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Profile Setup
Launch your AI assistant inside this directory and run `/setup` (or say *"Set up my PhD tracker profile"*).

The assistant will ask a few questions about:
* Academic background and career goals
* Research interests, methods, and excluded topics
* Funding requirements and location preferences
* Search query URLs from FindAPhD or jobs.ac.uk

Your preferences are saved locally to `user_profile.md`. Both `user_profile.md` and `jobs_database.json` are git-ignored to keep your data private.

---

## CLI Reference

The engine can also be run directly from the terminal via `./.venv/bin/python phd_tracker.py <command>`:

```bash
# 1. Scrape new jobs from configured boards
./.venv/bin/python phd_tracker.py scrape

# 2. Extract unreviewed positions for evaluation
./.venv/bin/python phd_tracker.py extract --status unreviewed --out .tmp/unreviewed.json

# 3. Apply evaluation decisions
./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json

# 4. View active applications sorted by nearest deadline
./.venv/bin/python phd_tracker.py list --urgent

# 5. Display details and timeline for a position
./.venv/bin/python phd_tracker.py show <job_id>

# 6. Update status, deadline, title, or timeline note
./.venv/bin/python phd_tracker.py update <job_id> --status applied --note "Submitted online application"

# 7. Print summary counts by status
./.venv/bin/python phd_tracker.py summary

# 8. Ingest bespoke portal scrape results
./.venv/bin/python phd_tracker.py ingest <path_to_json>

# 9. Clean database entries and auto-detect deadlines
./.venv/bin/python phd_tracker.py clean
```
