---
name: phd-tracker
description: >-
  Use this skill when the user asks to run the PhD tracker, check for new PhD jobs, evaluate ingested portal projects, or update the job database. Acts as both a job discovery tool and an Application Tracking System (ATS).
---

# PhD Tracker & ATS Runbook

This skill operates in two distinct modes depending on the user's request. Determine the user's intent and follow the appropriate workflow.

## Mode 1: Discovery & Evaluation (Finding & Matching Jobs)
Use this mode when the user says "Run the PhD tracker", "Check for new jobs", "Evaluate new jobs", or wants a daily rundown.

1. **Scrape or Ingest**:
   * For daily checks on aggregate job boards (FindAPhD / jobs.ac.uk): run `./.venv/bin/python phd_tracker.py scrape`.
   * *(Note: If projects were just imported via `portal-scraper` using `phd_tracker.py ingest`, skip scraping and proceed directly to Step 2).*
2. **Extract Unreviewed**: Extract only the new jobs into a temporary file:
   * `./.venv/bin/python phd_tracker.py extract --status unreviewed`
   * (This creates `.tmp/unreviewed.json` containing only jobs needing evaluation).
3. **Evaluate Jobs**: Read `.tmp/unreviewed.json` and `user_profile.md`. 
   * **Circuit Breaker:** If `.tmp/unreviewed.json` is empty, output "No new jobs found today." and stop.
   * For each unreviewed job, evaluate against user profile constraints (location, funding, fees) and research focus (e.g. applied ML, ecology, climate).
   * Decide status: `pending` (good match), `rejected` (poor match), or `manual_review` (ambiguous).
4. **Update Database**: Create `.tmp/evaluations.json` mapping job IDs to your decisions (e.g. `{"p123": {"status": "pending", "reason": "Matches applied ML interests"}}`). Then run:
   * `./.venv/bin/python phd_tracker.py apply .tmp/evaluations.json`
5. **Supervisor Research**: For every job moved to `pending`, invoke a `research` subagent to search for the lead supervisor's background, research interests, and publications. Run subagents concurrently via a single `invoke_subagent` call. (Fallback: "Insufficient online presence").
6. **Deliver Rundown**: Output a comprehensive rundown:
   * **Rejected Jobs:** Title, summary, 1-sentence reason.
   * **Manual Review:** Title, summary, what is ambiguous.
   * **Pending Jobs:** Title (with link), University, Project Overview, Ideal Candidate, Why it Fits, Supervisor Profile (from research subagents).

## Mode 2: ATS Tracking (Managing Existing Jobs)
Use this mode when the user wants to update a job's status, add a timeline note, shortlist a job, or view their pipeline.

**Valid ATS Statuses:** 
`pending` (Initial match), `shortlisted`, `contacted`, `applied`, `interviewing`, `offered`, `rejected_post_app`.

1. **Viewing the Pipeline (Kanban Board):** 
   If the user asks to see their tracked jobs, read `jobs_database.json` and present a Kanban-style markdown board grouping jobs by their ATS status (ignore `unreviewed` or `rejected` unless specifically asked). Display the most recent `timeline` event for each if available.
2. **Updating a Job:**
   If the user asks to move a job to a new status (e.g., "Move p123 to shortlisted and add note 'emailed supervisor'"):
   * Run: `./.venv/bin/python phd_tracker.py update <job_id> --status <status> --note "<note>"`
   * Example: `./.venv/bin/python phd_tracker.py update p123 --status shortlisted --note "Emailed Dr. Smith"`
   * Do NOT edit `jobs_database.json` directly. Always use the CLI.
3. **Adding Timeline Notes:**
   If the user just wants to add an event without changing status (e.g., "Add note to p123: Received reply"):
   * Run: `./.venv/bin/python phd_tracker.py update <job_id> --note "Received reply"`
4. **Confirmation:** Let the user know the update was successful and display the job's new status and latest timeline entry.
