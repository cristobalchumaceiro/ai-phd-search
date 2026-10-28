import os
import sys
import io
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import phd_tracker


class TrackerTestCase(unittest.TestCase):
    """Base class: every test runs against a fresh temporary jobs.db."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = os.path.join(self.tmp_dir.name, "jobs.db")
        self.db_patcher = patch('phd_tracker.DB_PATH', self.test_db_path)
        self.db_patcher.start()
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(conn, "job1", "Test Job 1", "http://job1", source="portal")
            phd_tracker.insert_job(conn, "job2", "Test Job 2", "http://job2", source="portal", status="applied")

    def tearDown(self):
        self.db_patcher.stop()
        self.tmp_dir.cleanup()

    def job(self, job_id):
        with phd_tracker.db_session() as conn:
            return phd_tracker.get_job(conn, job_id)

    def query(self, sql, params=()):
        with phd_tracker.db_session() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]


class TestSchemaAndDataLayer(TrackerTestCase):

    def test_schema_creates_all_tables(self):
        names = {r["name"] for r in self.query("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("jobs", "supervisors", "job_supervisors", "timeline", "scrape_runs"):
            self.assertIn(table, names)

    def test_foreign_keys_enabled(self):
        with phd_tracker.db_session() as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_insert_job_ignores_duplicates_and_sets_timestamps(self):
        with phd_tracker.db_session() as conn:
            self.assertFalse(phd_tracker.insert_job(conn, "job1", "Dup", "http://dup"))
        job = self.job("job1")
        self.assertEqual(job["title"], "Test Job 1")
        self.assertTrue(job["created_at"])
        self.assertEqual(job["created_at"], job["updated_at"])

    def test_infer_source(self):
        self.assertEqual(phd_tracker.infer_source("p1", "https://www.findaphd.com/x"), "findaphd")
        self.assertEqual(phd_tracker.infer_source("123", "https://www.jobs.ac.uk/job/123"), "jobsacuk")
        self.assertEqual(phd_tracker.infer_source("trees_775", "https://trees-dla.ac.uk/p"), "portal:trees")

    def test_clean_supervisor_name(self):
        self.assertEqual(phd_tracker.clean_supervisor_name("Prof. Mat Disney"), "Mat Disney")
        self.assertEqual(phd_tracker.clean_supervisor_name("Assoc Prof Yukun Hu"), "Yukun Hu")
        self.assertEqual(phd_tracker.clean_supervisor_name("D John Marsham"), "John Marsham")
        self.assertEqual(phd_tracker.clean_supervisor_name("Drew Smith"), "Drew Smith")

    def test_parse_supervisor_entries_string_formats(self):
        raw = [
            "Prof Tim Heaton < T.Heaton@leeds.ac.uk >",
            "Dr Nadhir Ben Rached < N.BenRached@leeds.ac.uk > (University of Leeds, Mathematics), "
            "George Datseris < G.Datseris@exeter.ac.uk > (University of Exeter, Mathematics and Statistics), "
            "Lorenzo Tomassini < L.F.Tomassini@leeds.ac.uk > (University of Leeds, School of Mathematics (and Met Office))",
            "Prof Jason Lowe (University of Leeds; Met Office, School of Earth, Environment & Sustainability)",
        ]
        entries = phd_tracker.parse_supervisor_entries(raw, default_institution="University of Leeds")
        self.assertEqual([e["name"] for e in entries], [
            "Prof Tim Heaton", "Dr Nadhir Ben Rached", "George Datseris", "Lorenzo Tomassini", "Prof Jason Lowe",
        ])
        self.assertEqual(entries[0]["institution"], "University of Leeds")
        self.assertEqual(entries[0]["academic_title"], "Professor")
        self.assertEqual(entries[2]["institution"], "University of Exeter")
        self.assertEqual(entries[2]["email"], "G.Datseris@exeter.ac.uk")
        self.assertEqual(entries[3]["department"], "School of Mathematics (and Met Office)")
        self.assertEqual(entries[4]["institution"], "University of Leeds")
        self.assertEqual(entries[4]["department"], "School of Earth, Environment & Sustainability")

    def test_parse_supervisor_entries_dict_format(self):
        raw = [{"name": "Tamsin Edwards", "department": "Geography", "university": "King's College London",
                "email": "tamsin.edwards@kcl.ac.uk", "profile_url": "https://kcl.ac.uk/te"}]
        entry = phd_tracker.parse_supervisor_entries(raw)[0]
        self.assertEqual(entry["institution"], "King's College London")
        self.assertEqual(entry["profile_url"], "https://kcl.ac.uk/te")

    def test_supervisor_profile_shared_across_jobs(self):
        with phd_tracker.db_session() as conn:
            a = phd_tracker.upsert_supervisor(conn, "Dr Jane Doe", "UCL")
            b = phd_tracker.upsert_supervisor(conn, "Prof Jane Doe", "ucl", email="j.doe@ucl.ac.uk")
            phd_tracker.link_supervisor(conn, "job1", a)
            phd_tracker.link_supervisor(conn, "job2", b)
            phd_tracker.link_supervisor(conn, "job2", b)
        self.assertEqual(a, b)
        sups = self.query("SELECT * FROM supervisors")
        self.assertEqual(len(sups), 1)
        self.assertEqual(sups[0]["email"], "j.doe@ucl.ac.uk")
        self.assertEqual(len(self.query("SELECT * FROM job_supervisors")), 2)

    def test_supervisor_without_institution_is_upgraded(self):
        with phd_tracker.db_session() as conn:
            a = phd_tracker.upsert_supervisor(conn, "Stephen Pates")
            b = phd_tracker.upsert_supervisor(conn, "Stephen Pates", "University College London")
            c = phd_tracker.upsert_supervisor(conn, "Dr Stephen Pates")
        self.assertEqual(a, b)
        self.assertEqual(b, c)
        self.assertEqual(self.query("SELECT institution FROM supervisors")[0]["institution"], "University College London")

    def test_fold_description_and_primary_institution(self):
        folded = phd_tracker.fold_description("Main.", "Train here.", "")
        self.assertEqual(folded, "Main.\n\nTraining:\n\nTrain here.")
        self.assertEqual(phd_tracker.primary_institution(["University of Leeds  (School of Earth)"]), "University of Leeds")
        self.assertIsNone(phd_tracker.primary_institution([]))

    def test_job_postings_created_and_queried(self):
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(conn, "canon1", "Canon Job", "http://canon")
            phd_tracker.add_job_posting(conn, "canon1", "portal:unrisk", "unrisk_1", "http://unrisk/1")

            self.assertEqual(phd_tracker.get_canonical_job_id(conn, "canon1"), "canon1")
            self.assertEqual(phd_tracker.get_canonical_job_id(conn, "unrisk_1"), "canon1")

            self.assertEqual(phd_tracker.get_job(conn, "unrisk_1")["id"], "canon1")
            self.assertEqual(phd_tracker.get_job(conn, "canon1")["title"], "Canon Job")

            postings = phd_tracker.get_job_postings(conn, "unrisk_1")
            self.assertEqual(len(postings), 2)
            self.assertEqual({p["external_id"] for p in postings}, {"canon1", "unrisk_1"})


class TestPhDTrackerCLI(TrackerTestCase):

    def test_clean_stale_singleton_locks_dead_pid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = os.path.join(temp_dir, "SingletonLock")
            sock_path = os.path.join(temp_dir, "SingletonSocket")
            cookie_path = os.path.join(temp_dir, "SingletonCookie")

            os.symlink("fakehost-999999", lock_path)
            with open(sock_path, "w") as f:
                f.write("socket")
            with open(cookie_path, "w") as f:
                f.write("cookie")

            self.assertTrue(os.path.islink(lock_path))
            self.assertTrue(os.path.exists(sock_path))
            self.assertTrue(os.path.exists(cookie_path))

            cleaned = phd_tracker._clean_stale_singleton_locks(temp_dir, force=False)
            self.assertTrue(cleaned)
            self.assertFalse(os.path.exists(lock_path))
            self.assertFalse(os.path.exists(sock_path))
            self.assertFalse(os.path.exists(cookie_path))

            # When force=True, cleans without needing dead pid symlink
            with open(lock_path, "w") as f:
                f.write("lock")
            with open(sock_path, "w") as f:
                f.write("socket")
            cleaned_force = phd_tracker._clean_stale_singleton_locks(temp_dir, force=True)
            self.assertTrue(cleaned_force)
            self.assertFalse(os.path.exists(lock_path))
            self.assertFalse(os.path.exists(sock_path))

    def test_command_update_status_and_note(self):
        phd_tracker.command_update("job2", status="interviewing", note="Got an interview!")
        job = self.job("job2")
        self.assertEqual(job["status"], "interviewing")
        with phd_tracker.db_session() as conn:
            timeline = phd_tracker.get_timeline(conn, "job2")
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["note"], "Got an interview!")
        self.assertTrue(timeline[0]["timestamp"])

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_command_update_invalid_job(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            phd_tracker.command_update("nonexistent_job", status="rejected", note="")
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error: Job ID 'nonexistent_job' not found.", mock_stderr.getvalue())

    def test_command_update_deadline(self):
        phd_tracker.command_update("job1", deadline="2026-11-23")
        job = self.job("job1")
        self.assertEqual(job["deadline"], "2026-11-23")

    def test_command_update_research_notes_and_institution(self):
        phd_tracker.command_update("job1", research_notes="Decoded methodology", institution="UCL", location="London")
        job = self.job("job1")
        self.assertEqual(job["research_notes"], "Decoded methodology")
        self.assertEqual(job["institution"], "UCL")
        self.assertEqual(job["location"], "London")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_supervisor_and_supervisors(self, mock_stdout):
        phd_tracker.command_supervisor(
            "job1",
            name="Prof Jane Doe",
            academic_title="Professor",
            email="jane.doe@ucl.ac.uk",
            institution="UCL",
            department="Computer Science",
            profile_url="https://ucl.ac.uk/jd",
            notes="Expert in ML",
        )
        with phd_tracker.db_session() as conn:
            sups = phd_tracker.get_job_supervisors(conn, "job1")
        self.assertEqual(len(sups), 1)
        self.assertEqual(sups[0]["name"], "Jane Doe")
        self.assertEqual(sups[0]["academic_title"], "Professor")
        self.assertEqual(sups[0]["institution"], "UCL")

        phd_tracker.command_supervisors()
        output = mock_stdout.getvalue()
        self.assertIn("Jane Doe", output)
        self.assertIn("Professor", output)
        self.assertIn("UCL", output)
        self.assertIn("Expert in ML", output)

        # Test list --supervisors and supervisor --list aliases
        phd_tracker.command_list(supervisors=True, search="Jane")
        self.assertIn("Jane Doe", mock_stdout.getvalue())

        phd_tracker.command_supervisor(list_mode=True, search="UCL")
        self.assertIn("UCL", mock_stdout.getvalue())

    def test_command_delete(self):
        with phd_tracker.db_session() as conn:
            phd_tracker.add_timeline(conn, "job1", "Initial contact")
        phd_tracker.command_delete("job1")
        self.assertIsNone(self.job("job1"))
        self.assertEqual(len(self.query("SELECT * FROM timeline WHERE job_id = 'job1'")), 0)
        self.assertEqual(len(self.query("SELECT * FROM job_supervisors WHERE job_id = 'job1'")), 0)
        with patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as cm:
            phd_tracker.command_delete("job1")
        self.assertEqual(cm.exception.code, 1)

    def test_command_merge(self):
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(conn, "jobA", "Messy Long Title " * 10, "http://findaphd/A", source="findaphd")
            phd_tracker.insert_job(conn, "jobB", "Clean Title", "http://portal/B", source="portal:custom", institution="UCL")
            phd_tracker.add_timeline(conn, "jobA", "Found on FindAPhD")
            phd_tracker.add_timeline(conn, "jobB", "Found on Portal")
            s_id = phd_tracker.upsert_supervisor(conn, "Jane Doe", "UCL")
            phd_tracker.link_supervisor(conn, "jobB", s_id)

        phd_tracker.command_merge("jobA", "jobB")

        self.assertIsNone(self.query("SELECT * FROM jobs WHERE id = 'jobB'") or None)
        job_a = self.job("jobA")
        self.assertEqual(job_a["title"], "Clean Title")
        self.assertEqual(job_a["institution"], "UCL")
        self.assertEqual(self.job("jobB")["id"], "jobA")
        postings = self.query("SELECT * FROM job_postings WHERE job_id = 'jobA'")
        self.assertEqual(len(postings), 2)
        timeline = self.query("SELECT * FROM timeline WHERE job_id = 'jobA'")
        self.assertEqual(len(timeline), 3)
        sups = self.query("SELECT * FROM job_supervisors WHERE job_id = 'jobA'")
        self.assertEqual(len(sups), 1)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_show_with_multiple_postings(self, mock_stdout):
        with phd_tracker.db_session() as conn:
            phd_tracker.add_job_posting(conn, "job1", "portal:partner", "partner_1", "http://partner/1")
        phd_tracker.command_show("partner_1")
        output = mock_stdout.getvalue()
        self.assertIn("JOB ID: job1", output)
        self.assertIn("ALIAS:  partner_1", output)
        self.assertIn("POSTINGS & URLS:", output)
        self.assertIn("http://job1", output)
        self.assertIn("http://partner/1", output)

    @patch('phd_tracker.scrape_jobsacuk')
    @patch('phd_tracker.scrape_findaphd')
    @patch('phd_tracker.sync_playwright')
    def test_command_scrape(self, mock_playwright, mock_findaphd, mock_jobsacuk):
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = mock_p.chromium.launch_persistent_context.return_value

        phd_tracker.command_scrape()

        mock_findaphd.assert_called_once()
        mock_jobsacuk.assert_called_once()
        mock_context.close.assert_called_once()

    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('phd_tracker.sync_playwright')
    def test_command_scrape_surfaces_system_chrome_error(self, mock_playwright, mock_stderr):
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_p.chromium.launch_persistent_context.side_effect = RuntimeError(
            "Sandbox denied Mach port lookup for Google Chrome.app"
        )

        with self.assertRaises(RuntimeError) as cm:
            phd_tracker.command_scrape()

        self.assertIn("Sandbox denied Mach port lookup", str(cm.exception))
        self.assertIn("Failed to launch system Google Chrome", mock_stderr.getvalue())
        self.assertNotIn("Falling back to bundled chromium", mock_stderr.getvalue())

    @patch('phd_tracker.time.sleep')
    @patch('phd_tracker._clean_stale_singleton_locks')
    @patch('phd_tracker.scrape_jobsacuk')
    @patch('phd_tracker.scrape_findaphd')
    @patch('phd_tracker.sync_playwright')
    def test_command_scrape_retries_once_on_singleton_collision(
        self, mock_playwright, mock_findaphd, mock_jobsacuk, mock_clean_locks, mock_sleep
    ):
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = MagicMock()

        mock_p.chromium.launch_persistent_context.side_effect = [
            RuntimeError("BrowserType.launch_persistent_context: Opening in existing browser session."),
            mock_context,
        ]

        phd_tracker.command_scrape()

        self.assertEqual(mock_p.chromium.launch_persistent_context.call_count, 2)
        mock_clean_locks.assert_any_call(phd_tracker.BROWSER_PROFILE_DIR, force=True)
        mock_sleep.assert_called_once_with(1)
        mock_findaphd.assert_called_once()
        mock_jobsacuk.assert_called_once()
        mock_context.close.assert_called_once()

    def test_wait_for_cloudflare_no_challenge(self):
        mock_page = MagicMock()
        mock_page.title.return_value = "Normal PhD Results Page"
        mock_page.content.return_value = "<html><body><h1>PhD Projects</h1></body></html>"
        self.assertTrue(phd_tracker.wait_for_cloudflare(mock_page, timeout_ms=5000))

    @patch('time.sleep')
    def test_wait_for_cloudflare_clears(self, mock_sleep):
        mock_page = MagicMock()
        mock_page.frames = []
        # Title transitions from challenge to verification screen to normal
        mock_page.title.side_effect = [
            "Just a moment...",
            "www.findaphd.com",
            "Computer Science PhD Projects",
            "Computer Science PhD Projects",
        ]
        mock_page.content.side_effect = [
            "<html><body>Performing security verification. Verification successful. Waiting for www.findaphd.com to respond</body></html>",
            "<html><body><h1>Computer Science PhD Projects</h1></body></html>",
        ]
        result = phd_tracker.wait_for_cloudflare(mock_page, timeout_ms=3000)
        self.assertTrue(result)

    @patch('time.sleep')
    def test_wait_for_cloudflare_timeout(self, mock_sleep):
        mock_page = MagicMock()
        mock_page.frames = []
        mock_page.title.return_value = "Just a moment..."
        mock_page.evaluate.return_value = None
        result = phd_tracker.wait_for_cloudflare(mock_page, timeout_ms=500)
        self.assertFalse(result)

    @patch('phd_tracker.cffi_requests', None)
    @patch('time.sleep')
    @patch('phd_tracker.get_target_url')
    def test_scrape_findaphd_multi_page(self, mock_get_target_url, mock_sleep):
        mock_get_target_url.return_value = "https://www.findaphd.com/search"
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_browser.new_context.return_value.new_page.return_value = mock_page
        mock_browser.cookies.return_value = []
        mock_page.title.return_value = "PhD Results"
        mock_page.evaluate.return_value = "Sample project description text."

        pages = {
            1: '<html><body><a href="/phds/project/proj1?p1">Project 1</a><a href="/phds/project/proj2?p2">Project 2</a></body></html>',
            2: '<html><body><a href="/phds/project/proj3?p3">Project 3</a></body></html>',
        }
        current_page = [1]
        def fake_goto(url, *args, **kwargs):
            if "PG=2" in url:
                current_page[0] = 2
            elif "PG=3" in url:
                current_page[0] = 3
        mock_page.goto.side_effect = fake_goto
        mock_page.content.side_effect = lambda: pages.get(current_page[0], '<html><body><div>No results</div></body></html>')

        with phd_tracker.db_session() as conn:
            phd_tracker.scrape_findaphd(conn, mock_browser)

        jobs = {r["id"]: r for r in self.query("SELECT * FROM jobs")}
        self.assertIn("p1", jobs)
        self.assertIn("p2", jobs)
        self.assertIn("p3", jobs)

    def test_command_ingest(self):
        new_jobs = [
            {
                "id": "trees_999",
                "title": "Trees Ingested Project",
                "url": "https://trees.ac.uk/project/999",
                "description": "Novel forestry research.",
                "institutions": ["University of Leeds (School of Earth)"],
                "supervisors": ["Prof Alan Turing < a.turing@leeds.ac.uk > (University of Leeds, Computing)"]
            }
        ]
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_ingest:
            json.dump(new_jobs, tmp_ingest)
            tmp_ingest_path = tmp_ingest.name

        try:
            phd_tracker.command_ingest(tmp_ingest_path)
            job = self.job("trees_999")
            self.assertIsNotNone(job)
            self.assertEqual(job["title"], "Trees Ingested Project")
            self.assertEqual(job["institution"], "University of Leeds")
            self.assertEqual(job["status"], "unreviewed")
            with phd_tracker.db_session() as conn:
                sups = phd_tracker.get_job_supervisors(conn, "trees_999")
            self.assertEqual(len(sups), 1)
            self.assertEqual(sups[0]["name"], "Alan Turing")
            self.assertEqual(sups[0]["email"], "a.turing@leeds.ac.uk")
        finally:
            if os.path.exists(tmp_ingest_path):
                os.remove(tmp_ingest_path)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_summary(self, mock_stdout):
        phd_tracker.command_summary()
        output = mock_stdout.getvalue()
        self.assertIn("Total Jobs in Database: 2", output)
        self.assertIn("unreviewed", output)
        self.assertIn("applied", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_list(self, mock_stdout):
        phd_tracker.command_list()
        output = mock_stdout.getvalue()
        self.assertIn("Test Job 1", output)
        self.assertIn("Test Job 2", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_list_urgent(self, mock_stdout):
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(conn, "later_job", "Later Job", "http://later", deadline="2027-01-15")
            phd_tracker.insert_job(conn, "urgent_job", "Urgent Job", "http://urgent", deadline="2026-11-23")

        phd_tracker.command_list(status="unreviewed", urgent=True)
        output = mock_stdout.getvalue()
        self.assertIn("Sorted by Nearest Deadline", output)
        urgent_idx = output.find("Urgent Job")
        later_idx = output.find("Later Job")
        no_deadline_idx = output.find("Test Job 1")
        self.assertTrue(urgent_idx < later_idx < no_deadline_idx)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_list_includes_institution_location_and_full_description(self, mock_stdout):
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(
                conn, "full_job", "Full Description Job", "http://full_job",
                institution="Imperial College London", location="London",
                deadline="2027-01-20", description="Detailed research into quantum algorithms.\nSecond line of description."
            )

        # 1. Summary mode (full=False)
        phd_tracker.command_list(status="unreviewed", full=False)
        out_summary = mock_stdout.getvalue()
        self.assertIn("Institution: Imperial College London", out_summary)
        self.assertIn("(London)", out_summary)
        self.assertIn("Deadline: 2027-01-20", out_summary)
        self.assertIn("Deadline: Unstated", out_summary)
        self.assertNotIn("Detailed research into quantum algorithms.", out_summary)

        # 2. Full mode (full=True)
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        phd_tracker.command_list(status="unreviewed", full=True)
        out_full = mock_stdout.getvalue()
        self.assertIn("Institution: Imperial College London", out_full)
        self.assertIn("(London)", out_full)
        self.assertIn("Deadline: 2027-01-20", out_full)
        self.assertIn("Description:\n    Detailed research into quantum algorithms.\n    Second line of description.", out_full)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_show(self, mock_stdout):
        phd_tracker.command_show("job1")
        output = mock_stdout.getvalue()
        self.assertIn("JOB ID: job1", output)
        self.assertIn("TITLE:  Test Job 1", output)
        self.assertIn("STATUS: unreviewed", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_show_with_deadline(self, mock_stdout):
        with phd_tracker.db_session() as conn:
            phd_tracker.update_job(conn, "job1", deadline="2026-11-23")
        phd_tracker.command_show("job1")
        output = mock_stdout.getvalue()
        self.assertIn("DEADLINE: 2026-11-23", output)

    def test_sanitise_html_text(self):
        sample_html = """
        <html>
            <head><title>PhD Project</title></head>
            <body>
                <header>FindAPhD Header Navigation Sign in</header>
                <div class="phd-sections__description">
                    <h2>Project Description</h2>
                    <p>10 fully funded 4-year interdisciplinary PhD positions.</p>
                    <p>Applications close 23 November 2026.</p>
                </div>
                <div class="phd-enquiry-form">
                    <h3>Register your interest for this PhD</h3>
                    <select><option>Afghanistan (+93)</option><option>Zimbabwe (+263)</option></select>
                </div>
                <footer>Copyright 2026 FindAPhD</footer>
            </body>
        </html>
        """
        clean = phd_tracker.sanitise_html_text(sample_html)
        self.assertNotIn("Afghanistan", clean)
        self.assertNotIn("Zimbabwe", clean)
        self.assertNotIn("Sign in", clean)
        self.assertNotIn("Copyright 2026", clean)
        self.assertIn("10 fully funded 4-year interdisciplinary PhD positions.", clean)
        self.assertIn("Applications close 23 November 2026.", clean)

    def test_clean_job_title(self):
        raw = "More details BHF 4-yr PhD Programme: Next Generation Human Models of Cardiovascular Disease Read more Funded PhD Programme"
        cleaned = phd_tracker.clean_job_title(raw)
        self.assertEqual(cleaned, "BHF 4-yr PhD Programme: Next Generation Human Models of Cardiovascular Disease")

        soup = BeautifulSoup('<div><a href="/p1"><h3>Clean Title From Heading</h3>More details</a></div>', "html.parser")
        link = soup.find("a")
        self.assertEqual(phd_tracker.clean_job_title(link_elem=link), "Clean Title From Heading")

    def test_parse_deadline(self):
        self.assertEqual(phd_tracker.parse_deadline("Applications close 23 November 2026 at 09:00 (GMT)"), "2026-11-23")
        self.assertEqual(phd_tracker.parse_deadline("Application Deadline: 15 January 2027"), "2027-01-15")
        self.assertEqual(phd_tracker.parse_deadline("Closing Date: 31st March 2027"), "2027-03-31")
        self.assertEqual(phd_tracker.parse_deadline("23 November 2026 at 09:00 (GMT): Online applications close"), "2026-11-23")
        self.assertEqual(phd_tracker.parse_deadline("Apply by: 2026-12-01"), "2026-12-01")
        self.assertEqual(phd_tracker.parse_deadline("Closes: 10/02/2027"), "2027-02-10")
        self.assertIsNone(phd_tracker.parse_deadline("Contact the department for further details."))

    def test_parse_deadline_until_variants(self):
        self.assertEqual(
            phd_tracker.parse_deadline("This project is open for applications until 22nd January 2027"),
            "2027-01-22"
        )
        self.assertEqual(
            phd_tracker.parse_deadline("Applications until 15 March 2027"),
            "2027-03-15"
        )
        self.assertEqual(
            phd_tracker.parse_deadline("Applications until: 2027-01-22"),
            "2027-01-22"
        )
        self.assertEqual(
            phd_tracker.parse_deadline("This project is open until 10/02/2027"),
            "2027-02-10"
        )

    def test_insert_job_auto_sanitises_and_parses_deadline(self):
        with phd_tracker.db_session() as conn:
            phd_tracker.insert_job(
                conn,
                "auto_cleaned_job",
                "More details AI in Healthcare Read more",
                "http://cleaned",
                description="Project about AI.\nDeadline: 2026-12-15\nMore details about the project.",
            )
        job = self.job("auto_cleaned_job")
        self.assertEqual(job["title"], "AI in Healthcare")
        self.assertEqual(job["deadline"], "2026-12-15")

    def test_set_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_dir = os.path.join(tmp_dir, "isolated_e2e")
            phd_tracker.set_data_dir(custom_dir)
            self.assertEqual(phd_tracker.PROFILE_PATH, os.path.join(custom_dir, "user_profile.md"))
            self.assertEqual(phd_tracker.DB_PATH, os.path.join(custom_dir, "jobs.db"))
            self.assertEqual(phd_tracker.BROWSER_PROFILE_DIR, os.path.join(custom_dir, ".browser_profile"))
            phd_tracker.DB_PATH = self.test_db_path


if __name__ == '__main__':
    unittest.main()
