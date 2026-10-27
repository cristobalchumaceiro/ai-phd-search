# Master Implementation Plan & Roadmap: AI PhD Tracker

**Date:** 27 October 2026  
**Task List Tracker:** [`tasks/todo.md`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/tasks/todo.md)  
**Status:** Phases 1–5 Complete | Phases 6–7 Planned (Ready for Phase 6 Schema Design)

---

## 1. Vision & Architectural North Star

`phd-tracker` is a local-first PhD discovery engine, research intelligence co-pilot, and Application Tracking System (ATS) operated through AI coding assistants.

Our roadmap is organised into **7 sequential phases**:
- **Phases 1–4 (Completed):** DOM/title hygiene, deadline regex parsing, dedicated `/research` skill (`phd-researcher`), `patchright` Cloudflare Turnstile clearance, and the isolated E2E smoke-test playbook.
- **Phase 5 (Current — Pipeline & Sandbox Hardening):** Migrate `.tmp/` $\rightarrow$ `tmp/` for macOS Seatbelt compatibility, add no-op `apply` guards, and standardise the match digest template in `SKILL.md`.
- **Phase 6 (Core Upgrade — SQLite Migration):** Co-design the full relational schema with the user, run a one-time lossless migration of the 116 existing records from `jobs_database.json` to `jobs.db`, and cut `phd_tracker.py` over cleanly to SQLite (without carrying legacy JSON migration code in the script).
- **Phase 7 (Data Richness — Structured Metadata & Portal Scraping):** Extract structured sidebar badges (closing dates, funding eligibility, institution, supervisor links) directly from FindAPhD / `jobs.ac.uk` DOM elements and validate `/research <id>` and `portal-scraper` against the new SQLite schema.

---

## 2. Triage Decisions on `pipeline_improvements_spec.md`

### Slice 1: Migrate `.tmp/` to `tmp/` (macOS Seatbelt Hardening) — **ADOPTED**
- **Rationale:** macOS Seatbelt (`BypassSandbox: false`) restricts writes to dot-prefixed directories (`.tmp/`), raising `PermissionError`. Moving default scratch paths to `tmp/` (and `os.path.join(DATA_DIR, "tmp", ...)` when `--data-dir` is used) eliminates sandbox friction immediately.

### Slice 2: Early-Stop Pagination — **DROPPED**
- **Decision:** Keep full pagination across all pages as the strict rule. FindAPhD search results are not guaranteed to be strictly chronological, so early-stopping risks missing newly listed roles on later pages. *(Can be tested empirically in the future if needed.)*

### Slice 3: Empty Extraction Safeguards & `daily-check` — **SIMPLIFIED**
- **Adopted:** Update `command_apply` so that when `updated_count == 0`, it skips `save_db(db)` while still cleaning up temporary files. (`command_extract` already writes `{}` and exits `0` when 0 unreviewed jobs exist.)
- **Deferred to Phase 6:** Skip `tmp/last_scrape_date.txt` and instead track scrape history natively in the SQLite `scrape_runs` table during Phase 6.

### Slice 4: Standardised Match Digest Schema in `SKILL.md` — **ADOPTED**
- **Rationale:** Adding the structured Markdown template (Run Metrics, 4–6 line Promoted Opportunities, 1-line Active Pipeline Overview) to `.agents/skills/phd-tracker/SKILL.md` ensures consistent, scannable output across sessions.

---

## 3. SQLite Migration Strategy & Approved Schema (Phase 6)

### 3.1 Strict CLI-Only Database Contract (Zero Raw SQL by Agents)
- Agents must **never** construct raw SQL queries on the fly (`sqlite3 jobs.db "..."` or `python -c "import sqlite3..."`).
- Every read, write, upsert, and delete across all 5 tables is encapsulated inside [`phd_tracker.py`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/phd_tracker.py) subcommands (`scrape`, `extract`, `apply`, `update`, `supervisor`, `supervisors`, `ingest`, `summary`, `list`, `show`, `clean`).
- This rule is enforced in [`AGENTS.md`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/AGENTS.md) and documented in each skill (`phd-tracker`, `phd-researcher`, `portal-scraper`).

### 3.2 Approved 6-Table Relational Schema (`jobs.db`)
```sql
-- 1. Core PhD Projects & Application Status
CREATE TABLE IF NOT EXISTS jobs (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL,             -- 'findaphd' | 'jobsacuk' | 'portal:<name>'
    title                   TEXT NOT NULL,
    url                     TEXT NOT NULL,
    institution             TEXT,
    location                TEXT,
    deadline                TEXT,                      -- ISO 'YYYY-MM-DD' or NULL
    description             TEXT,                      -- Full cleaned description (includes Training/Trajectory)
    needs_full_description  INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'unreviewed',
    reason                  TEXT,                      -- Match/discard rationale from /find or /match
    research_notes          TEXT,                      -- Project-specific notes/jargon decoding from /research <id>
    created_at              TEXT NOT NULL,             -- ISO-8601
    updated_at              TEXT NOT NULL              -- ISO-8601
);

-- 2. External Postings & Multi-Platform Source Links
CREATE TABLE IF NOT EXISTS job_postings (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source                  TEXT NOT NULL,             -- 'findaphd', 'jobsacuk', 'portal:unrisk', etc.
    external_id             TEXT NOT NULL,             -- 'p199271', 'unrisk_reducing-uncertainty...'
    url                     TEXT NOT NULL,
    scraped_at              TEXT NOT NULL,
    UNIQUE(source, external_id)
);

-- 3. Academic Profiles (Reusable across multiple jobs, enriched by /research)
CREATE TABLE IF NOT EXISTS supervisors (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    academic_title          TEXT,                      -- e.g. 'Professor', 'Associate Professor', 'Lecturer'
    email                   TEXT,
    institution             TEXT,
    department              TEXT,
    profile_url             TEXT,
    research_notes          TEXT,                      -- Lab group, key publications, research interests from /research
    UNIQUE(name, institution)
);

-- 4. Many-to-Many Link Table (Jobs <-> Supervisors)
CREATE TABLE IF NOT EXISTS job_supervisors (
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    supervisor_id           INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, supervisor_id)
);

-- 5. Application & Contact Log
CREATE TABLE IF NOT EXISTS timeline (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    timestamp               TEXT NOT NULL,             -- ISO-8601
    note                    TEXT NOT NULL
);

-- 6. Scrape Run History
CREATE TABLE IF NOT EXISTS scrape_runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at                  TEXT NOT NULL,             -- ISO-8601
    source                  TEXT NOT NULL,
    search_url              TEXT NOT NULL,
    pages_scanned           INTEGER NOT NULL,
    total_found             INTEGER NOT NULL,
    new_jobs_added          INTEGER NOT NULL
);
```

### 3.3 One-Time Migration (No Legacy Bloat in `phd_tracker.py`)
- Run a one-off migration script to transfer all 116 existing records (folding `training` and `trajectory` into `description`, normalising `supervisors` into `supervisors` + `job_supervisors`, and preserving `timeline` entries) from `jobs_database.json` into `jobs.db`.
- Verify 100% data fidelity, remove the temporary migration helper, and keep `phd_tracker.py` purely SQLite-backed.

---

## 4. Dependency Graph Across Remaining Phases

```
Phase 5: Pipeline & Sandbox Hardening
  ├── Task 5.1: Migrate .tmp/ → tmp/ across CLI, .gitignore, Skills & E2E Playbook
  ├── Task 5.2: Add no-op guard in command_apply when updated_count == 0
  └── Task 5.3: Add Standardised Match Digest Template to phd-tracker/SKILL.md
        │
        ▼
  [Checkpoint 5: Sandbox & Digest Verified]
        │
        ▼
Phase 6: SQLite Storage Engine Migration
  ├── Task 6.0: Interactive Schema Design Session with User (STOP & ALIGN)
  ├── Task 6.1: Implement SQLite schema & database layer in phd_tracker.py
  ├── Task 6.2: Run one-time migration of 116 records from jobs_database.json → jobs.db
  └── Task 6.3: Cut over CLI subcommands & unit test suite to SQLite
        │
        ▼
  [Checkpoint 6: SQLite Cutover & 116-Record Migration Verified]
        │
        ▼
Phase 7: Structured DOM Metadata & Portal Expansion
  ├── Task 7.1: Extract structured metadata badges from FindAPhD/jobs.ac.uk HTML into new SQLite columns
  └── Task 7.2: End-to-end validation of /research <id> and portal-scraper with SQLite
```
