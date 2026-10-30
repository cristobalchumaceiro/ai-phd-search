---
name: phd-researcher
description: >-
  Use this skill when the user wants to research a PhD vacancy, decode dense academic jargon, conduct due diligence on supervisors and lab groups, or prepare technical reading for interviews. Triggered via /research <job_id> or natural language queries.
---

# Academic Research Runbook

This skill researches specific PhD opportunities, helping users understand project details, technical jargon, supervisor publications, and recommended reading for interviews.

---

## Workflow: 4-Step Research Process

When the user requests research on a position (e.g. `/research <job_id>` or "research this supervisor/project"):

### Step 1: Ingest Ground Truth Record
Retrieve the project record directly from the local database:
```bash
./.venv/bin/python ai_phd_search.py show <job_id>
```
Extract:
- Official Project Title & Host Institution(s)
- Listed Primary / Secondary Supervisors
- Stated Application Deadline
- Full Scraped Description & Funding Notes

### Step 2: Advert Deconstruction & Jargon Demystification
Academic adverts are often dense with specialised terminology, domain acronyms, and funding subtleties. Provide a grounded breakdown:
1. **Core Problem Formulation:** In plain, precise scientific terms, what fundamental open problem or gap is this PhD tackling?
2. **Technical Methodology & Jargon Breakdown:** Demystify the specific mathematical tools, computational frameworks, wet-lab protocols, or theoretical paradigms mentioned in the advert (e.g. PINNs, surrogate emulation, single-cell RNA-seq, in silico screening).
3. **Advert Audit (Stated vs Unstated):**
   - *Explicitly Stated:* Funding status (Home vs International), stipend coverage, bench fees, cohort structure.
   - *Omitted / Ambiguous:* What is *not* mentioned in the advert? (e.g. specific compute cluster access, supervisory split across institutions, publication expectations).

### Step 3: Supervisor & Lab Intelligence Dossier
Investigate the named supervisors and their research group using web research tools (arXiv, Google Scholar, institutional lab pages):
1. **Supervisor Profile:** Academic title, department, primary research trajectory, and lab leadership roles.
2. **Recent Output (2024–2026):** Identify 2–3 recent preprints or peer-reviewed papers that reflect their current methodological focus.
3. **Active Grants & Collaborations:** Major UKRI/EPSRC/ERC grants, CDT/DLA affiliations, or clinical/industrial partnerships relevant to this project.
4. **Lab Culture & Direction:** Emerging directions of the lab and how this PhD project fits into their broader research agenda.

### Step 4: Interview Readiness & Preparatory Reading
Equip the candidate to engage in a high-level peer dialogue:
1. **Essential Preparatory Reading:** Recommend 2–3 foundational papers, review articles, or seminal codebases that will bring the candidate up to speed with the project's technical frontier.
2. **Perceptive Interview Questions:** Formulate 2–3 sharp, intellectually substantive questions for the candidate to ask the supervisor during an informal chat or interview (e.g. inquiring about specific methodological trade-offs or upcoming data collection phases).

---

## Standard Output Format

Present the findings in a structured Markdown report:

```markdown
# Academic Intelligence Dossier: [Project Title]
**Job ID:** `<job_id>` | **Host Institution:** [University] | **Deadline:** [YYYY-MM-DD or Not Stated]
**Supervisors:** [Names and Departments]

---

### 1. Advert Deconstruction & Technical Demystification
- **The Core Scientific Problem:** [Grounded summary of the research challenge]
- **Key Methodologies & Terms Decoded:**
  - `[Technical Term / Tool]`: [Clear scientific definition and context within the project]
  - `[Technical Term / Tool]`: [Clear scientific definition and context within the project]
- **Gaps & Omissions:** [Explicitly note what the advert does not disclose, e.g. international fee coverage, compute hardware]

### 2. Supervisor & Lab Intelligence Dossier
- **Primary Supervisor:** [Name, Department, Laboratory Group]
- **Current Research Trajectory (2024–2026):** [Summary of active interests]
- **Recent Landmark Publications:**
  - *[Title]* ([Year]) — [One-line summary of finding/relevance]
  - *[Title]* ([Year]) — [One-line summary of finding/relevance]
- **Active Affiliations & Grants:** [CDTs, UKRI/ERC programmes, industrial partners]

### 3. Preparatory Reading & Interview Readiness
- **Foundational Literature:**
  1. *[Key Paper / Survey]*: [Why the candidate should read this before an interview]
  2. *[Key Paper / Survey]*: [Why the candidate should read this before an interview]
- **Substantive Candidate Questions for Supervisors:**
  - *Question 1:* [Intellectually sharp question addressing methodological choice or project trajectory]
  - *Question 2:* [Question addressing data access, validation benchmarks, or co-supervision dynamic]
```

---

## Persisting Research Findings & Audit Logging

To ensure intelligence gathered during research is stored permanently in the database without constructing raw SQL queries, use the native CLI subcommands:

1. **Enrich Supervisor Profiles & Links:**
   Store verified academic details, staff page URLs, and lab research notes:
   ```bash
   ./.venv/bin/python ai_phd_search.py supervisor <job_id> --name "<Supervisor Name>" [--title "<Academic Title>"] [--institution "<Institution>"] [--department "<Department>"] [--email "<Email>"] [--url "<Profile URL>"] [--notes "<Lab Group & Publications>"]
   ```

2. **Save Project Research Notes & Append Timeline:**
   Update project research notes and record an audit log in a single command:
   ```bash
   ./.venv/bin/python ai_phd_search.py update <job_id> --research-notes "<Concise summary of decoded problem, methodology, and omissions>" --note "Completed academic intelligence dossier on supervisors and project literature"
   ```

3. **Query Existing Supervisor Dossiers:**
   Cross-reference supervisors across different PhD vacancies:
   ```bash
   ./.venv/bin/python ai_phd_search.py supervisors [--search "<Supervisor or University>"]
   ```
