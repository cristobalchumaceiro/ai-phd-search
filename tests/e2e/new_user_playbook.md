# New-User Onboarding E2E Playbook

This playbook simulates a brand-new user setting up `phd-tracker` from scratch with fresh browser cookies. Run every command using `--data-dir .tmp/e2e_run` so the live workspace files (`user_profile.md`, `jobs_database.json`, and `.browser_profile`) are never modified.

---

## Step 0: Prepare Isolated Environment

Ensure `.tmp/e2e_run` is completely empty before starting so that `.browser_profile` has zero pre-existing Cloudflare cookies.

```bash
rm -rf .tmp/e2e_run
mkdir -p .tmp/e2e_run
```

---

## Step 1: Simulate `/setup` (Create Test Persona Profile)

**Simulated User Prompt:**
> *"I am looking for a funded PhD in the UK researching Neuromorphic Computing and Spiking Neural Networks. I have an MSc in Computer Science and want to avoid pure wet-lab neuroscience."*

Write `.tmp/e2e_run/user_profile.md` with a specific FindAPhD search URL that returns a focused set of results so the live smoke test completes quickly:

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
- Confirm `.tmp/e2e_run/user_profile.md` exists and contains `**FindAPhD_URL:**`.

---

## Step 2: Simulate `/find` (Cold-Start Scrape with Fresh Cookies)

**Simulated User Prompt:**
> *"/find — check for new PhD positions."*

Execute the scraper against the isolated data directory (always run `scrape` with `BypassSandbox: true` on macOS so Seatbelt does not block Chrome's `MachPortRendezvousServer` and trigger a `SIGTRAP` crash popup):

```bash
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run scrape
```

**Pass Criteria:**
1. `.browser_profile` is created fresh inside `.tmp/e2e_run/.browser_profile`.
2. If Cloudflare Turnstile appears, `[AntiBot] Cloudflare challenge cleared.` is logged and pagination proceeds through all search pages until `No results found on page N`.
3. Every discovered PhD listing has its individual project URL visited (`[FindAPhD] Fetching full description for ...`).
4. Inspect `.tmp/e2e_run/jobs_database.json`:
   - At least 1 job record exists with `"status": "unreviewed"`.
   - `"needs_full_description"` is `false`.
   - `"description"` contains real project details (not `"Just a moment..."`, `"Performing security verification"`, or nationality dropdown boilerplate like `"Afghanistan (+93)"`).
   - `"title"` is clean (no `"More details"` or `"Read more"` suffixes).

---

## Step 3: Simulate `/match` (Extract, Evaluate, and Apply)

**Simulated User Prompt:**
> *"/match — evaluate the unreviewed roles against my profile."*

1. Extract unreviewed roles:
   ```bash
   ./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run extract --status unreviewed --out .tmp/e2e_run/unreviewed.json
   ```
2. Read `.tmp/e2e_run/unreviewed.json` and evaluate each role against `.tmp/e2e_run/user_profile.md`.
3. Write `.tmp/e2e_run/evals.json` mapping each `job_id` to `{"status": "pending" | "rejected", "reason": "..."}`.
4. Apply the evaluations:
   ```bash
   ./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run apply .tmp/e2e_run/evals.json
   ```

**Pass Criteria:**
- `Applied N evaluations to database.` is printed.
- `.tmp/e2e_run/evals.json` is automatically removed by `apply`.
- Zero jobs remain in `unreviewed` status.

---

## Step 4: Simulate ATS Pipeline Commands (`/summary`, `/list`, `/show`, `/update`)

Run the core ATS inspection and update commands to verify end-to-end state transitions:

```bash
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run summary
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run list --urgent
```

Pick one `job_id` from the list and test `show` and `update`:

```bash
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run show <job_id>
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run update <job_id> --status shortlisted --deadline "2026-12-15" --note "E2E smoke test verification"
./.venv/bin/python phd_tracker.py --data-dir .tmp/e2e_run list --status shortlisted --urgent
```

**Pass Criteria:**
- `summary` displays accurate counts matching the evaluated jobs.
- `list --urgent` orders jobs with deadlines ahead of jobs without deadlines.
- `show <job_id>` outputs the full record, deadline, timeline note, and clean description.

---

## Step 5: Teardown

Remove the temporary E2E directory once verification passes:

```bash
rm -rf .tmp/e2e_run
```
