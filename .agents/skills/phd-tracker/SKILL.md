---
name: phd-tracker
description: >-
  Use this skill when the user asks to set up their research profile, run the PhD tracker, check for new PhD positions, evaluate opportunities, or manage their application pipeline. Acts as both an autonomous discovery engine and a full Application Tracking System (ATS).
---

# PhD Tracker & ATS Runbook

This skill allows users to discover, evaluate, and track PhD positions across any academic discipline (humanities, social sciences, life sciences, physical sciences, engineering, or computing) entirely through natural language.

The AI assistant interfaces directly with the underlying Python engine (`phd_tracker.py`) via the terminal.

---

> [!IMPORTANT]
> **Autonomous Execution & Anti-Permission Fatigue Directive:**
> 1. **Pre-Approved Execution:** Any command matching `./.venv/bin/python phd_tracker.py *` is vetted, deterministic, safe, and fully pre-approved by the user. Execute these commands autonomously and proactively without prompting the user for confirmation.
> 2. **Zero Python One-Liners:** Never write or execute ad-hoc Python one-liners (`python -c "import json; ..."`) to inspect, count, or debug the database. Always use the built-in CLI subcommands documented in the **Engine CLI Reference** below.

---

## Engine CLI Reference (`phd_tracker.py`)

The application engine provides 8 specialised subcommands. Always invoke them using `./.venv/bin/python phd_tracker.py <command>`:

1. **`scrape`**: Runs automated Playwright scrapers for configured job boards (FindAPhD, jobs.ac.uk) and adds newly discovered opportunities to the database with status `unreviewed`.
   ```bash
   ./.venv/bin/python phd_tracker.py scrape
   ```
2. **`extract`**: Extracts jobs of a specific status from the database into an isolated JSON file (the data airlock). Defaults to `.tmp/<status>.json`.
   ```bash
   ./.venv/bin/python phd_tracker.py extract --status unreviewed [--out .tmp/unreviewed.json]
   ```
3. **`apply`**: Atomically updates the status and evaluation rationale for jobs from an evaluation JSON file, then automatically cleans up the temporary file.
   ```bash
   ./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json
   ```
4. **`update`**: Updates an individual job's ATS status and/or appends a timestamped note to its audit timeline.
   ```bash
   ./.venv/bin/python phd_tracker.py update <job_id> [--status <status>] [--note "<note>"]
   ```
5. **`ingest`**: Safely merges external project lists (e.g. scraped university/DLA/CDT portals) into the database with status `unreviewed` using atomic write protection.
   ```bash
   ./.venv/bin/python phd_tracker.py ingest <path_to_json>
   ```
6. **`summary`**: Displays a breakdown table of database counts grouped by status.
   ```bash
   ./.venv/bin/python phd_tracker.py summary
   ```
7. **`list`**: Lists tracked jobs in a formatted terminal view. Defaults to all active (non-rejected) jobs unless filtered.
   ```bash
   ./.venv/bin/python phd_tracker.py list [--status <status>]
   ```
8. **`show`**: Displays the complete record for a job: full title, URL, status, evaluation reason, supervisors, institutions, full description, training, trajectory, and complete timeline audit history.
   ```bash
   ./.venv/bin/python phd_tracker.py show <job_id>
   ```

---

## Mode 0: Profile Onboarding & Setup (Conversational Interview)
Trigger this mode automatically whenever `user_profile.md` does **not** exist in the workspace, or when the user says *"Set up my profile"*.

1. **Do not fail, and do not ask the user to manually edit files.**
2. Proactively ask the user 4 concise, discipline-agnostic interview questions:
   * **Academic Background & Aspirations:** What is your educational background, current degree, and target post-PhD career goal (e.g. academia, industry research labs, public policy, clinical practice, entrepreneurship)?
   * **Methodological Orientation:** What research style do you want to pursue? (e.g., theoretical/foundational, experimental lab work, computational/data-driven, field research, qualitative/archival studies)? Do you prefer developing novel methods/tools yourself, or applying existing frameworks to new problems?
   * **Topics, Themes & Exclusions:** What specific subjects or research questions excite you most? Are there any topics, subfields, or project types you strictly want to avoid?
   * **Hard Constraints & Search URLs:** What are your non-negotiable constraints (e.g. fully funded only, Home vs International fee status, location requirements)? Do you have specific search URLs from FindAPhD or jobs.ac.uk, or will you provide custom university portal links?
3. Synthesise their responses into a clean, structured `user_profile.md` file:
   * Place any target search URLs at the very top: `**FindAPhD_URL:** <url>` and `**JobsAcUk_URL:** <url>`.
   * Structure remaining sections clearly: Background & Career Goals, Methodological Approach, Core Research Themes, Project Exclusions, Supervisory Preferences, and Hard Constraints.

---

## Mode 1: Discovery & Evaluation (Finding & Matching Jobs)
Use this mode when the user says *"Check for new jobs"*, *"Run the PhD tracker"*, or asks for a daily rundown.

1. **Verify Profile:** Ensure `user_profile.md` exists (trigger Mode 0 first if missing).
2. **Scrape or Ingest**:
   * For daily checks on aggregate boards: run `./.venv/bin/python phd_tracker.py scrape`.
   * *(Note: If projects were just imported via `portal-scraper` using `phd_tracker.py ingest`, skip scraping and proceed directly to Step 3).*
3. **Extract Unreviewed Jobs**:
   * Run `./.venv/bin/python phd_tracker.py extract --status unreviewed --out .tmp/unreviewed.json`
4. **Evaluate Against Profile**:
   * Read `.tmp/unreviewed.json` and `user_profile.md`.
   * **Circuit Breaker:** If `.tmp/unreviewed.json` is empty, inform the user: *"No new unreviewed positions found today."* and stop.
   * Evaluate each job strictly against the user's hard constraints (funding, fee eligibility, location) and alignment with their research themes and methodology.
   * Categorise each job: `pending` (strong match), `rejected` (does not meet criteria/disliked), or `manual_review` (ambiguous).
5. **Apply Decisions to Database**:
   * Create `.tmp/evaluations.json` mapping job IDs to decisions:
     ```json
     {
       "job_id_1": {"status": "pending", "reason": "Strong match with primary research themes."},
       "job_id_2": {"status": "rejected", "reason": "Self-funded position; violates funding constraint."}
     }
     ```
   * Run `./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json`.
6. **Supervisor Research**: For each job promoted to `pending`, invoke a `research` subagent to search for the lead supervisor's publications, recent research directions, and academic group. Run subagents concurrently via `invoke_subagent`.
7. **Deliver Comprehensive Rundown**:
   * **Rejected Positions:** Title, institution, and 1-sentence rejection rationale.
   * **Manual Review Positions:** Title, institution, and specific ambiguity needing user input.
   * **Pending (Shortlisted) Positions:** Title (clickable markdown link), Institution, Research Overview, Alignment with Profile, and Supervisor Profile.

---

## Mode 2: ATS Tracking (Pipeline Management)
Use this mode when the user wants to manage their active applications, view their pipeline, or record updates.

**Valid ATS Statuses:**
`pending` (Initial match), `shortlisted`, `contacted`, `applied`, `interviewing`, `offered`, `rejected_post_app`.

1. **Viewing the Pipeline (Kanban Board):**
   * Run `./.venv/bin/python phd_tracker.py list` to inspect active positions.
   * Present a clear Kanban-style markdown board grouping jobs by ATS status. Include job title, institution, link, match reason, and latest timeline note.
2. **Inspecting a Specific Job:**
   * Run `./.venv/bin/python phd_tracker.py show <job_id>` to display full project details, description, supervisors, and timeline history.
3. **Updating Job Status:**
   * Run `./.venv/bin/python phd_tracker.py update <job_id> --status <new_status> --note "<optional_note>"`.
   * Example: `./.venv/bin/python phd_tracker.py update p123 --status contacted --note "Emailed lead supervisor Dr Smith"`.
4. **Adding Timeline Notes:**
   * Run `./.venv/bin/python phd_tracker.py update <job_id> --note "<note>"`.
   * Example: `./.venv/bin/python phd_tracker.py update p123 --note "Attended virtual department open day"`.
5. **Confirmation:** Report the change to the user with the updated status and timeline snippet.
