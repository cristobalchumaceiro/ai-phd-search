import argparse
import json
import time
import sys
import re
import os
import random
import datetime
from bs4 import BeautifulSoup
try:
    from patchright.sync_api import sync_playwright
except ImportError:
    from playwright.sync_api import sync_playwright
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("PHD_TRACKER_DATA_DIR") or SCRIPT_DIR
PROFILE_PATH = os.path.join(DATA_DIR, "user_profile.md")
DB_PATH = os.path.join(DATA_DIR, "jobs_database.json")
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, ".browser_profile")

def set_data_dir(data_dir):
    global DATA_DIR, PROFILE_PATH, DB_PATH, BROWSER_PROFILE_DIR
    DATA_DIR = os.path.abspath(data_dir)
    os.makedirs(DATA_DIR, exist_ok=True)
    PROFILE_PATH = os.path.join(DATA_DIR, "user_profile.md")
    DB_PATH = os.path.join(DATA_DIR, "jobs_database.json")
    BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, ".browser_profile")

def load_db():
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_db(db):
    tmp_path = DB_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(db, f, indent=2)
    os.replace(tmp_path, DB_PATH)

def get_target_url(key):
    try:
        with open(PROFILE_PATH, "r") as f:
            content = f.read()
            match = re.search(r"\*\*" + key + r":\*\*\s*(https?://[^\s]+)", content)
            if match and "Coming Soon" not in match.group(1):
                return match.group(1).strip()
    except Exception:
        pass
    return None

MONTHS_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

def parse_deadline(text):
    """Parses standard UK PhD application closing dates into ISO YYYY-MM-DD.
    Returns None if no unambiguous deadline date is detected.
    """
    if not text:
        return None

    # Pattern 1: ISO YYYY-MM-DD following deadline keywords
    m_iso = re.search(r"(?:deadline|closing date|closes|apply by|applications close)[ \t:]+(\d{4}-\d{2}-\d{2})", text, re.I)
    if m_iso:
        return m_iso.group(1)

    # Pattern 2: DD Month YYYY on the same line after deadline keywords
    m_text = re.search(
        r"(?:deadline|closing date|closes|apply by|applications close)[ \t:\w]*(?:on|by|at)?[ \t:]+(\d{1,2})(?:st|nd|rd|th)?[ \t]+([A-Za-z]+)[ \t]+(202\d)",
        text,
        re.I
    )
    if m_text:
        day = int(m_text.group(1))
        month_str = m_text.group(2).lower()
        year = int(m_text.group(3))
        month = MONTHS_MAP.get(month_str)
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Pattern 2b: Date first then "Online applications close" / "deadline" on the same line
    m_rev = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?[ \t]+([A-Za-z]+)[ \t]+(202\d)[^.\n]*?(?:deadline|closing date|applications close|closes)",
        text,
        re.I
    )
    if m_rev:
        day = int(m_rev.group(1))
        month_str = m_rev.group(2).lower()
        year = int(m_rev.group(3))
        month = MONTHS_MAP.get(month_str)
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # Pattern 3: DD/MM/YYYY
    m_slash = re.search(r"(?:deadline|closing date|closes|apply by)[ \t:]+(\d{1,2})/(\d{1,2})/(202\d)", text, re.I)
    if m_slash:
        day = int(m_slash.group(1))
        month = int(m_slash.group(2))
        year = int(m_slash.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return None

def sanitise_html_text(html_content):
    """Sanitises raw HTML by decomposing non-content tags (form, select, option,
    nav, footer, header, script, style, modals, cookies) and returning clean body text.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup.select("form, select, option, nav, footer, header, script, style, noscript, .modal, [class*='modal'], [id*='modal'], [class*='cookie'], [id*='cookie']"):
        tag.decompose()

    desc_elem = soup.select_one(
        ".phd-sections__description, .phd-project-description, .project-description, "
        ".phd-programme-description, .programme-description, .course-description, .instProgDesc, "
        ".dept-desc, article, main"
    )
    if not desc_elem:
        desc_elem = soup.find("body") or soup

    text = desc_elem.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_text = "\n\n".join(lines)
    cut_idx = cleaned_text.find("Register your interest for this PhD")
    if cut_idx != -1:
        cleaned_text = cleaned_text[:cut_idx].strip()
    return cleaned_text

def clean_job_title(raw_title="", link_elem=None, card=None):
    """Extracts a clean, concise project title, stripping boilerplate buttons
    ("More details", "Read more"), institution names, and card fragments.
    """
    title = ""
    if link_elem:
        heading = link_elem.find(["h1", "h2", "h3", "h4", "h5"])
        if heading:
            title = heading.get_text(" ", strip=True)
        elif hasattr(link_elem, "get") and "phd-result__title" in link_elem.get("class", []):
            title = link_elem.get_text(" ", strip=True)

    if not title and card:
        card_title_elem = card.select_one(".phd-result__title, h3, h4")
        if card_title_elem:
            title = card_title_elem.get_text(" ", strip=True)

    if not title:
        title = raw_title or (link_elem.get_text(" ", strip=True) if link_elem else "")

    title = re.sub(r"\s+", " ", title).strip()

    prefixes = [
        r"^more\s+details\s*",
        r"^read\s+more\s*",
        r"^view\s+programme\s*",
        r"^find\s+out\s+more\s*",
    ]
    suffixes = [
        r"\s*more\s+details$",
        r"\s*read\s+more$",
        r"\s*view\s+programme$",
        r"\s*find\s+out\s+more$",
        r"\s*Funded\s+PhD\s+Programme.*$",
    ]

    changed = True
    while changed:
        changed = False
        for p in prefixes:
            new_title = re.sub(p, "", title, flags=re.I).strip()
            if new_title != title:
                title = new_title
                changed = True
        for s in suffixes:
            new_title = re.sub(s, "", title, flags=re.I).strip()
            if new_title != title:
                title = new_title
                changed = True

    return title

def is_cloudflare_blocked_text(text):
    if not text:
        return True
    lower = text.lower()
    return any(
        ind in lower
        for ind in [
            "just a moment",
            "attention required",
            "checking your browser",
            "sorry, you have been blocked",
            "enable javascript and cookies to continue",
            "performing security verification",
            "verification successful. waiting for",
            "verifying you are human",
            "performance and security by\n\ncloudflare",
            "performance and security by cloudflare",
        ]
    )

def _is_page_on_cloudflare(page_obj):
    challenge_indicators = [
        "just a moment",
        "attention required",
        "checking your browser",
        "security verification",
    ]
    try:
        curr_title = (page_obj.title() or "").strip().lower()
    except Exception:
        return True

    if (
        not curr_title
        or curr_title in ("www.findaphd.com", "findaphd.com")
        or any(indicator in curr_title for indicator in challenge_indicators)
    ):
        return True

    try:
        html = page_obj.content()
        if isinstance(html, str) and is_cloudflare_blocked_text(html):
            return True
    except Exception:
        pass

    return False

def wait_for_cloudflare(page_obj, timeout_ms=45000):
    if not _is_page_on_cloudflare(page_obj):
        return True

    print("[AntiBot] Cloudflare challenge detected. Waiting for clearance (or click the checkbox in Chrome)...", file=sys.stderr)
    start_time = time.time()
    attempt = 0
    while time.time() - start_time < (timeout_ms / 1000):
        if not _is_page_on_cloudflare(page_obj):
            print("[AntiBot] Cloudflare challenge cleared.", file=sys.stderr)
            time.sleep(2)
            return True

        attempt += 1
        # Wait passively on first 2 checks so non-interactive Turnstile can auto-resolve untouched
        if attempt >= 2:
            try:
                for frame in page_obj.frames:
                    if "challenges.cloudflare.com" in frame.url:
                        for selector in ["input[type='checkbox']", ".ctp-checkbox-label", "#challenge-stage", "body"]:
                            elem = frame.locator(selector)
                            if elem.count() > 0:
                                elem.first.click(timeout=1000)
                                break
            except Exception:
                pass

        time.sleep(1.5)

    print("[AntiBot] Warning: Cloudflare challenge did not resolve within timeout.", file=sys.stderr)
    return False

def scrape_findaphd(db, browser_or_context):
    base_url = get_target_url("FindAPhD_URL")
    if not base_url:
        print("Warning: FindAPhD_URL not found, skipping.", file=sys.stderr)
        return

    owns_context = False
    if hasattr(browser_or_context, "new_context"):
        context = browser_or_context.new_context()
        owns_context = True
    else:
        context = browser_or_context

    page_obj = context.new_page()

    page = 1
    seen_this_run = set()
    while True:
        url = base_url if page == 1 else f"{base_url}&PG={page}"
        print(f"[FindAPhD] Scraping search page {page}...", file=sys.stderr)
        page_obj.goto(url, wait_until="domcontentloaded")
        try:
            page_obj.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        page_obj.wait_for_timeout(2000)

        # Cloudflare Turnstile challenge gate
        cleared = wait_for_cloudflare(page_obj, timeout_ms=45000)
        if not cleared:
            print(f"[FindAPhD] Cloudflare challenge unresolved on page {page}. Halting scraper.", file=sys.stderr)
            break

        html = None
        for attempt in range(3):
            try:
                html = page_obj.content()
                break
            except Exception:
                page_obj.wait_for_timeout(2000)
        if html is None:
            html = page_obj.content()

        soup = BeautifulSoup(html, "html.parser")
        results = soup.find_all("a", href=lambda x: x and ("/phds/project/" in x or "/phds/program" in x))

        if not results:
            page_title = page_obj.title().lower()
            if any(ind in page_title for ind in ["just a moment", "attention required", "checking your browser"]):
                print(f"[FindAPhD] Blocked by Cloudflare on page {page}. Stopping pagination.", file=sys.stderr)
            else:
                print(f"[FindAPhD] No results found on page {page}. Stopping pagination.", file=sys.stderr)
            break

        page_job_ids = set()
        new_on_page = 0
        for link_elem in results:
            href = link_elem["href"]
            job_url = href if href.startswith("http") else f"https://www.findaphd.com{href if href.startswith('/') else '/' + href}"
            card = link_elem.find_parent("div", class_=lambda x: x and "row" in x)
            title = clean_job_title(link_elem.text, link_elem=link_elem, card=card)
            if not title:
                continue
            job_id = href.split("?")[-1] if "?" in href else href.strip("/")
            snippet = card.text.strip().replace("\n", " ") if card else "No snippet available."

            page_job_ids.add(job_id)
            if job_id not in db:
                new_on_page += 1
                new_entry = {
                    "title": title,
                    "url": job_url,
                    "status": "unreviewed",
                    "description": snippet,
                    "needs_full_description": True,
                }
                dl = parse_deadline(snippet)
                if dl:
                    new_entry["deadline"] = dl
                db[job_id] = new_entry

        if not page_job_ids or page_job_ids.issubset(seen_this_run):
            print(f"[FindAPhD] No new listings on page {page} compared to current session. Reached end of pagination.", file=sys.stderr)
            break

        print(f"[FindAPhD] Page {page}: {len(page_job_ids)} listings found ({new_on_page} new to database).", file=sys.stderr)
        seen_this_run.update(page_job_ids)
        page += 1

    save_db(db)

    # Initialise fast curl_cffi session with persistent browser cookies if available
    curl_session = None
    if cffi_requests:
        try:
            cookies = {c['name']: c['value'] for c in context.cookies()}
            ua = page_obj.evaluate("navigator.userAgent")
            curl_session = cffi_requests.Session(impersonate="chrome131")
            curl_session.cookies.update(cookies)
            curl_session.headers.update({"User-Agent": ua})
        except Exception as e:
            print(f"[FindAPhD] Warning: Could not initialise curl_cffi session ({e}), falling back to browser.", file=sys.stderr)

    for job_id, job_data in db.items():
        needs_desc = (
            (job_data.get("status") == "unreviewed" and job_data.get("needs_full_description", True))
            or is_cloudflare_blocked_text(job_data.get("description", ""))
        )
        if "findaphd" in job_data.get("url", "").lower() and needs_desc:
            print(f"[FindAPhD] Fetching full description for {job_data['url']}...", file=sys.stderr)
            description_extracted = False

            # Fast Description Fetching via TLS Fingerprinting (curl_cffi)
            if curl_session:
                try:
                    time.sleep(random.uniform(0.5, 1.5))
                    resp = curl_session.get(job_data['url'], timeout=12)
                    if resp.status_code == 200 and not is_cloudflare_blocked_text(resp.text):
                        desc_text = sanitise_html_text(resp.text)
                        if desc_text and not is_cloudflare_blocked_text(desc_text):
                            job_data['description'] = desc_text
                            job_data['needs_full_description'] = False
                            dl = parse_deadline(desc_text)
                            if dl:
                                job_data['deadline'] = dl
                            description_extracted = True
                            save_db(db)
                    elif resp.status_code in (403, 503):
                        curl_session = None
                except Exception as e:
                    print(f"[FindAPhD] curl_cffi fetch failed ({e}), falling back to browser...", file=sys.stderr)
                    curl_session = None

            # Fallback to browser navigation if curl_cffi did not extract description
            if not description_extracted:
                try:
                    time.sleep(random.uniform(1.5, 3.0))
                    page_obj.goto(job_data['url'], wait_until="domcontentloaded")
                    wait_for_cloudflare(page_obj, timeout_ms=20000)
                    try:
                        page_obj.wait_for_selector(".phd-sections__description, .phd-project-description, .project-description, .phd-programme-description, .programme-description, .course-description, .instProgDesc", timeout=4000)
                    except Exception:
                        pass
                    page_obj.evaluate("window.scrollBy(0, 500)")
                    time.sleep(0.5)
                    content_html = page_obj.content()
                    clean_desc = sanitise_html_text(content_html)
                    if clean_desc and not is_cloudflare_blocked_text(clean_desc):
                        job_data['description'] = clean_desc
                        job_data['needs_full_description'] = False
                        dl = parse_deadline(clean_desc)
                        if dl:
                            job_data['deadline'] = dl
                    save_db(db)
                except Exception as e:
                    print(f"[FindAPhD] Failed to fetch {job_data['url']}: {e}", file=sys.stderr)

    page_obj.close()
    if owns_context:
        context.close()

def scrape_jobsacuk(db, browser_or_context):
    base_url = get_target_url("JobsAcUk_URL")
    if not base_url:
        print("Warning: JobsAcUk_URL not found, skipping.", file=sys.stderr)
        return

    owns_context = False
    if hasattr(browser_or_context, "new_context"):
        context = browser_or_context.new_context()
        owns_context = True
    else:
        context = browser_or_context

    page_obj = context.new_page()

    start_index = 1
    new_jobs = {}
    seen_this_run = set()

    while True:
        url = base_url if start_index == 1 else f"{base_url}&pageSize=25&startIndex={start_index}"
        print(f"[JobsAcUk] Scraping search page (startIndex {start_index})...", file=sys.stderr)
        page_obj.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(3, 6))

        links = page_obj.locator('a[href^="/job/"]').all()
        if not links:
            print(f"[JobsAcUk] No results found on startIndex {start_index}. Stopping pagination.", file=sys.stderr)
            break

        page_job_ids = set()
        new_on_page = 0
        for link in links:
            href = link.get_attribute("href")
            title = link.inner_text().strip()
            if not href or not title:
                continue
            full_url = f"https://www.jobs.ac.uk{href}"
            job_id = href.split('/')[2] if len(href.split('/')) > 2 else href
            page_job_ids.add(job_id)
            if job_id not in new_jobs and job_id not in db:
                new_jobs[job_id] = {"title": title, "url": full_url, "status": "unreviewed"}
                new_on_page += 1

        if not page_job_ids or page_job_ids.issubset(seen_this_run):
            print(f"[JobsAcUk] StartIndex {start_index} contains only previously seen listings from current session. Reached end of pagination.", file=sys.stderr)
            break

        print(f"[JobsAcUk] StartIndex {start_index}: {len(page_job_ids)} listings found ({new_on_page} new to database).", file=sys.stderr)
        seen_this_run.update(page_job_ids)
        start_index += 25

    for job_id, job in new_jobs.items():
        print(f"[JobsAcUk] Fetching full description for {job['url']}...", file=sys.stderr)
        try:
            page_obj.goto(job["url"], wait_until="domcontentloaded")
            page_obj.evaluate("window.scrollBy(0, 500)")
            time.sleep(random.uniform(2, 4))
            page_obj.evaluate("window.scrollBy(0, 500)")
            html_content = page_obj.content()
            clean_desc = sanitise_html_text(html_content)
            job["description"] = clean_desc if clean_desc else "Failed to extract description."
            dl = parse_deadline(clean_desc)
            if dl:
                job["deadline"] = dl
        except Exception as e:
            print(f"[JobsAcUk] Failed to fetch {job['url']}: {e}", file=sys.stderr)
            job["description"] = "Failed to fetch."
        db[job_id] = job
        save_db(db)
        time.sleep(random.uniform(5, 10))

    page_obj.close()
    if owns_context:
        context.close()

def command_scrape():
    db = load_db()
    user_data_dir = BROWSER_PROFILE_DIR
    os.makedirs(user_data_dir, exist_ok=True)
    launch_kwargs = {
        "user_data_dir": user_data_dir,
        "headless": False,
        "no_viewport": True,
    }

    with sync_playwright() as p:
        try:
            browser_or_context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception as chrome_err:
            print(f"[Scraper] Error: Failed to launch system Google Chrome: {chrome_err}", file=sys.stderr)
            raise

        scrape_findaphd(db, browser_or_context)
        scrape_jobsacuk(db, browser_or_context)
        browser_or_context.close()
    print("Scraping complete.", file=sys.stderr)

def command_extract(status, out_file):
    db = load_db()
    extracted = {k: v for k, v in db.items() if v.get('status') == status}
    with open(out_file, 'w') as f:
        json.dump(extracted, f, indent=2)
    print(f"Extracted {len(extracted)} '{status}' jobs to {out_file}.", file=sys.stderr)

def command_apply(evals_file):
    db = load_db()
    try:
        with open(evals_file, 'r') as f:
            evals = json.load(f)
    except Exception as e:
        print(f"Error loading evals file {evals_file}: {e}", file=sys.stderr)
        sys.exit(1)
        
    updated_count = 0
    for job_id, job_eval in evals.items():
        if job_id in db:
            db[job_id]['status'] = job_eval.get('status', db[job_id]['status'])
            db[job_id]['reason'] = job_eval.get('reason', db[job_id].get('reason', ''))
            updated_count += 1
            
    save_db(db)
    print(f"Applied {updated_count} evaluations to database.", file=sys.stderr)
    try:
        os.remove(evals_file)
        if os.path.exists(".tmp/unreviewed.json"):
            os.remove(".tmp/unreviewed.json")
        if os.path.exists(".tmp") and not os.listdir(".tmp"):
            os.rmdir(".tmp")
    except:
        pass

def command_update(job_id, status=None, note=None, deadline=None, title=None):
    if not status and not note and not deadline and not title:
        print("Error: Must provide at least --status, --note, --deadline, or --title to update.", file=sys.stderr)
        sys.exit(1)

    db = load_db()
    if job_id not in db:
        print(f"Error: Job ID '{job_id}' not found.", file=sys.stderr)
        sys.exit(1)
        
    job = db[job_id]
    
    if status:
        job['status'] = status

    if title:
        job['title'] = clean_job_title(title)

    if deadline:
        parsed_dl = parse_deadline(deadline) or deadline
        job['deadline'] = parsed_dl
        
    if note:
        job.setdefault('timeline', []).append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "note": note
        })
        
    save_db(db)
    print(f"Successfully updated job '{job_id}'.", file=sys.stderr)

def command_clean():
    db = load_db()
    cleaned_fields = 0
    deadlines_found = 0
    for jid, job in db.items():
        title = job.get("title", "")
        clean_t = clean_job_title(title)
        if clean_t and clean_t != title:
            job["title"] = clean_t
            cleaned_fields += 1
            
        desc = job.get("description", "")
        cut_idx = desc.find("Register your interest for this PhD")
        if cut_idx != -1:
            desc = desc[:cut_idx].strip()
            job["description"] = desc
            cleaned_fields += 1

        dl = parse_deadline(desc)
        if dl and job.get("deadline") != dl:
            job["deadline"] = dl
            deadlines_found += 1
            cleaned_fields += 1

    save_db(db)
    print(f"Hygiene pass complete: cleaned {cleaned_fields} fields and identified {deadlines_found} deadlines across {len(db)} records.", file=sys.stderr)

def command_ingest(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Ingest file '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Error reading ingest file: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(raw_data, list):
        jobs_dict = {}
        for item in raw_data:
            job_id = item.get("id") or item.get("url", "")
            if job_id:
                jobs_dict[job_id] = item
    elif isinstance(raw_data, dict):
        jobs_dict = raw_data
    else:
        print("Error: Ingest data must be a JSON object or array of objects.", file=sys.stderr)
        sys.exit(1)

    db = load_db()
    added_count = 0
    for job_id, job in jobs_dict.items():
        if job_id not in db:
            desc = job.get("description", "")
            dl = job.get("deadline") or parse_deadline(desc)
            db[job_id] = {
                "title": job.get("title", ""),
                "url": job.get("url", ""),
                "status": "unreviewed",
                "description": desc
            }
            if dl:
                db[job_id]["deadline"] = dl
            if "supervisors" in job:
                db[job_id]["supervisors"] = job["supervisors"]
            if "institutions" in job:
                db[job_id]["institutions"] = job["institutions"]
            added_count += 1

    save_db(db)
    print(f"Ingested {added_count} new jobs into database (total database size: {len(db)}).", file=sys.stderr)

def command_summary():
    db = load_db()
    counts = {}
    for j in db.values():
        st = j.get("status", "unspecified")
        counts[st] = counts.get(st, 0) + 1
        
    print(f"\n{'='*20} PhD Tracker Summary {'='*20}")
    print(f"Total Jobs in Database: {len(db)}")
    print(f"{'-'*55}")
    for st, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  • {st:<18} : {count} jobs")
    print(f"{'='*55}\n")

def command_list(status=None, urgent=False):
    db = load_db()
    matches = []
    for jid, j in db.items():
        curr_st = j.get("status", "")
        if status:
            if curr_st.lower() == status.lower():
                matches.append((jid, j))
        else:
            if curr_st != "rejected":
                matches.append((jid, j))

    if urgent:
        matches.sort(key=lambda item: (item[1].get("deadline") is None, item[1].get("deadline", "9999-99-99")))

    urgent_tag = " [Sorted by Nearest Deadline]" if urgent else ""
    header = f"Jobs with Status '{status}'{urgent_tag}" if status else f"Active Tracked Jobs (Excluding Rejected){urgent_tag}"
    print(f"\n=== {header} ({len(matches)} found) ===")
    if not matches:
        print("No matching jobs found.\n")
        return

    for jid, j in matches:
        title = j.get("title", "Untitled")
        curr_st = j.get("status", "unknown")
        url = j.get("url", "")
        deadline = j.get("deadline", "")
        reason = j.get("reason", "")
        sups = j.get("supervisors", [])
        if isinstance(sups, list):
            sup_str = ", ".join([s.get("name", "") + (f" ({s.get('university')})" if s.get("university") else "") for s in sups if isinstance(s, dict)])
        else:
            sup_str = str(sups)
            
        timeline = j.get("timeline", [])
        latest_note = f"Latest Note: {timeline[-1].get('note')} ({timeline[-1].get('timestamp', '')[:10]})" if timeline else ""

        print(f"\n[{jid}] {title}")
        dl_str = f" | Deadline: {deadline}" if deadline else ""
        print(f"  Status: {curr_st}{dl_str} | URL: {url}")
        if sup_str:
            print(f"  Supervisors: {sup_str}")
        if reason:
            print(f"  Reason: {reason}")
        if latest_note:
            print(f"  {latest_note}")
    print()

def command_show(job_id):
    db = load_db()
    if job_id not in db:
        print(f"Error: Job ID '{job_id}' not found in database.", file=sys.stderr)
        sys.exit(1)
        
    j = db[job_id]
    print(f"\n{'='*70}")
    print(f"JOB ID: {job_id}")
    print(f"TITLE:  {j.get('title')}")
    print(f"STATUS: {j.get('status')}")
    if j.get("deadline"):
        print(f"DEADLINE: {j.get('deadline')}")
    print(f"URL:    {j.get('url')}")
    if j.get("reason"):
        print(f"REASON: {j.get('reason')}")
        
    sups = j.get("supervisors", [])
    if sups:
        print(f"\nSUPERVISORS:")
        if isinstance(sups, list):
            for s in sups:
                if isinstance(s, dict):
                    print(f"  • {s.get('name')} | Dept: {s.get('department')} | Uni: {s.get('university')} | Email: {s.get('email', 'N/A')}")
                else:
                    print(f"  • {s}")
        else:
            print(f"  {sups}")
            
    insts = j.get("institutions", [])
    if insts:
        print(f"INSTITUTIONS: {', '.join(insts) if isinstance(insts, list) else insts}")
        
    timeline = j.get("timeline", [])
    if timeline:
        print(f"\nTIMELINE:")
        for t in timeline:
            print(f"  • [{t.get('timestamp', '')[:19]}] {t.get('note')}")
            
    desc = j.get("description")
    if desc:
        print(f"\nDESCRIPTION:\n{desc}")
        
    training = j.get("training")
    if training:
        print(f"\nTRAINING:\n{training}")
        
    trajectory = j.get("trajectory")
    if trajectory:
        print(f"\nTRAJECTORY:\n{trajectory}")
    print(f"{'='*70}\n")

def main():
    parser = argparse.ArgumentParser(description="PhD Tracker CLI")
    parser.add_argument("--data-dir", help="Directory for user_profile.md, jobs_database.json, and .browser_profile (useful for isolated E2E tests)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("scrape", help="Scrape new jobs and add to database")
    
    extract_cmd = subparsers.add_parser("extract", help="Extract jobs of a specific status to a JSON file")
    extract_cmd.add_argument("--status", required=True, help="Status to extract (e.g., unreviewed, pending, rejected)")
    extract_cmd.add_argument("--out", help="Output file (defaults to .tmp/<status>.json)")
    
    apply_cmd = subparsers.add_parser("apply", help="Apply evaluations to the database")
    apply_cmd.add_argument("evals_file", help="JSON file containing evaluations")
    
    update_cmd = subparsers.add_parser("update", help="Update a job's status and add a timeline note")
    update_cmd.add_argument("job_id", help="The ID of the job to update")
    update_cmd.add_argument("--status", help="New status for the job")
    update_cmd.add_argument("--note", help="Note to append to the job's timeline")
    update_cmd.add_argument("--deadline", help="Application deadline date (YYYY-MM-DD)")
    update_cmd.add_argument("--title", help="Updated clean title for the job")
    
    ingest_cmd = subparsers.add_parser("ingest", help="Ingest external or portal jobs into database as unreviewed")
    ingest_cmd.add_argument("jobs_file", help="JSON file containing jobs to ingest")

    subparsers.add_parser("summary", help="Print summary counts of all jobs in the database by status")
    subparsers.add_parser("clean", help="Sanitise database entries and auto-detect deadlines from descriptions")

    list_cmd = subparsers.add_parser("list", help="List jobs filtered by status (defaults to all non-rejected jobs)")
    list_cmd.add_argument("--status", help="Status to filter by (e.g. pending, shortlisted, applied)")
    list_cmd.add_argument("--urgent", action="store_true", help="Sort active jobs by nearest application deadline")

    show_cmd = subparsers.add_parser("show", help="Show complete record and timeline for a specific job")
    show_cmd.add_argument("job_id", help="The ID of the job to display")

    args = parser.parse_args()
    if args.data_dir:
        set_data_dir(args.data_dir)
    
    if args.command == "scrape":
        command_scrape()
    elif args.command == "extract":
        out_file = args.out if args.out else f".tmp/{args.status}.json"
        out_dir = os.path.dirname(out_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        command_extract(args.status, out_file)
    elif args.command == "apply":
        command_apply(args.evals_file)
    elif args.command == "update":
        command_update(args.job_id, args.status, args.note, args.deadline, args.title)
    elif args.command == "ingest":
        command_ingest(args.jobs_file)
    elif args.command == "summary":
        command_summary()
    elif args.command == "clean":
        command_clean()
    elif args.command == "list":
        command_list(args.status, args.urgent)
    elif args.command == "show":
        command_show(args.job_id)

if __name__ == "__main__":
    main()
