# Living Roadmap & Task Tracker: AI PhD Tracker

**Plan & Architecture Reference:** [`tasks/plan.md`](file:///Users/cristobalchumaceirorangel/Projects/phd-tracker/tasks/plan.md)  
**Last Updated:** 27 October 2026

Use this file to track progress across sessions. Mark tasks `[x]` only when implementation and verification steps pass.

---

## ✅ Completed Phases (Phases 1–4)

### Phase 1: Scraper & Data Hygiene
- [x] **Task 1.1:** DOM Boilerplate Sanitisation & Enquiry Form Stripping (`sanitise_html_text`)
- [x] **Task 1.2:** Title Cleanliness for FindAPhD Cards (`clean_job_title`)
- [x] **Task 1.3:** First-Class Deadline Regex Extraction (`parse_deadline`) & `list --urgent` Sorting
- [x] **Task 1.4:** Retroactive Database Hygiene Command (`phd_tracker.py clean`) & Dependency Pinning

### Phase 2: Dedicated Academic Research Skill
- [x] **Task 2.1:** Create `.agents/skills/phd-researcher/SKILL.md` for `/research <job_id>` (advert-grounded jargon breakdown, supervisor publication lookup, and reading recommendations)

### Phase 3: Command & Documentation Alignment
- [x] **Task 3.1:** Streamline `.agents/skills/phd-tracker/SKILL.md` around the 5-command lifecycle (`/setup`, `/find`, `/match`, `/research`, `/summary`)
- [x] **Task 3.2:** De-fluff `README.md` and skill files; add private `docs/` folder (`.gitkeep`) for user CVs/transcripts

### Phase 4: Cloudflare Turnstile Fix & E2E Smoke Test Suite
- [x] **Task 4.1:** Replace `playwright` + `playwright-stealth` with `patchright` (`channel="chrome"`) and fix Cloudflare `"Performing security verification"` transition screen race condition
- [x] **Task 4.2:** Remove silent fallback to `Google Chrome for Testing` so system Chrome launch errors surface immediately
- [x] **Task 4.3:** Add `--data-dir` CLI isolation and create `tests/e2e/new_user_playbook.md` + `tests/e2e/README.md`
- [x] **Task 4.4:** Move unit test suite to `tests/test_phd_tracker.py` (22 unit tests passing in 0.52s)

---

## ✅ Phase 5: Pipeline & Sandbox Hardening (Completed)

### Task 5.1: Migrate Scratch Directory from `.tmp/` to `tmp/`
**Description:** Eliminate macOS Seatbelt `PermissionError` on dot-prefixed directories by moving default temporary extraction/evaluation files from `.tmp/` to `tmp/`.

**Acceptance criteria:**
- [x] `phd_tracker.py extract` defaults `--out` to `tmp/<status>.json`.
- [x] `phd_tracker.py apply` cleans up `tmp/unreviewed.json` and prunes `tmp/` if empty, while still honouring explicit `--out` paths.
- [x] `.gitignore`, `README.md`, `.agents/skills/phd-tracker/SKILL.md`, `.agents/skills/portal-scraper/SKILL.md`, and `tests/e2e/new_user_playbook.md` updated from `.tmp/` to `tmp/`.

**Verification:**
- [x] Tests pass: `./.venv/bin/python -m unittest discover -s tests`
- [x] Manual check: Run `./.venv/bin/python phd_tracker.py extract --status unreviewed` inside the standard sandbox (`BypassSandbox: false`) and confirm exit code `0` with no `PermissionError`.

**Dependencies:** None  
**Files likely touched:** `phd_tracker.py`, `.gitignore`, `README.md`, `.agents/skills/phd-tracker/SKILL.md`, `.agents/skills/portal-scraper/SKILL.md`, `tests/e2e/new_user_playbook.md`  
**Estimated scope:** Medium (5–6 files)

---

### Task 5.2: Empty-Apply No-Op Guard
**Description:** Prevent redundant disk writes when `apply` receives an empty `{}` evaluation file (or when `updated_count == 0`).

**Acceptance criteria:**
- [x] `command_apply` skips `save_db(db)` when `updated_count == 0`, logs `Applied 0 evaluations to database.`, and still cleans up the input evaluation file and `tmp/unreviewed.json`.

**Verification:**
- [x] Tests pass: `./.venv/bin/python -m unittest discover -s tests` (including a new unit test verifying `save_db` is not called when `updated_count == 0`).

**Dependencies:** Task 5.1  
**Files likely touched:** `phd_tracker.py`, `tests/test_phd_tracker.py`  
**Estimated scope:** Small (2 files)

---

### Task 5.3: Standardise Match & Daily Digest Output Template in `SKILL.md`
**Description:** Add the structured Markdown output schema to `.agents/skills/phd-tracker/SKILL.md` so `/find` + `/match` runs produce a consistent, token-efficient digest (Run Metrics, 4–6 lines per Promoted Opportunity, 1 line per Active Pipeline role, zero rejected role dumps).

**Acceptance criteria:**
- [x] `.agents/skills/phd-tracker/SKILL.md` defines the exact Markdown template for both new-match runs and zero-new-match runs.
- [x] Template remains completely profile-agnostic (references `user_profile.md` generically).

**Verification:**
- [x] Manual check: Inspect `.agents/skills/phd-tracker/SKILL.md` for clarity and formatting rules.

**Dependencies:** Task 5.1  
**Files likely touched:** `.agents/skills/phd-tracker/SKILL.md`  
**Estimated scope:** Extra-Small (1 file)

### Checkpoint 5: Pipeline & Sandbox Hardening Verified
- [x] All unit tests pass in $< 1.0\text{s}$ (23 tests in 0.52s)
- [x] Standard sandbox `extract` and `apply` work on `tmp/` without elevation
- [x] Human review before starting Phase 6 (SQLite Migration)

---

## 🗄️ Phase 6: SQLite Storage Engine Migration (`jobs.db`)

### Task 6.0: Interactive Schema Design with User (Gate)
**Description:** Before writing any SQLite code, conduct a focused design discussion with the user to finalise the exact tables and columns for `jobs.db` (including `jobs`, `supervisors`, `job_supervisors`, `timeline`, and `scrape_runs`).

**Acceptance criteria:**
- [x] Full 5-table SQLite specification (`jobs`, `supervisors`, `job_supervisors`, `timeline`, `scrape_runs`) reviewed and approved by the user.
- [x] Strict CLI-only access contract agreed (agents never write raw SQL queries; all CRUD goes through `phd_tracker.py` subcommands).

**Dependencies:** Checkpoint 5

---

### Task 6.1: SQLite Schema & Database Layer
**Description:** Replace the JSON persistence helpers in `phd_tracker.py` with an embedded `sqlite3` storage layer managing `jobs.db` (scoped to `DATA_DIR`) using the approved 5-table schema from Task 6.0.

**Acceptance criteria:**
- [x] Schema creates all 5 approved tables (`jobs`, `supervisors`, `job_supervisors`, `timeline`, `scrape_runs`) with foreign keys enabled (`PRAGMA foreign_keys = ON`).
- [x] Helper functions encapsulate job upserts, supervisor profile upserts (`UNIQUE(name, institution)`), timeline inserts, and `scrape_runs` logging.

**Verification:**
- [x] Unit tests verifying schema creation and CRUD operations against a temporary SQLite database.

**Dependencies:** Task 6.0  
**Files likely touched:** `phd_tracker.py`, `tests/test_phd_tracker.py`  
**Estimated scope:** Medium (2 files)

---

### Task 6.2: One-Time Migration of `jobs_database.json` to `jobs.db`
**Description:** Run a one-off migration script to transfer all 116 existing records (folding `training`/`trajectory` into `description`, normalising `supervisors` into `supervisors` + `job_supervisors`, and preserving `timeline` arrays) from `jobs_database.json` into `jobs.db`, without leaving legacy JSON migration code inside `phd_tracker.py`.

**Acceptance criteria:**
- [x] All 116 existing records in `jobs_database.json` migrate with 100% fidelity into `jobs.db`.
- [x] All existing supervisor records (both string format on `trees_*` and dict format on `unrisk_*`) are parsed and linked in `supervisors` + `job_supervisors`.
- [x] Temporary migration helper is removed once `jobs.db` is verified.

**Verification:**
- [x] Live check verifying all 116 jobs, supervisor links, timelines, and status counts match before and after migration.

**Dependencies:** Task 6.1  
**Files likely touched:** `jobs.db`, `.gitignore`  
**Estimated scope:** Small (2 files)

---

### Task 6.3: Cut Over CLI Subcommands & Agent Skills to SQLite
**Description:** Update `scrape`, `extract`, `apply`, `update`, `ingest`, `summary`, `clean`, `list`, and `show` to read/write via SQLite queries, add CLI support for updating `research_notes` and `supervisor` profiles (so agents never write raw SQL), and document the CLI interface across `AGENTS.md` and `.agents/skills/*/SKILL.md`.

**Acceptance criteria:**
- [x] All existing CLI subcommands operate directly on `jobs.db`.
- [x] `update` supports `--research-notes`, `--institution`, `--location`, and `--reason`.
- [x] New `supervisor` and `supervisors` subcommands allow `/research <id>` to upsert supervisor academic profiles (`--name`, `--title`, `--email`, `--institution`, `--department`, `--url`, `--notes`) and link them to jobs without writing SQL.
- [x] `AGENTS.md`, `README.md`, and `.agents/skills/*/SKILL.md` updated to document the new subcommands and forbid ad-hoc SQL queries.

**Verification:**
- [x] All unit tests in `tests/test_phd_tracker.py` pass in $< 1.0\text{s}$.
- [x] `./.venv/bin/python phd_tracker.py summary` and `list --urgent` return identical counts and ordering against `jobs.db`.

**Dependencies:** Task 6.2  
**Files likely touched:** `phd_tracker.py`, `tests/test_phd_tracker.py`, `AGENTS.md`, `README.md`, `.agents/skills/phd-tracker/SKILL.md`, `.agents/skills/phd-researcher/SKILL.md`, `.agents/skills/portal-scraper/SKILL.md`  
**Estimated scope:** Medium (7 files)

### Checkpoint 6: SQLite Migration & Scope Freeze Complete
- [x] 114 existing jobs verified in `jobs.db` with 5 contacted positions
- [x] Deduplication and postings alias resolver implemented (`phd_tracker.py merge`)
- [x] `clean` deprecated (automatic title and deadline parsing on insert)
- [x] `supervisor` / `supervisors` consolidated: `list --supervisors` and `supervisor --list`
- [x] All 42 unit and E2E tests pass in < 0.9s
- [x] Feature freeze declared; prepared for `v1.0.0` release tag

---

## 🔒 Scope Freeze (Ready for v1.0.0 Tag)
Phase 7 (external badge scraping and additional portal adapters) has been frozen in accordance with user decision to lock the core architecture, prevent overengineering, and cut release tag `v1.0.0`.
