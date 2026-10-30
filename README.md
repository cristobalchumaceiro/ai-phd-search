# AI PhD Search

A tool for discovering and tracking PhD positions, inspired by [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search).

You interact with an AI assistant in chat, and the assistant runs the local Python script (`ai_phd_search.py`) to scrape listings, evaluate matches, and update your application pipeline.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Chat Interface                            │
│    /setup  |  /find  |  /match  |  /summary  |  /research <id>         │
│        (or natural language: "find new jobs", "research project")      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Agent Skills (.agents/)                         │
│   • ai-phd-search: Profile onboarding, matching, and pipeline tracking │
│   • phd-researcher: Project breakdown, supervisor lookup, reading lists│
│   • portal-scraper: Scraper for university and CDT project pages       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Python Engine (ai_phd_search.py)                    │
│   Web scraping, description cleaner, deadline extraction, local storage│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                             jobs.db (SQLite)
```

* **The Engine (`ai_phd_search.py`)**: A Python CLI that scrapes academic job boards (FindAPhD, jobs.ac.uk), strips enquiry forms and boilerplate from project descriptions, extracts application deadlines, and stores listings in a local SQLite relational database (`jobs.db`).
* **The Skills (`.agents/skills/`)**:
  * **`ai-phd-search`**: Handles profile setup, matches positions against your preferences, and manages your application pipeline.
  * **`phd-researcher`**: Researches project details, decodes technical jargon, looks up supervisor publications, and suggests preparatory reading.
  * **`portal-scraper`**: Scrapes bespoke university, CDT, or DTP project portals.

---

## Commands

You can interact with your AI assistant using short slash commands or natural language:

| Slash Command | Action / Prompt Equivalent | Description |
| :--- | :--- | :--- |
| **`/setup`** *(alias: `/ai-phd-search setup`)* | *"Set up my profile"* | Sets up your research profile through a short chat interview (background, topics, funding, and search URLs). |
| **`/find`** *(aliases: `/search`, `/ai-phd-search find`)* | *"Find new positions"* | Scrapes new listings from configured job boards. |
| **`/match`** *(alias: `/ai-phd-search match`)* | *"Match unreviewed jobs"* | Evaluates unreviewed positions against your profile, categorising matches and rejections. |
| **`/summary`** *(alias: `/ai-phd-search summary`)* | *"Show my summary"* | Shows application counts and active positions sorted by deadline. |
| **`/research <id>`** *(alias: `/phd-researcher <id>`)* | *"Research project <id>"* | Breaks down project requirements, decodes jargon, looks up supervisor publications, and suggests relevant papers to read. |
| **`/scrape-portal <url>`** *(alias: `/portal-scraper <url>`)* | *"Scrape university portal"* | Scrapes bespoke university, CDT, or DLA project catalogues and safely ingests them into the search engine. |

---

## Getting Started

### Prerequisites
* **Python 3.10+**
* **Google Chrome**: The scraper uses your system installation of Google Chrome (`channel="chrome"`) to pass anti-bot checks on FindAPhD. Make sure Google Chrome is installed in your standard Applications folder (or run `patchright install chrome` after installing dependencies).

### 1. Installation
Clone the repository, create a virtual environment, and install dependencies:

```bash
git clone https://github.com/cristobalchumaceiro/ai-phd-search.git
cd ai-phd-search
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run with Any AI Coding Assistant
Open this repository in your AI coding assistant of choice (**Google Antigravity**, **Claude Code**, **Cursor**, **Windsurf**, or **Codex**).

* **Universal Agent Compatibility:** The repository includes configuration files ([`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md)) that provide safe, pre-approved execution boundaries and guide your assistant through the application lifecycle under the Zero Raw SQL rule.
* **Commands & Prompts:**
  * In **Google Antigravity**: Short slash commands (`/setup`, `/find`, `/match`, `/research <id>`, `/summary`) are auto-discovered from `.agents/skills/`.
  * In **Claude Code / Cursor / Codex**: You can use slash commands or natural language:
    * *"Set up my research profile"*
    * *"Find new PhD positions"*
    * *"Match unreviewed positions against my profile"*
    * *"Research project <job_id>"*
    * *"Show my application summary"*

*(Optional)*: Drop your CV or academic transcripts into the `docs/` folder beforehand so the assistant can read your background automatically during profile setup.

The assistant will help configure your preferences, funding criteria, and search queries into `user_profile.md`. Everything in `docs/`, `user_profile.md`, and `jobs.db` is git-ignored to keep your data private.

---

## CLI Reference

While users typically interact through the **Chat Commands** above, the local Python engine (`ai_phd_search.py`) can also be run directly from the terminal. It acts as both a standalone CLI and a deterministic interface for autonomous AI agents:

```bash
# 1. Scrape new jobs from configured boards
./.venv/bin/python ai_phd_search.py scrape

# 2. Inspect unreviewed positions with full descriptions (agent pipeline)
./.venv/bin/python ai_phd_search.py list --status unreviewed --full

# 3. View active applications sorted by nearest deadline
./.venv/bin/python ai_phd_search.py list --urgent

# 4. List or search academic supervisor profiles
./.venv/bin/python ai_phd_search.py list --supervisors [--search "UCL"]

# 5. Display details, multi-portal postings, supervisors, and timeline for a position
./.venv/bin/python ai_phd_search.py show <job_id>

# 6. Update status, deadline, title, research notes, institution, location, or timeline note
./.venv/bin/python ai_phd_search.py update <job_id> [<job_id> ...] --status applied --note "Submitted online application"

# 7. Add or enrich a supervisor profile and link to a job
./.venv/bin/python ai_phd_search.py supervisor <job_id> --name "Prof Jane Doe" --title "Professor" --institution "UCL"

# 8. Print summary counts by status and scrape history
./.venv/bin/python ai_phd_search.py summary

# 9. Ingest bespoke portal scrape results
./.venv/bin/python ai_phd_search.py ingest <path_to_json>

# 10. Merge cross-platform duplicate jobs (combines postings, supervisors & timeline)
./.venv/bin/python ai_phd_search.py merge <keep_job_id> <duplicate_job_id>

# 11. Delete a job (cascades to timeline and links)
./.venv/bin/python ai_phd_search.py delete <job_id>
```

---

## Contributing

Contributions of all kinds are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for local setup instructions and development guidelines.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
