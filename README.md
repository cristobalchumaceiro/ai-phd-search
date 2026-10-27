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

### Prerequisites
* **Python 3.10+**
* **Google Chrome**: The scraper uses your system installation of Google Chrome (`channel="chrome"`) to pass anti-bot checks on FindAPhD. Make sure Google Chrome is installed in your standard Applications folder (or run `patchright install chrome` after installing dependencies).

### 1. Installation
Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/cristobalchumaceiro/phd-tracker.git
cd phd-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Profile Setup
*(Optional)* Drop your CV or academic transcripts into the `docs/` folder so the assistant can read your background automatically.

Launch your AI assistant inside this directory and run `/setup` (or say *"Set up my PhD tracker profile"*).

The assistant will ask a few questions about:
* Academic background and career goals
* Research interests, methods, and excluded topics
* Funding requirements and location preferences
* Search query URLs from FindAPhD or jobs.ac.uk

Your preferences are saved locally to `user_profile.md`. Everything in `docs/`, `user_profile.md`, and `jobs.db` is git-ignored to keep your data private.

---

## CLI Reference

The engine can also be run directly from the terminal via `./.venv/bin/python phd_tracker.py <command>`:

```bash
# 1. Scrape new jobs from configured boards
./.venv/bin/python phd_tracker.py scrape

# 2. Extract unreviewed positions for evaluation
./.venv/bin/python phd_tracker.py extract --status unreviewed --out tmp/unreviewed.json

# 3. Apply evaluation decisions
./.venv/bin/python phd_tracker.py apply tmp/evaluations.json

# 4. View active applications sorted by nearest deadline
./.venv/bin/python phd_tracker.py list --urgent

# 5. Display details, supervisors, and timeline for a position
./.venv/bin/python phd_tracker.py show <job_id>

# 6. Update status, deadline, title, research notes, or timeline note
./.venv/bin/python phd_tracker.py update <job_id> --status applied --note "Submitted online application"

# 7. Add or enrich a supervisor profile and link to a job
./.venv/bin/python phd_tracker.py supervisor <job_id> --name "Prof Jane Doe" --title "Professor" --institution "UCL"

# 8. List or search supervisor profiles
./.venv/bin/python phd_tracker.py supervisors --search "UCL"

# 9. Print summary counts by status and scrape history
./.venv/bin/python phd_tracker.py summary

# 10. Ingest bespoke portal scrape results
./.venv/bin/python phd_tracker.py ingest <path_to_json>

# 11. Clean database entries and auto-detect deadlines
./.venv/bin/python phd_tracker.py clean

# 12. Delete a job (cascades to timeline and links)
./.venv/bin/python phd_tracker.py delete <job_id>

# 13. Merge cross-platform duplicate jobs (combines postings, supervisors & timeline)
./.venv/bin/python phd_tracker.py merge <keep_job_id> <duplicate_job_id>
```
