# New-User Onboarding E2E Playbook

This playbook simulates a brand-new user setting up `ai-phd-search` from scratch with fresh browser cookies. Run every command using `--data-dir tests/e2e/run` so the live workspace files (`user_profile.md`, `jobs.db`, and `.browser_profile`) are never modified.

---

## Step 0: Prepare Isolated Environment

Ensure `tests/e2e/run` is completely empty before starting so that `.browser_profile` has zero pre-existing Cloudflare cookies.

```bash
rm -rf tests/e2e/run
mkdir -p tests/e2e/run
```

---

## Step 1: Simulate `/setup` (Create Test Persona Profile)

**Simulated User Prompt:**
> *"I am looking for a funded PhD in the UK researching Neuromorphic Computing and Spiking Neural Networks. I have an MSc in Computer Science and want to avoid pure wet-lab neuroscience."*

Write `tests/e2e/run/user_profile.md` with a specific FindAPhD search URL that returns a focused set of results so the live smoke test completes quickly:

```markdown
# PhD Search Criteria & Academic Profile

## 1. Core Research Interests
- **Primary Themes:** Neuromorphic Computing, Spiking Neural Networks (SNNs), Event-Based Vision, Brain-Inspired Hardware.
- **Methodologies:** Algorithmic modelling, FPGA/ASIC hardware acceleration, energy-efficient edge AI.

## 2. Dealbreakers & Exclusions
- Pure wet-lab neuroscience or animal electrophysiology without a computational focus.
- Unfunded or self-funded programmes.

## 3. Target Search URLs
- **FindAPhD_URL:** https://www.findaphd.com/phds/?Keywords=spiking+neural+networks
- **JobsAcUk_URL:** Coming Soon
```

**Verification:**
- Confirm `tests/e2e/run/user_profile.md` exists and contains `**FindAPhD_URL:**`.

---

## Step 2: Simulate `/find` (Cold-Start Scrape with Fresh Cookies)

**Simulated User Prompt:**
> *"/find — check for new PhD positions."*

Execute the scraper against the isolated data directory (always run `scrape` with `BypassSandbox: true` on macOS so Seatbelt does not block Chrome's `MachPortRendezvousServer` and trigger a `SIGTRAP` crash popup):

```bash
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run scrape
```

**Pass Criteria:**
1. `.browser_profile` is created fresh inside `tests/e2e/run/.browser_profile`.
2. If Cloudflare Turnstile appears, `[AntiBot] Cloudflare challenge cleared.` is logged and pagination proceeds through all search pages until `No results found on page N`.
3. Every discovered PhD listing has its individual project URL visited (`[FindAPhD] Fetching full description for ...`).
4. Inspect `tests/e2e/run/jobs.db`:
   - At least 1 job record exists with `"status": "unreviewed"`.
   - `"needs_full_description"` is `false`.
   - `"description"` contains real project details (not `"Just a moment..."`, `"Performing security verification"`, or nationality dropdown boilerplate like `"Afghanistan (+93)"`).
   - `"title"` is clean (no `"More details"` or `"Read more"` suffixes).

---

## Step 3: Simulate `/match` (List Unreviewed & Direct Update)

**Simulated User Prompt:**
> *"/match — evaluate the unreviewed roles against my profile."*

1. Inspect unreviewed roles with full descriptions directly on stdout:
   ```bash
   ./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run list --status unreviewed --full
   ```
2. Read `tests/e2e/run/user_profile.md` and evaluate each listed role against research preferences and funding criteria.
3. Apply decisions and enrich metadata directly in the database for each role:
   ```bash
   ./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run update <job_id> --status <pending|rejected> --reason "<fit rationale>" [--institution "<institution>"] [--location "<location>"]
   ```
4. If supervisors are named in the project description, link their profiles:
   ```bash
   ./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run supervisor <job_id> --name "<name>" [--institution "<institution>"] [--title "<title>"]
   ```

**Pass Criteria:**
- Each unreviewed position is evaluated and updated via `ai_phd_search.py update`.
- Named supervisors are linked via `ai_phd_search.py supervisor` and deduplicated into relational supervisor profiles.
- Zero jobs remain in `unreviewed` status (`./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run list --status unreviewed` outputs `0 found`).

---

## Step 4: Simulate ATS Pipeline Commands (`/summary`, `/list`, `/show`, `/update`, `supervisors`)

Run the core ATS inspection and update commands to verify end-to-end state transitions:

```bash
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run summary
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run list --urgent
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run supervisors
```

Pick one `job_id` from the list and test `show` and `update`:

```bash
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run show <job_id>
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run update <job_id> --status shortlisted --deadline "2026-12-15" --note "E2E smoke test verification"
./.venv/bin/python ai_phd_search.py --data-dir tests/e2e/run list --status shortlisted --urgent
```

**Pass Criteria:**
- `summary` displays accurate counts matching the evaluated jobs and supervisor profiles.
- `list --urgent` displays host institutions, locations, and orders jobs with deadlines ahead of jobs without deadlines.
- `supervisors` lists all linked supervisor profiles and their associated jobs.
- `show <job_id>` outputs the full record, deadline, linked supervisors, timeline note, and clean description.

---

## Step 5: Teardown

Remove the temporary E2E directory once verification passes:

```bash
rm -rf tests/e2e/run
```
