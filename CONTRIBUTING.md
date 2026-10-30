# Contributing to AI PhD Search

Contributions, bug reports, and feature suggestions are welcome!

## Quickstart

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/<your-username>/ai-phd-search.git
   cd ai-phd-search
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the test suite:**
   ```bash
   ./.venv/bin/python -m unittest discover -s tests -v
   ```

## Development Guidelines

* **Privacy:** Never commit personal data. SQLite database files (`jobs.db`), personal profile files (`user_profile.md`), and documents in `docs/` are strictly git-ignored.
* **Encapsulated Storage (Zero Raw SQL):** All database reads and writes must be handled via CLI subcommands in `ai_phd_search.py` rather than ad-hoc SQL strings.
* **Tests:** Add unit tests in `tests/test_ai_phd_search.py` for any new parser logic or CLI commands. Ensure the full test suite passes before submitting.
* **Language:** Use British English spelling in documentation, code comments, and docstrings (e.g. *normalise*, *sanitise*, *colour*).

## Pull Requests

1. Create a feature branch (`git checkout -b feature/my-change`).
2. Make focused, atomic commits.
3. Verify that all tests pass (`./.venv/bin/python -m unittest discover -s tests -v`).
4. Open a pull request describing what changed and why.
