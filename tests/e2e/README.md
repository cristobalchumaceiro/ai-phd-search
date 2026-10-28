# End-to-End (E2E) New-User Smoke Tests

While `tests/test_phd_tracker.py` tests the CLI commands and HTML parsers offline using mocks (`./.venv/bin/python -m unittest discover -s tests`), external job boards (specifically FindAPhD's Cloudflare Turnstile configuration and DOM structure) change over time without notice.

This directory contains a repeatable **New-User Onboarding Playbook** (`new_user_playbook.md`) designed to be executed by an AI coding agent (or subagent) in an isolated test run directory (`--data-dir tests/e2e/run`).

## What It Verifies

1. **Zero-State Onboarding (`/setup`):** Generating a valid `user_profile.md` from scratch with a narrow, fast search query.
2. **Cold-Start Anti-Bot Clearance (`/find`):** Launching `patchright` with an empty `.browser_profile` (zero cached cookies), clearing Cloudflare Turnstile automatically, paginating through all search pages, and navigating to individual PhD project URLs to fetch full, sanitised descriptions.
3. **Evaluation & Triage (`/match`):** Inspecting `unreviewed` roles via `list --status unreviewed --full`, evaluating them against the test persona's research criteria, and committing evaluations (`pending` / `rejected`) directly via `update`.
4. **Pipeline Inspection (`/summary`, `/list`, `/show`):** Verifying status counts, deadline sorting (`--urgent`), and record formatting.

## How to Run

Ask your agent (or invoke a subagent) with:

> "Run the E2E new-user smoke test playbook in `tests/e2e/new_user_playbook.md`."

Because the playbook passes `--data-dir tests/e2e/run` to every `phd_tracker.py` invocation, your real `user_profile.md`, `jobs.db`, and `.browser_profile` cookies in the repository root remain untouched.
