import os
import io
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import phd_tracker

class TestPhDTrackerCLI(unittest.TestCase):

    def setUp(self):
        # Create a temporary database file
        self.test_db_fd, self.test_db_path = tempfile.mkstemp()
        self.initial_db = {
            "job1": {"title": "Test Job 1", "status": "unreviewed", "url": "http://job1"},
            "job2": {"title": "Test Job 2", "status": "applied", "url": "http://job2"}
        }
        with open(self.test_db_path, 'w') as f:
            json.dump(self.initial_db, f)

        # Patch DB_PATH in the module
        self.db_patcher = patch('phd_tracker.DB_PATH', self.test_db_path)
        self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        os.close(self.test_db_fd)
        os.remove(self.test_db_path)

    def test_command_extract(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp_out:
            tmp_out_path = tmp_out.name

        try:
            phd_tracker.command_extract("unreviewed", tmp_out_path)
            
            with open(tmp_out_path, 'r') as f:
                extracted = json.load(f)
                
            self.assertEqual(len(extracted), 1)
            self.assertIn("job1", extracted)
            self.assertEqual(extracted["job1"]["status"], "unreviewed")
        finally:
            os.remove(tmp_out_path)

    def test_command_apply(self):
        evals = {
            "job1": {"status": "rejected", "reason": "Not a fit"}
        }
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_evals:
            json.dump(evals, tmp_evals)
            tmp_evals_path = tmp_evals.name

        try:
            phd_tracker.command_apply(tmp_evals_path)
            
            with open(self.test_db_path, 'r') as f:
                db = json.load(f)
                
            self.assertEqual(db["job1"]["status"], "rejected")
            self.assertEqual(db["job1"]["reason"], "Not a fit")
            
            # command_apply attempts to delete the evals file
            self.assertFalse(os.path.exists(tmp_evals_path))
        finally:
            if os.path.exists(tmp_evals_path):
                os.remove(tmp_evals_path)

    def test_command_update_status_and_note(self):
        phd_tracker.command_update("job2", status="interviewing", note="Got an interview!")
        
        with open(self.test_db_path, 'r') as f:
            db = json.load(f)
            
        self.assertEqual(db["job2"]["status"], "interviewing")
        self.assertIn("timeline", db["job2"])
        self.assertEqual(len(db["job2"]["timeline"]), 1)
        self.assertEqual(db["job2"]["timeline"][0]["note"], "Got an interview!")
        self.assertIn("timestamp", db["job2"]["timeline"][0])

    @patch('sys.stderr', new_callable=io.StringIO)
    def test_command_update_invalid_job(self, mock_stderr):
        with self.assertRaises(SystemExit) as cm:
            phd_tracker.command_update("nonexistent_job", status="rejected", note="")
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Error: Job ID 'nonexistent_job' not found.", mock_stderr.getvalue())

    @patch('phd_tracker.scrape_jobsacuk')
    @patch('phd_tracker.scrape_findaphd')
    @patch('phd_tracker.sync_playwright')
    def test_command_scrape(self, mock_playwright, mock_findaphd, mock_jobsacuk):
        # Setup mock playwright context manager
        mock_p = MagicMock()
        mock_playwright.return_value.__enter__.return_value = mock_p
        mock_context = mock_p.chromium.launch_persistent_context.return_value

        phd_tracker.command_scrape()

        # Verify the scrapers were called with the correct mocked dependencies
        mock_findaphd.assert_called_once()
        mock_jobsacuk.assert_called_once()

        # Verify browser context was closed properly
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
        self.assertEqual(mock_p.chromium.launch_persistent_context.call_count, 1)

    def test_wait_for_cloudflare_no_challenge(self):
        mock_page = MagicMock()
        mock_page.title.return_value = "Computer Science PhD Projects"
        result = phd_tracker.wait_for_cloudflare(mock_page, timeout_ms=500)
        self.assertTrue(result)

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

        test_db = {}
        phd_tracker.scrape_findaphd(test_db, mock_browser)

        # Verify all 3 projects from multiple pages were recorded
        self.assertIn("p1", test_db)
        self.assertIn("p2", test_db)
        self.assertIn("p3", test_db)
        self.assertEqual(len(test_db), 3)

    def test_command_ingest(self):
        new_portal_jobs = [
            {
                "id": "portal_job_1",
                "title": "Portal Project 1",
                "url": "https://example.ac.uk/project1",
                "description": "A novel AI project",
                "supervisors": [{"name": "Dr. Smith", "university": "UCL"}],
                "institutions": ["UCL"]
            }
        ]
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_ingest:
            json.dump(new_portal_jobs, tmp_ingest)
            tmp_ingest_path = tmp_ingest.name

        try:
            phd_tracker.command_ingest(tmp_ingest_path)
            with open(self.test_db_path, 'r') as f:
                db = json.load(f)

            self.assertIn("portal_job_1", db)
            self.assertEqual(db["portal_job_1"]["title"], "Portal Project 1")
            self.assertEqual(db["portal_job_1"]["status"], "unreviewed")
            self.assertEqual(len(db["portal_job_1"]["supervisors"]), 1)
        finally:
            if os.path.exists(tmp_ingest_path):
                os.remove(tmp_ingest_path)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_summary(self, mock_stdout):
        phd_tracker.command_summary()
        output = mock_stdout.getvalue()
        self.assertIn("PhD Tracker Summary", output)
        self.assertIn("Total Jobs in Database: 2", output)
        self.assertIn("unreviewed", output)
        self.assertIn("applied", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_list(self, mock_stdout):
        phd_tracker.command_list(status="unreviewed")
        output = mock_stdout.getvalue()
        self.assertIn("job1", output)
        self.assertIn("Test Job 1", output)
        self.assertNotIn("job2", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_show(self, mock_stdout):
        phd_tracker.command_show("job1")
        output = mock_stdout.getvalue()
        self.assertIn("JOB ID: job1", output)
        self.assertIn("TITLE:  Test Job 1", output)
        self.assertIn("STATUS: unreviewed", output)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_show_with_deadline(self, mock_stdout):
        with open(self.test_db_path, 'r') as f:
            db = json.load(f)
        db["job1"]["deadline"] = "2026-11-23"
        with open(self.test_db_path, 'w') as f:
            json.dump(db, f)

        phd_tracker.command_show("job1")
        output = mock_stdout.getvalue()
        self.assertIn("DEADLINE: 2026-11-23", output)

    def test_sanitise_html_text(self):
        sample_html = """
        <html>
        <head><title>PhD Opportunity</title></head>
        <body>
        <header><nav><a href="/">Home</a><a href="/login">Sign in</a></nav></header>
        <div class="content">
            <h1>PhD Programme Title</h1>
            <div class="course-description">
                <p>10 fully funded 4-year interdisciplinary PhD positions.</p>
                <p>Deadline: Applications close 23 November 2026.</p>
            </div>
        </div>
        <form id="enquiry-modal" class="modal">
            <h3>Register interest</h3>
            <select id="country">
                <option>Afghanistan</option>
                <option>Albania</option>
                <option>Zimbabwe</option>
            </select>
        </form>
        <footer><p>Copyright 2026</p></footer>
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
        # Test case 1: Raw string with "More details" and "Read more"
        raw = "More details BHF 4-yr PhD Programme: Next Generation Human Models of Cardiovascular Disease Read more Funded PhD Programme"
        cleaned = phd_tracker.clean_job_title(raw)
        self.assertEqual(cleaned, "BHF 4-yr PhD Programme: Next Generation Human Models of Cardiovascular Disease")

        # Test case 2: Mock HTML element with inner heading
        soup = phd_tracker.BeautifulSoup('<div><a href="/p1"><h3>Clean Title From Heading</h3>More details</a></div>', "html.parser")
        link = soup.find("a")
        self.assertEqual(phd_tracker.clean_job_title(link_elem=link), "Clean Title From Heading")

    def test_parse_deadline(self):
        # UK Text dates
        self.assertEqual(phd_tracker.parse_deadline("Applications close 23 November 2026 at 09:00 (GMT)"), "2026-11-23")
        self.assertEqual(phd_tracker.parse_deadline("Application Deadline: 15 January 2027"), "2027-01-15")
        self.assertEqual(phd_tracker.parse_deadline("Closing Date: 31st March 2027"), "2027-03-31")
        # Reverse format: date first then closing phrase
        self.assertEqual(phd_tracker.parse_deadline("23 November 2026 at 09:00 (GMT): Online applications close"), "2026-11-23")
        # ISO format
        self.assertEqual(phd_tracker.parse_deadline("Apply by: 2026-12-01"), "2026-12-01")
        # Slashes
        self.assertEqual(phd_tracker.parse_deadline("Closes: 10/02/2027"), "2027-02-10")
        # None
        self.assertIsNone(phd_tracker.parse_deadline("Contact the department for further details."))

    def test_command_update_deadline(self):
        phd_tracker.command_update("job1", deadline="2026-11-23")
        with open(self.test_db_path, 'r') as f:
            db = json.load(f)
        self.assertEqual(db["job1"]["deadline"], "2026-11-23")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_command_list_urgent(self, mock_stdout):
        # Setup jobs with different deadlines
        with open(self.test_db_path, 'r') as f:
            db = json.load(f)
        db["later_job"] = {"title": "Later Job", "status": "unreviewed", "url": "http://later", "deadline": "2027-01-15"}
        db["urgent_job"] = {"title": "Urgent Job", "status": "unreviewed", "url": "http://urgent", "deadline": "2026-11-23"}
        # job1 in setUp has no deadline
        with open(self.test_db_path, 'w') as f:
            json.dump(db, f)

        phd_tracker.command_list(status="unreviewed", urgent=True)
        output = mock_stdout.getvalue()
        self.assertIn("Sorted by Nearest Deadline", output)
        urgent_idx = output.find("Urgent Job")
        later_idx = output.find("Later Job")
        no_deadline_idx = output.find("Test Job 1")
        self.assertTrue(urgent_idx < later_idx < no_deadline_idx)

    def test_command_clean(self):
        with open(self.test_db_path, 'r') as f:
            db = json.load(f)
        db["bloated_job"] = {
            "title": "More details AI in Healthcare Read more",
            "status": "unreviewed",
            "url": "http://bloated",
            "description": "Project about AI.\nDeadline: 2026-12-15\nRegister your interest for this PhD\nAfghanistan (+93)\nSelect your nationality"
        }
        with open(self.test_db_path, 'w') as f:
            json.dump(db, f)

        phd_tracker.command_clean()

        with open(self.test_db_path, 'r') as f:
            cleaned_db = json.load(f)

        self.assertEqual(cleaned_db["bloated_job"]["title"], "AI in Healthcare")
        self.assertNotIn("Afghanistan", cleaned_db["bloated_job"]["description"])
        self.assertNotIn("Select your nationality", cleaned_db["bloated_job"]["description"])
        self.assertEqual(cleaned_db["bloated_job"]["deadline"], "2026-12-15")

    def test_set_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_dir = os.path.join(tmp_dir, "isolated_e2e")
            phd_tracker.set_data_dir(custom_dir)
            self.assertEqual(phd_tracker.PROFILE_PATH, os.path.join(custom_dir, "user_profile.md"))
            self.assertEqual(phd_tracker.DB_PATH, os.path.join(custom_dir, "jobs_database.json"))
            self.assertEqual(phd_tracker.BROWSER_PROFILE_DIR, os.path.join(custom_dir, ".browser_profile"))
            # Restore DB_PATH for tearDown
            phd_tracker.DB_PATH = self.test_db_path

if __name__ == '__main__':
    unittest.main()
