---
name: portal-scraper
description: >-
  Autonomous, resilient scraper for one-off university, DLA, and CDT PhD project portals.
  Inspects arbitrary portal DOM archetypes, performs TDD micro-probing against a data contract,
  caches pages locally with polite rate-limiting, audits completeness, and safely ingests new projects into the tracker database.
---

# Autonomous Portal Scraper Runbook

Use this skill when the user provides an arbitrary university, research centre, or Doctoral Landscape Award (DLA/CDT) portal URL (such as NERC TREES DLA, London NERC DTP, Imperial DLA, Cambridge, Oxford, etc.) and asks you to scrape or import its opportunities.

---

## Non-Negotiable Safety Rules
1. **Strictly Read-Only Scraping:** Never submit web forms, login credentials, or personal information on external sites.
2. **Polite Rate-Limiting:** Always include randomised delays (1.2–2.5 seconds) between network requests to protect university servers.
3. **Local Cache First:** Download raw HTML to a system temporary cache directory (`/tmp/phd_portal_cache/`) so that all parsing, debugging, and quality checks run 100% locally from disk without re-hitting external servers.
4. **Safe Database Hand-Off:** Never edit `jobs.db` directly. Always output a structured `/tmp/portal_jobs.json` and ingest it via the safe CLI bridge.

---

## The 5-Phase Execution Pipeline

### Phase 1: Reconnaissance (DOM Archetype Detection)
Identify how the portal presents its project catalogue:
* **Drupal Views / AJAX Infinite Scroll:** Look for `ul[data-drupal-views-infinite-scroll-pager] li.pager__item a.button[rel="next"]` or "Load more" buttons.
* **Classic Query Pagination:** Check for `?page=1`, `?page=2`, `?p=2`, etc.
* **Scroll Listeners:** Monitor DOM additions upon window scrolling.
* **Single-Page Table / Accordions:** Extract all links directly if pre-rendered.

Extract all unique project links to a list and confirm the total count matches any on-page signals (e.g. *"Showing 20 of 131 projects"*).

---

### Phase 2: Micro-Probing & TDD (Self-Verification)
Before running full-scale ingestion, test your extraction logic on a sample of **2 project detail cards** against the Data Contract:

**Data Contract Requirements:**
```python
{
    "id": str,             # Unique project ID or node slug
    "title": str,          # Non-empty substantive project title (> 10 characters)
    "url": str,            # Valid absolute URL
    "description": str,    # Substantive project text (> 80 words, no boilerplate CTA)
    "supervisors": list,   # Optional: list of dicts with name, university, department, email, profile_url
    "institutions": list   # Optional: list of host and partner universities/institutions
}
```
* If extraction fails or yields empty strings (e.g. due to duplicate container classes or hidden accordions), refine your selectors locally on the cached HTML sample before scaling up.

---

### Phase 3: Resilient Batch Ingest with Local Caching
1. Save each page's raw HTML to `/tmp/phd_portal_cache/`.
2. Checkpoint each file immediately upon receipt so interrupted runs resume without re-downloading.
3. Apply polite random delays (1.2–2.5s) between requests.
4. Parse the cached HTML files into a single dictionary or array matching the Data Contract.

---

### Phase 4: QA Completeness Audit
Verify the resulting dataset before committing it to the tracker:
* **Count Check:** Total records equal expected catalogue count.
* **Zero Duplicates:** Confirm all URLs and project IDs are strictly unique.
* **Quality Gate:** Confirm 100% of projects have substantive titles and descriptions (> 50 words).

---

### Phase 5: Safe Ingestion & Hand-Off to AI PhD Search
Once verified, save the extracted projects to `/tmp/portal_jobs.json` and run the atomic ingest command:
```bash
./.venv/bin/python ai_phd_search.py ingest /tmp/portal_jobs.json
```
This safely merges the new opportunities into `jobs.db` with status `"unreviewed"` without risking database corruption.

Finally, transition to the `ai-phd-search` evaluation workflow:
Tell the user the projects have been ingested, and proceed to evaluate the new `"unreviewed"` projects against their `user_profile.md` using `./.venv/bin/python ai_phd_search.py list --status unreviewed --full` and `./.venv/bin/python ai_phd_search.py update <job_id>`.
