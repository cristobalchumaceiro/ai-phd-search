---
name: ai-phd-search
description: >-
  Use this skill when the user asks to set up their research profile, run the search and tracking pipeline, check for new PhD positions, evaluate opportunities, or manage their application pipeline. Acts as both an autonomous discovery engine and a full Application Tracking System (ATS).
---

# AI PhD Search & ATS Runbook

This skill allows users to discover, evaluate, and track PhD positions across any academic discipline entirely through natural language and structured slash commands.

The AI assistant interfaces directly with the lean, local Python engine (`ai_phd_search.py`) via the terminal.

---

> [!IMPORTANT]
> **Autonomous Execution & Anti-Permission Fatigue Directive:**
> 1. **Pre-Approved Execution:** Any command matching `./.venv/bin/python ai_phd_search.py *` is vetted, deterministic, safe, and fully pre-approved by the user. Execute these commands autonomously and proactively without prompting the user for confirmation.
> 2. **Zero Python One-Liners:** Never write or execute ad-hoc Python one-liners (`python -c "import sqlite3; ..."`) to inspect, count, or debug the database. Always use the built-in CLI subcommands documented in the **Engine CLI Reference** below.
> 3. **Zero Raw SQL Rule:** Agents must **never** execute raw SQL queries (`sqlite3 jobs.db "..."`). All database operations (CRUD, supervisor profiles, timelines, deadlines) are strictly handled via `ai_phd_search.py` subcommands.
> 4. **Zero Temp-File / Zero Ad-Hoc Shell Diagnostics Rule:** Never create or use `tmp/` or `.tmp/` directories in the workspace for matching. All matching and evaluation inspects listings directly on `stdout` (`list --status unreviewed --full`) and updates SQLite directly via `update` and `supervisor`. Never retry local database CLI commands with `BypassSandbox: true`. Never run `ps`, `grep`, `kill`, or manual `/Applications/Google Chrome.app` shell commands to debug `scrape`.

---

## Engine CLI Reference (`ai_phd_search.py`)

The application engine provides 10 specialised subcommands backed by SQLite (`jobs.db`). Always invoke them using `./.venv/bin/python ai_phd_search.py <command>`:

1. **`scrape`**: Runs automated stealth Playwright scrapers for configured job boards (FindAPhD, jobs.ac.uk) with automated Cloudflare clearance, stale profile lock self-healing, and TLS session caching. Newly discovered opportunities are ingested with status `unreviewed`.
   ```bash
   ./.venv/bin/python ai_phd_search.py scrape
   ```
2. **`update`**: Updates one or more jobs atomically in SQLite (`jobs.db`) with ATS status, deadline, title, evaluation reason, research notes, host institution, location, and/or appends a timestamped note to their audit timeline. Accepts multiple `<job_id>` arguments to update batches of jobs (e.g. multiple rejections sharing a rationale) in a single transaction. Valid statuses: `unreviewed`, `pending`, `shortlisted`, `contacted`, `applied`, `interviewing`, `offer`, `rejected`.
   ```bash
   ./.venv/bin/python ai_phd_search.py update <job_id> [<job_id> ...] [--status <status>] [--reason "<reason>"] [--note "<note>"] [--deadline <YYYY-MM-DD>] [--title "<title>"] [--research-notes "<notes>"] [--institution "<institution>"] [--location "<location>"]
   ```
3. **`supervisor`**: Creates or enriches a supervisor's academic profile (deduplicated by name and institution with honorific stripping) and links them to a specific job. Pass `--list` (or `--search`) to view supervisors.
   ```bash
   # Link supervisor to job
   ./.venv/bin/python ai_phd_search.py supervisor <job_id> --name "<name>" [--title "<academic_title>"] [--institution "<institution>"] [--department "<department>"] [--email "<email>"] [--url "<profile_url>"] [--notes "<notes>"]

   # View supervisors
   ./.venv/bin/python ai_phd_search.py supervisor --list [--search "<query>"]
   ```
4. **`supervisors`**: Lists or searches supervisor profiles across the database (alias for `list --supervisors`).
   ```bash
   ./.venv/bin/python ai_phd_search.py supervisors [--search "<query>"]
   ```
5. **`delete`**: Deletes a job from the database (cascading to its timeline and supervisor links, while preserving reusable supervisor profiles).
   ```bash
   ./.venv/bin/python ai_phd_search.py delete <job_id>
   ```
6. **`merge`**: Merges a cross-platform duplicate job into a canonical job. Combines all postings/URLs, moves supervisor links, merges timeline entries, adopts the cleaner title/institution, and retains the duplicate ID as a queryable alias in `job_postings`.
   ```bash
   ./.venv/bin/python ai_phd_search.py merge <keep_job_id> <duplicate_job_id>
   ```
7. **`ingest`**: Safely merges external project lists (e.g. scraped university/DLA/CDT portals) into the database with status `unreviewed` using atomic write protection.
   ```bash
   ./.venv/bin/python ai_phd_search.py ingest <path_to_json>
   ```
8. **`summary`**: Displays a breakdown table of database counts grouped by status, supervisor profiles count, and last scrape run metadata.
   ```bash
   ./.venv/bin/python ai_phd_search.py summary
   ```
9. **`list`**: Lists tracked jobs in a formatted terminal view. Defaults to all active (non-rejected) jobs unless filtered. Pass `--status <status>` to filter, `--urgent` to sort by nearest application deadline, `--full` to include full descriptions and metadata, or `--supervisors` to list supervisor profiles.
   ```bash
   ./.venv/bin/python ai_phd_search.py list [--status <status>] [--urgent] [--full] [--supervisors] [--search "<query>"]
   ```
10. **`show`**: Displays the complete record for a job: full title, URL(s) and external posting links, status, deadline, evaluation reason, supervisors, institutions, location, research notes, full description, and complete timeline audit history.
    ```bash
    ./.venv/bin/python ai_phd_search.py show <job_id>
    ```

---

## Daily Lifecycle & Core Commands

### 1. `/setup` — Research Profile Onboarding
Trigger this command whenever `user_profile.md` does not exist, or when the user says *"Set up my profile"*.

1. **Prerequisite Check:** Ensure Google Chrome is installed on the user's machine (e.g. `/Applications/Google Chrome.app` on macOS), as `ai_phd_search.py scrape` launches system Chrome (`channel="chrome"`) to clear anti-bot checks. If Chrome is missing, let the user know they need Google Chrome installed (or can run `./.venv/bin/patchright install chrome`).
2. **Check `docs/` for Existing Background Material:** Check if the user has placed a CV, transcript, or research statement inside `docs/`. If present, read it first to pre-fill their academic background and avoid asking redundant questions.
3. **Do not ask the user to manually edit files.**
4. Conduct a concise conversational interview covering:
   - **Academic Background & Aspirations:** Degrees, disciplines, and career ambitions (academia, research labs, industry).
   - **Methodological Approach:** Theoretical, experimental, computational, data-driven, or qualitative.
   - **Research Themes & Exclusions:** Specific questions/topics of interest and topics strictly excluded.
   - **Hard Constraints & URLs:** Funding requirements (Home/International, stipends), geographical constraints, and target FindAPhD / jobs.ac.uk search URLs.
5. Synthesise their responses into `user_profile.md` with URLs pinned at the top:
   `**FindAPhD_URL:** <url>` and `**JobsAcUk_URL:** <url>`.

### 2. `/find` & `/match` — Deterministic Daily Discovery & Profile Matching
Trigger when the user wants to check for new PhD opportunities (`/find`), evaluate unreviewed listings (`/match`), or runs both together.

Follow this exact 4-step deterministic sequence:

1. **Step 1 (`scrape`):** Run `./.venv/bin/python ai_phd_search.py scrape` (`BypassSandbox: true`, `WaitMsBeforeAsync: 10000`). If backgrounded, end turn and wait for task completion notification.
2. **Step 2 (`list --status unreviewed --full`):** Run `./.venv/bin/python ai_phd_search.py list --status unreviewed --full` (`BypassSandbox: false`).
   - **Circuit Breaker:** If `0 found`, skip Step 3, run `./.venv/bin/python ai_phd_search.py list --urgent` (`BypassSandbox: false`), and output the **When No New Positions Are Found** template below.
3. **Step 3 (`update` & `supervisor` per unreviewed job):** Read `user_profile.md` once. For unreviewed jobs output in Step 2, evaluate fit against `user_profile.md`:
   - **Batching Rejections:** Batch multiple rejected positions that share a common rationale into a single command turn to minimise latency and token overhead:
     ```bash
     ./.venv/bin/python ai_phd_search.py update <job_id1> <job_id2> ... --status rejected --reason "<shared rationale>"
     ```
   - **Promoting Matches (`pending`):** Update individual accepted matches with their specific rationale and metadata:
     ```bash
     ./.venv/bin/python ai_phd_search.py update <job_id> --status pending --reason "<rationale>" [--deadline YYYY-MM-DD] [--institution "<inst>"] [--location "<loc>"]
     ```
   - **Status Rule (`pending` vs `shortlisted`):** The closed set of valid ATS statuses is `("unreviewed", "pending", "shortlisted", "contacted", "applied", "interviewing", "offer", "rejected")`. Assign `pending` to **all** machine-accepted matches (both strong and borderline fits, noting any caveats such as stipend rate or methodological balance in `--reason`). Never use `manual_review` (which is rejected by the engine), and never auto-assign `shortlisted` — `shortlisted` is reserved strictly for projects manually approved by the user.
   - Include `--deadline` (standard ASCII `YYYY-MM-DD`), `--institution`, or `--location` if stated in the description but missing from the header, and run `./.venv/bin/python ai_phd_search.py supervisor <job_id> ...` if a supervisor is named in the advert.
4. **Step 4 (`list --urgent` & Digest):** Run `./.venv/bin/python ai_phd_search.py list --urgent` (`BypassSandbox: false`) and render the **Standard Output Template** below.

> [!CAUTION]
> **What NOT To Do During /find & /match:**
> - Never execute an unprompted `ai_phd_search.py list` or `ai_phd_search.py summary` between Steps 2 and 4. All unreviewed job IDs and descriptions are already provided by Step 2 (`list --status unreviewed --full`); proceed directly to Step 3 updates and then Step 4 (`list --urgent`).
> - Never execute `ai_phd_search.py show <job_id>` for jobs already printed by `list --status unreviewed --full` or `list --urgent`. Step 2 provides full descriptions and Step 4 provides complete metadata (status, institution, location, deadline, supervisors, reason) for the pipeline summary.
> - Never create temporary JSON files or workspace directories (`tmp/`, `.tmp/`).
> - Never retry local database CLI commands with `BypassSandbox: true`.
> - Never run `ps`, `grep`, `kill`, or manual `/Applications/Google Chrome.app` shell commands to debug `scrape`.

---

### Standard Output Template (`/find` & `/match` Digest)

Format `/match` and combined daily `/find` + `/match` responses using this exact structure:

#### 1. When New Positions Are Discovered & Evaluated:
```markdown
### AI PhD Search Run — YYYY‑MM‑DD
> **Run Summary:** **X** scraped (A FindAPhD · B jobs.ac.uk) · **Y** new ingested · **M** matches · **R** rejected

#### Matches Found (M)
| Project | Institution | Supervisor(s) | Fit Summary | Deadline |
| :--- | :--- | :--- | :--- | :--- |
| [<Job Title>](<URL>) | <Concise/Abbreviated Institution> | <Names or —> | <1 concise sentence on alignment + funding/caveats> | <YYYY‑MM‑DD or —> |

#### In Progress (N)
| Project | Institution | Supervisor(s) | Status | Deadline |
| :--- | :--- | :--- | :--- | :--- |
| [<Job Title>](<URL>) | <Concise/Abbreviated Institution> | <Names or —> | <Pending\|Shortlisted\|Contacted\|Applied\|Interviewing\|Offer> | <YYYY‑MM‑DD or —> |

#### Rejected Today (R)
* [<Job Title>](<URL>) — *<Short 1-clause rejection reason>.*
```
*(If `M = 0` matches were promoted in the current run, render `#### Matches Found` followed by `*None today.*` instead of an empty table. If `R = 0` positions were rejected in the current run, omit the `#### Rejected Today` section entirely.)*

#### 2. When No New Positions Are Found (`0` Newly Ingested):
```markdown
### AI PhD Search Run — YYYY‑MM‑DD
> **Run Summary:** **X** scraped (A FindAPhD · B jobs.ac.uk) · **0** new ingested (all feeds up to date)

#### Matches Found
*None today.*

#### In Progress (N)
| Project | Institution | Supervisor(s) | Status | Deadline |
| :--- | :--- | :--- | :--- | :--- |
| [<Job Title>](<URL>) | <Concise/Abbreviated Institution> | <Names or —> | <Pending\|Shortlisted\|Contacted\|Applied\|Interviewing\|Offer> | <YYYY‑MM‑DD or —> |
```

**Strict Output Formatting Rules:**
1. **No `ID` Column in Tables:** Do not include a `Job ID` column in `Matches Found` or `In Progress`; hyperlink the `Project` title directly to `<URL>`.
2. **Single-Line `Status` & `Deadline` Cells (Prevent Overflow/Wrapping):**
   * **Never wrap `Status` or `Deadline` in `` `backtick` `` code tags** inside tables. Render `Status` as plain single-word Title Case (`Pending`, `Shortlisted`, `Contacted`, `Applied`, `Interviewing`, `Offer`).
   * **Always format rendered dates with Unicode non-breaking hyphens `‑` (`U+2011`)** instead of standard ASCII hyphens `-` (`U+002D`) — e.g. `2027‑01‑22` rather than `2027-01-22` — so browsers treat dates as single unbreakable tokens and never wrap `Deadline` onto two lines. *(Keep standard ASCII `YYYY-MM-DD` when passing `--deadline` to the CLI.)*
3. **Dynamic Column Proportions:** Abbreviate well-known institutions in table cells (`UCL`, `KCL`, `QMUL`, `UWL`, `Imperial`, etc.), use `—` for unstated supervisors or deadlines, and keep `Fit Summary` to one concise sentence so `Project` receives maximum horizontal space.
4. **Compact Rejections Footer:** Place `Rejected Today` **at the very bottom** after `In Progress` using single-line Markdown bullets (`* [<Job Title>](<URL>) — *<Short 1-clause reason>.*`). Do not use HTML `<details>` tags (to preserve CLI portability), do not include historical rejections from prior runs, and do not repeat `user_profile.md` or raw JSON payloads.
5. **Conditional Research Prompt (`Pending` Jobs Only):** Keep `phd-researcher` strictly user-triggered (do not auto-run it during `/find` or `/match`). At the very end of the digest:
   * **If ≥ 1 job in `In Progress` currently has status `Pending`:** Append a single concise line offering to run `phd-researcher` on any `Pending` project or supervisory team to help triage it into `shortlisted` or `rejected` (e.g. *Need deeper insight to triage your `Pending` projects? Ask to research any project or supervisory team.*).
   * **If 0 jobs have status `Pending`:** Omit this prompt completely so the output never nags when nothing is awaiting triage.

### 3. `/research <job_id>` — Project & Supervisor Research
Trigger when the user requests deeper intelligence on a specific position or supervisor.
- Hand off to the dedicated `phd-researcher` skill (`.agents/skills/phd-researcher/SKILL.md`).
- Generates:
  1. Project Requirements & Jargon Breakdown (explains technical methods and notes unstated details like funding or compute access).
  2. Supervisor & Lab Background (recent publications, grants, and research direction).
  3. Recommended Reading (2–3 relevant papers) and suggested questions to ask supervisors.

### 4. `/summary` — Pipeline Overview & Deadlines
Trigger when the user wants a high-level status of their applications.
1. Run `./.venv/bin/python ai_phd_search.py summary` to get exact status counts.
2. Run `./.venv/bin/python ai_phd_search.py list --urgent` to list active positions sorted by closing date.
3. Render the **`In Progress`** table (matching the 5-column formatting rules above) alongside status counts:
   - **Pending** (machine-matched, awaiting human review)
   - **Shortlisted** (human-approved)
   - **Contacted** (informal supervisor discussions)
   - **Applied / Interviewing / Offer**
4. Highlight upcoming deadlines in the next 14–30 days.
