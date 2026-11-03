# AI PhD Search

A tool for discovering and tracking PhD positions, inspired by [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search).

You interact with an AI assistant in chat, and the assistant runs the local Python script (`ai_phd_search.py`) to scrape listings, evaluate matches, and update your application pipeline.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              Chat Interface                            │
│  /ai-phd-search [setup|find|match|summary]  |  /phd-researcher <id>    │
│        (or shorthand / natural language: "/find", "research project")  │
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

You can interact with your AI assistant using the skill slash commands, shorthand prompts, or natural language:

| Skill Command (`/` Autocomplete) | Shorthand / Natural Language | Description |
| :--- | :--- | :--- |
| **`/ai-phd-search setup`** | `/setup` or *"Set up my profile"* | Sets up your research profile through a short chat interview (background, topics, funding, and search URLs). |
| **`/ai-phd-search find`** | `/find` or *"Find new positions"* | Scrapes new listings from configured job boards. |
| **`/ai-phd-search match`** | `/match` or *"Match unreviewed jobs"* | Evaluates unreviewed positions against your profile, categorising matches and rejections. |
| **`/ai-phd-search summary`** | `/summary` or *"Show my summary"* | Shows application counts and active positions sorted by deadline. |
| **`/phd-researcher <id>`** | `/research <id>` or *"Research project `<id>`"* | Breaks down project requirements, decodes jargon, looks up supervisor publications, and suggests relevant papers to read. |
| **`/portal-scraper <url>`** | `/scrape-portal <url>` or *"Scrape university portal"* | Scrapes bespoke university, CDT, or DLA project catalogues and safely ingests them into the search engine. |

> **Note:** Typing `/` in your editor's chat box will autocomplete the three skills (`/ai-phd-search`, `/phd-researcher`, `/portal-scraper`), to which you pass subcommands like `setup`, `find`, `match`, or `summary`. You can also type the shorthand commands (`/find`, `/match`, etc.) or plain English directly in chat.

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

* **Universal Agent Compatibility:** The repository includes configuration files ([`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md)) that provide safe, pre-approved execution boundaries and guide your assistant through the application lifecycle.
* **Commands & Prompts:**
  * **Skills (`/` menu):** `/ai-phd-search`, `/phd-researcher`, and `/portal-scraper` are auto-discovered from `.agents/skills/`.
  * **Subcommands & Natural Language:** Pass a subcommand (`/ai-phd-search find`), use shorthand (`/find`, `/match`, `/summary`), or ask in plain English:
    * *"Set up my research profile"*
    * *"Find new PhD positions"*
    * *"Match unreviewed positions against my profile"*
    * *"Research project `<job_id>`"*
    * *"Show my application summary"*

*(Optional)*: Drop your CV or academic transcripts into the `docs/` folder beforehand so the assistant can read your background automatically during profile setup.

The assistant will help configure your preferences, funding criteria, and search queries into `user_profile.md`. Everything in `docs/`, `user_profile.md`, and `jobs.db` is git-ignored to keep your data private.

---

## Scheduled Runs & Daily Automation

Once your `user_profile.md` is configured, this tool works particularly well as a scheduled background task (for example, a daily morning digest using `/automation` in **Google Antigravity** or `/schedule` in **Claude Code**).

You can use a simple prompt like *"Run `/find` and `/match` and show me today's digest"*, or use the deterministic 4-step prompt below for unattended daily runs:

```markdown
Read `.agents/skills/ai-phd-search/SKILL.md` first, then execute the deterministic 4-step daily PhD discovery and matching pipeline:

1. Step 1 (`scrape`):
   Execute `./.venv/bin/python ai_phd_search.py scrape` (allow unsandboxed browser execution for Chrome).

2. Step 2 (`list --status unreviewed --full`):
   Execute `./.venv/bin/python ai_phd_search.py list --status unreviewed --full`.
   - Circuit Breaker: If `0 found`, skip Step 3, run `./.venv/bin/python ai_phd_search.py list --urgent`, and output the "When No New Positions Are Found" tabular template from `.agents/skills/ai-phd-search/SKILL.md`.

3. Step 3 (`update` & `supervisor` per unreviewed job):
   Read `user_profile.md` once. Evaluate each unreviewed job against `user_profile.md` and update directly via `./.venv/bin/python ai_phd_search.py update <job_id> --status <pending|rejected> --reason "<rationale>" [--deadline YYYY-MM-DD] [--institution "<inst>"] [--location "<loc>"]`.
   - Assign `pending` to all machine-accepted matches (never `shortlisted`, noting any caveats in `--reason`) and batch common rejections together (`update <id1> <id2> --status rejected --reason "..."`).
   - Link named supervisors via `./.venv/bin/python ai_phd_search.py supervisor <job_id> ...`.

4. Step 4 (`list --urgent` & Morning Digest):
   Run `./.venv/bin/python ai_phd_search.py list --urgent` and render the Morning Digest adhering strictly to the Standard Output Template and formatting rules in `.agents/skills/ai-phd-search/SKILL.md`. Follow all guidelines in `AGENTS.md` (zero raw SQL, zero temp files).
```

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
