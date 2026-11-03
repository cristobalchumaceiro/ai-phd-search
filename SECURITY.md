# Security Policy & Agentic Risk Disclosure

**AI PhD Search** is an **agentic workflow**. Rather than running as a traditional passive application, you operate it through an AI coding assistant (such as Google Antigravity, Claude Code, Cursor, or Codex) that is granted permission to execute commands, launch a browser, and read local files on your machine.

Before using this tool, please understand how it interacts with your system, the web, and your personal data.

---

## 1. What You Are Granting the Agent Access To

1. **Terminal & Command Execution:**
   * The repository includes [`AGENTS.md`](AGENTS.md) and [`CLAUDE.md`](CLAUDE.md), which instruct your AI assistant to run `./.venv/bin/python ai_phd_search.py *` subcommands autonomously without prompting you for confirmation on every step.
   * The `scrape` command launches your local Google Chrome installation (`patchright`) outside the terminal sandbox so it can reach external websites and pass Cloudflare anti-bot checks.

2. **Web Access & Untrusted External Content:**
   * During scraping and supervisor research, the tool fetches live web pages from external job boards (FindAPhD, jobs.ac.uk) and university portals, and feeds the extracted text into your AI assistant's context window.
   * **Prompt Injection Risk:** Because job descriptions are authored by third parties on the public internet, untrusted web text is read directly by your LLM. While `ai_phd_search.py` strips HTML tags, forms, and scripts before storing descriptions, always review any unexpected shell commands if your assistant asks to run something outside the standard `ai_phd_search.py` CLI.

3. **Personal & Academic Data:**
   * If you place your CV or transcripts in `docs/`, or generate `user_profile.md` and `jobs.db`, your AI assistant reads these files and sends their contents to your configured LLM provider (e.g. Anthropic, Google, OpenAI) to evaluate PhD fit.
   * All personal files (`docs/*`, `user_profile.md`, `jobs.db`, and `.browser_profile/`) are listed in [`.gitignore`](.gitignore) so they are never committed to Git, but you should always verify `git status` before pushing to a public fork.

---

## 2. Built-In Safeguards

* **Read-Only Scraping:** The scraper only fetches public listings and never submits forms, credentials, or personal information to external portals.
* **Encapsulated Database CLI:** All database operations go through deterministic subcommands in `ai_phd_search.py` rather than ad-hoc shell scripts or raw SQL queries.
* **Sandboxed Local Operations:** Only `scrape` requires network and browser access; all other commands (`list`, `show`, `update`, `supervisor`, `summary`, `merge`, `delete`, `ingest`) are local SQLite operations.

---

## 3. Reporting a Vulnerability

If you discover a security issue—such as a sanitizer bypass, a path traversal bug, or a flaw in the `.gitignore` rules that could expose personal data—please open a [GitHub Issue](https://github.com/cristobalchumaceiro/ai-phd-search/issues) or contact the maintainer directly via GitHub rather than including sensitive details in a public pull request.
