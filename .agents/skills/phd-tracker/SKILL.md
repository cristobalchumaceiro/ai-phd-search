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
> 2. **Zero Python One-Liners:** Never write or execute ad-hoc Python one-liners (`python -c "import sqlite3; ..."`) to inspect, count, or debug the database. Always use the built-in CLI subcommands documented in the **Engine CLI Reference** below.
> 3. **Zero Raw SQL Rule:** Agents must **never** execute raw SQL queries (`sqlite3 jobs.db "..."`). All database operations (CRUD, supervisor profiles, timelines, deadlines) are strictly handled via `phd_tracker.py` subcommands.

---

## Engine CLI Reference (`phd_tracker.py`)

The application engine provides 12 specialised subcommands backed by SQLite (`jobs.db`). Always invoke them using `./.venv/bin/python phd_tracker.py <command>`:

1. **`scrape`**: Runs automated stealth Playwright scrapers for configured job boards (FindAPhD, jobs.ac.uk) with automated Cloudflare clearance and TLS session caching. Newly discovered opportunities are ingested with status `unreviewed`.
   ```bash
   ./.venv/bin/python phd_tracker.py scrape
   ```
2. **`extract`**: Extracts jobs of a specific status from the database into a temporary JSON file. Defaults to `tmp/<status>.json`.
   ```bash
   ./.venv/bin/python phd_tracker.py extract --status unreviewed [--out tmp/unreviewed.json]
   ```
3. **`apply`**: Updates the status and evaluation rationale for jobs from an evaluation JSON file, then automatically cleans up the temporary file.
   ```bash
   ./.venv/bin/python phd_tracker.py apply tmp/evaluations.json
   ```
4. **`update`**: Updates an individual job's ATS status, deadline, title, research notes, institution, location, and/or appends a timestamped note to its audit timeline.
   ```bash
   ./.venv/bin/python phd_tracker.py update <job_id> [--status <status>] [--note "<note>"] [--deadline <YYYY-MM-DD>] [--title "<title>"] [--research-notes "<notes>"] [--institution "<institution>"] [--location "<location>"]
   ```
5. **`supervisor`**: Creates or enriches a supervisor's academic profile (deduplicated by name and institution with honorific stripping) and links them to a specific job. Pass `--list` (or `--search`) to view supervisors.
   ```bash
   # Link supervisor to job
   ./.venv/bin/python phd_tracker.py supervisor <job_id> --name "<name>" [--title "<academic_title>"] [--institution "<institution>"] [--department "<department>"] [--email "<email>"] [--url "<profile_url>"] [--notes "<notes>"]

   # View supervisors
   ./.venv/bin/python phd_tracker.py supervisor --list [--search "<query>"]
   ```
6. **`supervisors`**: Lists or searches supervisor profiles across the database (alias for `list --supervisors`).
   ```bash
   ./.venv/bin/python phd_tracker.py supervisors [--search "<query>"]
   ```
7. **`delete`**: Deletes a job from the database (cascading to its timeline and supervisor links, while preserving reusable supervisor profiles).
   ```bash
   ./.venv/bin/python phd_tracker.py delete <job_id>
   ```
8. **`merge`**: Merges a cross-platform duplicate job into a canonical job. Combines all postings/URLs, moves supervisor links, merges timeline entries, adopts the cleaner title/institution, and retains the duplicate ID as a queryable alias in `job_postings`.
   ```bash
   ./.venv/bin/python phd_tracker.py merge <keep_job_id> <duplicate_job_id>
   ```
9. **`ingest`**: Safely merges external project lists (e.g. scraped university/DLA/CDT portals) into the database with status `unreviewed` using atomic write protection.
   ```bash
   ./.venv/bin/python phd_tracker.py ingest <path_to_json>
   ```
10. **`summary`**: Displays a breakdown table of database counts grouped by status, supervisor profiles count, and last scrape run metadata.
    ```bash
    ./.venv/bin/python phd_tracker.py summary
    ```
11. **`list`**: Lists tracked jobs in a formatted terminal view. Defaults to all active (non-rejected) jobs unless filtered. Pass `--urgent` to sort by nearest application deadline, or `--supervisors` to list supervisor profiles.
    ```bash
    ./.venv/bin/python phd_tracker.py list [--status <status>] [--urgent] [--supervisors] [--search "<query>"]
    ```
12. **`show`**: Displays the complete record for a job: full title, URL(s) and external posting links, status, deadline, evaluation reason, supervisors, institutions, research notes, full description, and complete timeline audit history.
    ```bash
    ./.venv/bin/python phd_tracker.py show <job_id>
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
   ./.venv/bin/python phd_tracker.py extract --status unreviewed --out tmp/unreviewed.json
   ```
2. **Circuit Breaker:** If `tmp/unreviewed.json` contains 0 jobs, notify the user using the **No New Positions** output template below.
3. Read `tmp/unreviewed.json` and `user_profile.md`.
4. Evaluate each job against hard constraints and research fit. Categorise as:
   - `pending` (strong match with research interests and funding criteria)
   - `rejected` (fails funding, fee eligibility, or topic preferences)
   - `manual_review` (ambiguous or borderline fit)
5. Write decisions to `tmp/evaluations.json` and apply:
   ```bash
   ./.venv/bin/python phd_tracker.py apply tmp/evaluations.json
   ```
6. Present the match digest using the **Standard Output Template** below.

---

### Standard Output Template (`/find` & `/match` Digest)

Format `/match` and combined daily `/find` + `/match` responses using this structure:

#### 1. When New Positions Are Discovered & Evaluated:
```markdown
### PhD Tracker Run: YYYY-MM-DD

#### Run Metrics
* **Total Scraped:** X listings across FindAPhD & jobs.ac.uk
* **New Ingested:** Y new entries
* **Evaluations Applied:** Z evaluated against user_profile.md

#### Promoted Opportunities
<!-- 4–6 lines per match (status: pending or manual_review) -->
* **[<job_id>] [<Job Title>](<URL>)** — <Institution>
  * **Supervisors:** <Names & Affiliated Centres/Labs>
  * **Funding & Eligibility:** <Home/International status, stipend details>
  * **Application Deadline:** <YYYY-MM-DD or Unstated>
  * **Fit Assessment:** <1–2 sentences explaining alignment with user_profile.md>
  * **Assigned Status:** `pending` | `manual_review`

#### Active Pipeline Overview
<!-- 1 line per active (non-rejected) position -->
* **[<job_id>]** [<Job Title>](<URL>) — <Supervisors> (<Institution>) | `<status>` | Deadline: <YYYY-MM-DD or Unstated>
```

#### 2. When No New Positions Are Found:
```markdown
### PhD Tracker Run: YYYY-MM-DD

#### Run Metrics
* **Total Scraped:** X listings across FindAPhD & jobs.ac.uk
* **New Ingested:** 0 (all current listings already in database)
* **Status:** All feeds are up to date. No new unreviewed opportunities.

#### Active Pipeline Overview
* **[<job_id>]** [<Job Title>](<URL>) — <Supervisors> (<Institution>) | `<status>` | Deadline: <YYYY-MM-DD or Unstated>
```

**Output Formatting Rules:**
* Keep each newly promoted opportunity to **4–6 lines** and each existing active pipeline item to **1 line**.
* Do not repeat the full `user_profile.md` text, do not print raw JSON payloads, and do not list `rejected` positions unless explicitly asked by the user.

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
