import os
import sys
import json
import sqlite3
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phd_tracker


def migrate_json_to_sqlite(json_path, db_path):
    """Losslessly transfers all records from a jobs_database.json file into jobs.db."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with phd_tracker.db_session(db_path) as conn:
        for job_id, item in data.items():
            desc = phd_tracker.fold_description(
                item.get("description", ""),
                item.get("training"),
                item.get("trajectory"),
            )
            institution = item.get("institution") or phd_tracker.primary_institution(item.get("institutions"))
            deadline = item.get("deadline") or phd_tracker.parse_deadline(desc)
            url = item.get("url", "")
            source = item.get("source") or phd_tracker.infer_source(job_id, url)

            phd_tracker.insert_job(
                conn,
                job_id=job_id,
                title=item.get("title", ""),
                url=url,
                source=source,
                description=desc,
                status=item.get("status", "unreviewed"),
                deadline=deadline,
                needs_full_description=item.get("needs_full_description", False),
                institution=institution,
                location=item.get("location"),
                reason=item.get("reason"),
                created_at=item.get("created_at") or phd_tracker.now_iso(),
                updated_at=item.get("updated_at") or phd_tracker.now_iso(),
            )

            if item.get("research_notes"):
                phd_tracker.update_job(conn, job_id, research_notes=item["research_notes"])

            timeline = item.get("timeline", [])
            for entry in timeline:
                if isinstance(entry, dict):
                    ts = entry.get("timestamp") or phd_tracker.now_iso()
                    note = entry.get("note", "")
                    phd_tracker.add_timeline(conn, job_id, note, timestamp=ts, touch=False)
                elif isinstance(entry, str):
                    phd_tracker.add_timeline(conn, job_id, entry, touch=False)

            supervisors = item.get("supervisors")
            if supervisors:
                phd_tracker.link_supervisors_for_job(conn, job_id, supervisors, default_institution=institution)


class TestJsonToSqliteMigration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = os.path.join(self.tmp_dir.name, "migrated_jobs.db")
        self.source_json = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs_database.backup.json")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_migration_fidelity_and_completeness(self):
        migrate_json_to_sqlite(self.source_json, self.test_db_path)

        with open(self.source_json, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        with phd_tracker.db_session(self.test_db_path) as conn:
            # 1. Total jobs count
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            self.assertEqual(total_jobs, len(raw_data))
            self.assertEqual(total_jobs, 116)

            # 2. Status counts
            raw_status_counts = {}
            for j in raw_data.values():
                s = j.get("status", "unreviewed")
                raw_status_counts[s] = raw_status_counts.get(s, 0) + 1

            db_status_rows = conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()
            db_status_counts = {r[0]: r[1] for r in db_status_rows}
            self.assertEqual(db_status_counts, raw_status_counts)
            self.assertEqual(db_status_counts["contacted"], 7)
            self.assertEqual(db_status_counts["manual_review"], 1)
            self.assertEqual(db_status_counts["rejected"], 107)
            self.assertEqual(db_status_counts["shortlisted"], 1)

            # 3. Verify every job's fields
            for job_id, expected in raw_data.items():
                row = phd_tracker.get_job(conn, job_id)
                self.assertIsNotNone(row, f"Job {job_id} missing in SQLite")
                self.assertEqual(row["title"], expected.get("title", ""))
                self.assertEqual(row["url"], expected.get("url", ""))
                self.assertEqual(row["status"], expected.get("status", "unreviewed"))
                self.assertEqual(row["reason"], expected.get("reason"))

                # Check deadline
                if expected.get("deadline"):
                    self.assertEqual(row["deadline"], expected["deadline"])

                # Check description and training fold
                if expected.get("training"):
                    self.assertIn("Training:\n\n" + expected["training"].strip(), row["description"])
                if expected.get("trajectory"):
                    self.assertIn("Career Trajectory:\n\n" + expected["trajectory"].strip(), row["description"])

                # Check timeline fidelity
                expected_timeline = expected.get("timeline", [])
                actual_timeline = phd_tracker.get_timeline(conn, job_id)
                self.assertEqual(len(actual_timeline), len(expected_timeline))
                for exp_t, act_t in zip(expected_timeline, actual_timeline):
                    if isinstance(exp_t, dict):
                        self.assertEqual(act_t["note"], exp_t.get("note", ""))
                        self.assertEqual(act_t["timestamp"], exp_t.get("timestamp"))

                # Check supervisors
                if expected.get("supervisors"):
                    sups = phd_tracker.get_job_supervisors(conn, job_id)
                    self.assertGreater(len(sups), 0, f"Expected supervisors for job {job_id}")

            # 4. Supervisor profiles are populated and deduplicated
            total_supervisors = conn.execute("SELECT COUNT(*) FROM supervisors").fetchone()[0]
            self.assertGreater(total_supervisors, 20)
            total_links = conn.execute("SELECT COUNT(*) FROM job_supervisors").fetchone()[0]
            self.assertGreater(total_links, total_supervisors)

            # 5. Job postings table contains initial postings for all migrated jobs
            total_postings = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
            self.assertEqual(total_postings, 116)

    def test_migration_idempotent(self):
        migrate_json_to_sqlite(self.source_json, self.test_db_path)
        # Running a second time should not crash or duplicate records
        migrate_json_to_sqlite(self.source_json, self.test_db_path)
        with phd_tracker.db_session(self.test_db_path) as conn:
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            self.assertEqual(total_jobs, 116)


if __name__ == '__main__':
    unittest.main()
