# Claude Code Project Guidelines: PhD Tracker

This repository is configured for autonomous AI coding agents.

## Core Rules & Guardrails
* **Pre-Approved Execution Scope:** Any command matching `./.venv/bin/python phd_tracker.py *` (specifically: `scrape`, `extract`, `apply`, `update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) is safe, verified, and pre-approved. Execute these autonomously without prompting the user.
* **Zero Raw SQL Rule:** NEVER execute ad-hoc SQL queries (`sqlite3 jobs.db "..."` or Python scripts importing `sqlite3`). All database interactions are strictly encapsulated within `phd_tracker.py` subcommands.
* **Browser Sandbox Requirement (`scrape` only):** `phd_tracker.py scrape` launches system Google Chrome (`channel="chrome"`) to pass Cloudflare Turnstile verification.

## Agent Workflows & Skills
Detailed agent instructions and lifecycle workflows are located in `.agents/skills/`:
* **Profile Setup (`/phd-tracker setup` or *"Set up my profile"*):** Follow `.agents/skills/phd-tracker/SKILL.md` to interview the user or parse CVs in `docs/` and generate `user_profile.md`.
* **Find New Positions (`/phd-tracker find` or *"Find new positions"*):** Run `./.venv/bin/python phd_tracker.py scrape`, extract unreviewed positions, score them against `user_profile.md`, apply decisions with `./.venv/bin/python phd_tracker.py apply tmp/evaluations.json`, and present the match digest.
* **Match Positions (`/phd-tracker match` or *"Match unreviewed jobs"*):** Follow `.agents/skills/phd-tracker/SKILL.md` to evaluate any unreviewed positions against the user's preferences.
* **Academic Due Diligence (`/phd-researcher <job_id>` or *"Research project <job_id>"*):** Follow `.agents/skills/phd-researcher/SKILL.md` to break down project descriptions, search supervisor publications, suggest foundational reading lists, and record notes.
* **Pipeline Summary (`/phd-tracker summary` or *"Show my summary"*):** Run `./.venv/bin/python phd_tracker.py summary` and `./.venv/bin/python phd_tracker.py list --urgent`.
* **Portal Scraping (`/portal-scraper <url>` or *"Scrape portal"*):** Follow `.agents/skills/portal-scraper/SKILL.md` to scrape bespoke university portals and ingest them.

## Testing
Verify all changes against the comprehensive test suite:
```bash
./.venv/bin/python -m unittest discover -s tests
```
