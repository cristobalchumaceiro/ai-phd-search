import os
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phd_tracker


class TestE2EJsonVsSqliteEquivalence(unittest.TestCase):

    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.json_baseline_path = os.path.join(self.root_dir, "tests", "e2e", "run", "json_baseline", "jobs_database.json")
        self.sqlite_db_path = os.path.join(self.root_dir, "tests", "e2e", "run", "sqlite_run", "jobs.db")

    def test_json_baseline_matches_sqlite_run_exactly(self):
        self.assertTrue(os.path.exists(self.json_baseline_path), "JSON baseline missing")
        self.assertTrue(os.path.exists(self.sqlite_db_path), "SQLite run DB missing")

        with open(self.json_baseline_path, "r", encoding="utf-8") as f:
            json_jobs = json.load(f)

        with phd_tracker.db_session(self.sqlite_db_path) as conn:
            sqlite_jobs = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()}

        # 1. Exact count
        self.assertEqual(len(sqlite_jobs), len(json_jobs))
        self.assertEqual(len(sqlite_jobs), 7)

        # 2. Every job exists with matching title, status, URL, reason
        for job_id, exp in json_jobs.items():
            self.assertIn(job_id, sqlite_jobs)
            act = sqlite_jobs[job_id]
            self.assertEqual(act["title"], exp["title"])
            self.assertEqual(act["status"], exp["status"])
            self.assertEqual(act["reason"], exp["reason"])
            self.assertEqual(act["url"], exp["url"])
            if exp.get("deadline"):
                self.assertEqual(act["deadline"], exp["deadline"])

        # 3. Timeline check on shortlisted job p199240
        with phd_tracker.db_session(self.sqlite_db_path) as conn:
            timeline = phd_tracker.get_timeline(conn, "p199240")
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["note"], "E2E smoke test verification")


if __name__ == "__main__":
    unittest.main()
