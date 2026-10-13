# Autonomous AI PhD Tracker & ATS

An automated pipeline that scrapes academic job boards (FindAPhD, jobs.ac.uk), bypasses bot-protections, and uses an AI Agent to evaluate opportunities against your personal CV. It acts as a full Application Tracking System (ATS) you can control entirely with natural language.

## How It Works

1. **The Python Engine (`phd_tracker.py`)**: A Playwright script that mimics human behavior to bypass Cloudflare, scraping job descriptions and safely updating your local `jobs_database.json`.
2. **The PhD Tracker & ATS (`.agents/skills/phd-tracker/SKILL.md`)**: The primary AI skill managing daily scraping, profile evaluation, supervisor research, and ATS pipeline tracking.
3. **The Portal Scraper (`.agents/skills/portal-scraper/SKILL.md`)**: A specialised skill that can autonomously inspect any arbitrary university, DLA, or CDT portal URL, micro-test extraction, and import all opportunities directly into the tracker.

---

## 1. Setup & Configuration

1. **Clone the Repository**
   ```bash
   git clone https://github.com/cristobalchumaceiro/phd-tracker.git
   cd phd-tracker
   ```

2. **Install Dependencies**
   *(We highly recommend naming your virtual environment `.venv` as the AI agent is instructed to look for it there).*
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure Your Profile**
   Rename `user_profile.template.md` to `user_profile.md`. 
   Paste your specific FindAPhD search URL at the top, and define your research interests, CV details, and hard constraints (e.g., funding requirements).
   *(Note: Your data is completely private. `user_profile.md` and `jobs_database.json` are git-ignored, so your personal CV and evaluations never leave your machine).*

---

## 2. Using the Tracker in Natural Language

You do not need to memorize commands or slash shortcuts. Once setup, open your AI assistant in this repository and simply talk to it. 

### Discovery Mode
To find and evaluate new jobs, try saying:
* *"Any new positions today?"*
* *"Run the PhD tracker."*
* *"Scrape for new jobs."*

### Custom Portal Scraping
If you have a link to a specific Doctoral Landscape Award (DLA), CDT, or university project portal:
* *"Scrape and import projects from `https://www.trees-dla.ac.uk/projects`."*
* *"Extract all PhD positions from this portal URL and evaluate them against my profile."*

### ATS Mode
To manage jobs you've already discovered, try saying:
* *"Show me my current PhD pipeline."* (The agent will render a Kanban board).
* *"Move job p123 to shortlisted and add a note that I emailed the supervisor."*
* *"Add a timeline note to p123 that they rejected my application."*

---

## 3. Agent Usage Instructions

You can use this tracker with your preferred AI CLI assistant. Because this tool relies on a custom `SKILL.md` file to instruct the AI, usage differs slightly depending on how you interact with your assistant:

### Google Antigravity (Recommended)
Antigravity natively understands the rules in the `.agents/skills` folder. 
* **Installation:** Follow the [official Antigravity instructions](https://github.com/google/antigravity) to install the CLI.
* **CLI:** Run `agy` in your terminal.
* **Usage:** Simply start talking (e.g., *"Are there any new PhD positions today?"*).

### Anthropic Claude Code
Claude Code does not automatically discover the hidden `.agents/skills` folder.
* **Installation:** Run `npm install -g @anthropic-ai/claude-code`.
* **CLI:** Run `claude` in your terminal.
* **Usage:** In your first prompt, tell it to read `.agents/skills/phd-tracker/SKILL.md` to learn how the system works. After that, you can interact with it naturally.
