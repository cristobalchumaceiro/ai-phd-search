---
name: phd-tracker
description: >-
  Use this skill when the user asks to set up their research profile, run the PhD tracker, check for new PhD positions, evaluate opportunities, or manage their application pipeline. Acts as both an autonomous discovery engine and a full Application Tracking System (ATS).
---

# PhD Tracker & ATS Runbook

This skill allows users to discover, evaluate, and track PhD positions across any academic discipline entirely through natural language and structured slash commands.

The AI assistant interfaces directly with the lean, local Python engine (`phd_tracker.py`) via the terminal.

---

> [!IMPORTANT]
> **Autonomous Execution & Anti-Permission Fatigue Directive:**
> 1. **Pre-Approved Execution:** Any command matching `./.venv/bin/python phd_tracker.py *` is vetted, deterministic, safe, and fully pre-approved by the user. Execute these commands autonomously and proactively without prompting the user for confirmation.
> 2. **Zero Python One-Liners:** Never write or execute ad-hoc Python one-liners (`python -c "import json; ..."`) to inspect, count, or debug the database. Always use the built-in CLI subcommands documented in the **Engine CLI Reference** below.

---

## Engine CLI Reference (`phd_tracker.py`)

The application engine provides 9 specialised subcommands. Always invoke them using `./.venv/bin/python phd_tracker.py <command>`:

1. **`scrape`**: Runs automated stealth Playwright scrapers for configured job boards (FindAPhD, jobs.ac.uk) with automated Cloudflare clearance and TLS session caching. Newly discovered opportunities are ingested with status `unreviewed`.
   ```bash
   ./.venv/bin/python phd_tracker.py scrape
   ```
2. **`extract`**: Extracts jobs of a specific status from the database into a temporary JSON file. Defaults to `.tmp/<status>.json`.
   ```bash
   ./.venv/bin/python phd_tracker.py extract --status unreviewed [--out .tmp/unreviewed.json]
   ```
3. **`apply`**: Updates the status and evaluation rationale for jobs from an evaluation JSON file, then automatically cleans up the temporary file.
   ```bash
   ./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json
   ```
4. **`update`**: Updates an individual job's ATS status, deadline, title, and/or appends a timestamped note to its audit timeline.
   ```bash
   ./.venv/bin/python phd_tracker.py update <job_id> [--status <status>] [--note "<note>"] [--deadline <YYYY-MM-DD>] [--title "<title>"]
   ```
5. **`ingest`**: Safely merges external project lists (e.g. scraped university/DLA/CDT portals) into the database with status `unreviewed` using atomic write protection.
   ```bash
   ./.venv/bin/python phd_tracker.py ingest <path_to_json>
   ```
6. **`summary`**: Displays a breakdown table of database counts grouped by status.
   ```bash
   ./.venv/bin/python phd_tracker.py summary
   ```
7. **`list`**: Lists tracked jobs in a formatted terminal view. Defaults to all active (non-rejected) jobs unless filtered. Pass `--urgent` to sort by nearest application deadline.
   ```bash
   ./.venv/bin/python phd_tracker.py list [--status <status>] [--urgent]
   ```
8. **`show`**: Displays the complete record for a job: full title, URL, status, deadline, evaluation reason, supervisors, institutions, full description, and complete timeline audit history.
   ```bash
   ./.venv/bin/python phd_tracker.py show <job_id>
   ```
9. **`clean`**: Runs data hygiene across the database, stripping enquiry modal boilerplate and auto-detecting application deadlines.
   ```bash
   ./.venv/bin/python phd_tracker.py clean
   ```

---

## The 5-Command Lifecycle

### 1. `/setup` — Research Profile Onboarding
Trigger this command whenever `user_profile.md` does not exist, or when the user says *"Set up my profile"*.

1. **Prerequisite Check:** Ensure Google Chrome is installed on the user's machine (e.g. `/Applications/Google Chrome.app` on macOS), as `phd_tracker.py scrape` launches system Chrome (`channel="chrome"`) to clear anti-bot checks. If Chrome is missing, let the user know they need Google Chrome installed (or can run `./.venv/bin/patchright install chrome`).
2. **Check `docs/` for Existing Background Material:** Check if the user has placed a CV, transcript, or research statement inside `docs/`. If present, read it first to pre-fill their academic background and avoid asking redundant questions.
3. **Do not ask the user to manually edit files.**
4. Conduct a concise conversational interview covering:
   - **Academic Background & Aspirations:** Degrees, disciplines, and career ambitions (academia, research labs, industry).
   - **Methodological Approach:** Theoretical, experimental, computational, data-driven, or qualitative.
   - **Research Themes & Exclusions:** Specific questions/topics of interest and topics strictly excluded.
   - **Hard Constraints & URLs:** Funding requirements (Home/International, stipends), geographical constraints, and target FindAPhD / jobs.ac.uk search URLs.
5. Synthesise their responses into `user_profile.md` with URLs pinned at the top:
   `**FindAPhD_URL:** <url>` and `**JobsAcUk_URL:** <url>`.

### 2. `/find` — Discovery & Ingestion
Trigger when the user wants to check for new PhD opportunities.
1. Run `./.venv/bin/python phd_tracker.py scrape`.
2. Inspect the newly scraped count and summarise newly added opportunities.

### 3. `/match` — Profile Matching
Trigger when the user wants to evaluate unreviewed opportunities against their profile.
1. Extract unreviewed positions:
   ```bash
   ./.venv/bin/python phd_tracker.py extract --status unreviewed --out .tmp/unreviewed.json
   ```
2. **Circuit Breaker:** If `.tmp/unreviewed.json` contains 0 jobs, notify the user: *"No new unreviewed positions found."*
3. Read `.tmp/unreviewed.json` and `user_profile.md`.
4. Evaluate each job against hard constraints and research fit. Categorise as:
   - `pending` (strong match with research interests and funding criteria)
   - `rejected` (fails funding, fee eligibility, or topic preferences)
   - `manual_review` (ambiguous or borderline fit)
5. Write decisions to `.tmp/evaluations.json` and apply:
   ```bash
   ./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json
   ```
6. Present a concise match digest to the user highlighting promoted positions with reasons.

### 4. `/research <job_id>` — Project & Supervisor Research
Trigger when the user requests deeper intelligence on a specific position or supervisor.
- Hand off to the dedicated `phd-researcher` skill (`.agents/skills/phd-researcher/SKILL.md`).
- Generates:
  1. Project Requirements & Jargon Breakdown (explains technical methods and notes unstated details like funding or compute access).
  2. Supervisor & Lab Background (recent publications, grants, and research direction).
  3. Recommended Reading (2–3 relevant papers) and suggested questions to ask supervisors.

### 5. `/summary` — Pipeline Overview & Deadlines
Trigger when the user wants a high-level status of their applications.
1. Run `./.venv/bin/python phd_tracker.py summary` to get exact status counts.
2. Run `./.venv/bin/python phd_tracker.py list --urgent` to list active positions sorted by closing date.
3. Render a clean Markdown Kanban pipeline:
   - **Shortlisted / Pending Review**
   - **Contacted / Informal Discussions**
   - **Applied (Awaiting Decision)**
   - **Interviewing / Offers**
4. Highlight upcoming deadlines in the next 14–30 days.
