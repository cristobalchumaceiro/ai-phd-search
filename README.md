# PhD Tracker

A tool for discovering and tracking PhD positions, inspired by [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search).

You interact with an AI assistant in chat, and the assistant runs the local Python script (`phd_tracker.py`) to scrape listings, evaluate matches, and update your application pipeline.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Chat Interface                            │
│    /phd-tracker [setup|find|match|summary]  |  /phd-researcher <id>    │
│        (or natural language: "find new jobs", "research project")      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Skills (.agents/)                         │
│   • phd-tracker: Profile onboarding, matching, and pipeline tracking   │
│   • phd-researcher: Project breakdown, supervisor lookup, reading lists│
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
                             jobs.db (SQLite)
```

* **The Engine (`phd_tracker.py`)**: A Python CLI that scrapes academic job boards (FindAPhD, jobs.ac.uk), strips enquiry forms and boilerplate from project descriptions, extracts application deadlines, and stores listings in a local SQLite relational database (`jobs.db`).
* **The Skills (`.agents/skills/`)**:
  * **`phd-tracker`**: Handles profile setup, matches positions against your preferences, and manages your application pipeline.
  * **`phd-researcher`**: Researches project details, decodes technical jargon, looks up supervisor publications, and suggests preparatory reading.
  * **`portal-scraper`**: Scrapes bespoke university, CDT, or DTP project portals.

---

## Commands

You can interact with your AI assistant using the registered slash commands or natural language:

| Slash Command | Action / Prompt Equivalent | Description |
| :--- | :--- | :--- |
| **`/phd-tracker setup`** | *"Set up my profile"* | Sets up your research profile through a short chat interview (background, topics, funding, and search URLs). |
| **`/phd-tracker find`** | *"Find new positions"* | Scrapes new listings from configured job boards. |
| **`/phd-tracker match`** | *"Match unreviewed jobs"* | Evaluates unreviewed positions against your profile, categorising matches and rejections. |
| **`/phd-tracker summary`** | *"Show my summary"* | Shows application counts and active positions sorted by deadline. |
| **`/phd-researcher <id>`** | *"Research project <id>"* | Breaks down project requirements, decodes jargon, looks up supervisor publications, and suggests relevant papers to read. |
| **`/portal-scraper <url>`** | *"Scrape university portal"* | Scrapes bespoke university, CDT, or DLA project catalogues and safely ingests them into the tracker. |

---

## Getting Started

### Prerequisites
* **Python 3.10+**
* **Google Chrome**: The scraper uses your system installation of Google Chrome (`channel="chrome"`) to pass anti-bot checks on FindAPhD. Make sure Google Chrome is installed in your standard Applications folder (or run `patchright install chrome` after installing dependencies).

### 1. Installation
Clone the repository, create a virtual environment, and install dependencies:

```bash
git clone https://github.com/cristobalchumaceiro/phd-tracker.git
cd phd-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run with Any AI Coding Assistant
Open this repository in your AI coding assistant of choice (**Google Antigravity**, **Claude Code**, **Cursor**, **Windsurf**, or **Codex**).

* **Universal Agent Compatibility:** The repository includes configuration files ([`AGENTS.md`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/AGENTS.md) and [`CLAUDE.md`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/CLAUDE.md)) that provide safe, pre-approved execution boundaries and guide your assistant through the application lifecycle under the Zero Raw SQL rule.
* **Commands & Prompts:**
  * In **Google Antigravity**: Native slash commands (`/setup`, `/find`, `/match`, `/research <id>`, `/summary`) are auto-discovered from `.agents/skills/`.
  * In **Claude Code / Cursor / Codex**: You can use slash commands or natural language:
    * *"Set up my PhD tracker profile"*
    * *"Find new PhD positions"*
    * *"Match unreviewed positions against my profile"*
    * *"Research project <job_id>"*
    * *"Show my application summary"*

*(Optional)*: Drop your CV or academic transcripts into the `docs/` folder beforehand so the assistant can read your background automatically during profile setup.

The assistant will help configure your preferences, funding criteria, and search queries into `user_profile.md`. Everything in `docs/`, `user_profile.md`, and `jobs.db` is git-ignored to keep your data private.

---

## CLI Reference

While users typically interact through the **Chat Commands** above, the local Python engine (`phd_tracker.py`) can also be run directly from the terminal. It acts as both a standalone CLI and a deterministic interface for autonomous AI agents:

```bash
# 1. Scrape new jobs from configured boards
./.venv/bin/python phd_tracker.py scrape

# 2. Inspect unreviewed positions with full descriptions (agent pipeline)
./.venv/bin/python phd_tracker.py list --status unreviewed --full

# 3. View active applications sorted by nearest deadline
./.venv/bin/python phd_tracker.py list --urgent

# 4. List or search academic supervisor profiles
./.venv/bin/python phd_tracker.py list --supervisors [--search "UCL"]

# 5. Display details, multi-portal postings, supervisors, and timeline for a position
./.venv/bin/python phd_tracker.py show <job_id>

# 6. Update status, deadline, title, research notes, institution, location, or timeline note
./.venv/bin/python phd_tracker.py update <job_id> [<job_id> ...] --status applied --note "Submitted online application"

# 7. Add or enrich a supervisor profile and link to a job
./.venv/bin/python phd_tracker.py supervisor <job_id> --name "Prof Jane Doe" --title "Professor" --institution "UCL"

# 8. Print summary counts by status and scrape history
./.venv/bin/python phd_tracker.py summary

# 9. Ingest bespoke portal scrape results
./.venv/bin/python phd_tracker.py ingest <path_to_json>

# 10. Merge cross-platform duplicate jobs (combines postings, supervisors & timeline)
./.venv/bin/python phd_tracker.py merge <keep_job_id> <duplicate_job_id>

# 11. Delete a job (cascades to timeline and links)
./.venv/bin/python phd_tracker.py delete <job_id>
```

---

## Contributing

Contributions of all kinds are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for local setup instructions and development guidelines.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
