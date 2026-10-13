import argparse
import json
import time
import sys
import re
import os
import random
import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_PATH = os.path.join(SCRIPT_DIR, "user_profile.md")
DB_PATH = os.path.join(SCRIPT_DIR, "jobs_database.json")

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

def scrape_findaphd(db, browser):
    base_url = get_target_url("FindAPhD_URL")
    if not base_url:
        print("Warning: FindAPhD_URL not found, skipping.", file=sys.stderr)
        return
        
    context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page_obj = context.new_page()
    Stealth().apply_stealth_sync(page_obj)
    
    page = 1
    while True:
        url = base_url if page == 1 else f"{base_url}&PG={page}"
        print(f"[FindAPhD] Scraping search page {page}...", file=sys.stderr)
        page_obj.goto(url, wait_until="domcontentloaded")
        page_obj.wait_for_timeout(3000)
        html = page_obj.content()
        soup = BeautifulSoup(html, "html.parser")
        results = soup.find_all("a", href=lambda x: x and ("/phds/project/" in x or "/phds/program" in x))
        
        if not results:
            print(f"[FindAPhD] No results found on page {page}. Stopping pagination.", file=sys.stderr)
            break
            
        found_new_on_page = False
        for link_elem in results:
            href = link_elem["href"]
            job_url = href if href.startswith("http") else f"https://www.findaphd.com{href if href.startswith('/') else '/' + href}"
            title = link_elem.text.replace("\n", "").strip()
            if not title:
                continue
            job_id = href.split("?")[-1] if "?" in href else href.strip("/")
            card = link_elem.find_parent("div", class_=lambda x: x and "row" in x)
            snippet = card.text.strip().replace("\n", " ") if card else "No snippet available."
            
            if job_id not in db:
                found_new_on_page = True
                db[job_id] = {"title": title, "url": job_url, "status": "unreviewed", "description": snippet}
                
        if not found_new_on_page:
            print("[FindAPhD] No new jobs on this page. Stopping pagination.")
            break
        page += 1
        
    save_db(db)
    for job_id, job_data in db.items():
        if job_data.get("status") == "unreviewed" and "findaphd" in job_data.get("url", "").lower():
            print(f"[FindAPhD] Fetching full description for {job_data['url']}...", file=sys.stderr)
            try:
                time.sleep(random.uniform(5.0, 12.0))
                page_obj.goto(job_data['url'], wait_until="domcontentloaded")
                try:
                    page_obj.wait_for_selector(".phd-sections__description, .phd-project-description, .project-description", timeout=15000)
                except:
                    pass
                page_obj.evaluate("window.scrollBy(0, 500)")
                time.sleep(1)
                page_obj.evaluate("window.scrollBy(0, 500)")
                content = page_obj.evaluate("""() => {
                    const desc = document.querySelector('.phd-sections__description') || document.querySelector('.phd-project-description') || document.querySelector('.project-description');
                    if (desc) return desc.innerText;
                    if (!document.body.innerText.includes("Sorry, you have been blocked")) return document.body.innerText;
                    return "Cloudflare Blocked";
                }""")
                if content and content != "Cloudflare Blocked":
                    job_data['description'] = content
                save_db(db)
            except Exception as e:
                print(f"[FindAPhD] Failed to fetch {job_data['url']}: {e}", file=sys.stderr)
    context.close()

def scrape_jobsacuk(db, browser):
    base_url = get_target_url("JobsAcUk_URL")
    if not base_url:
        print("Warning: JobsAcUk_URL not found, skipping.", file=sys.stderr)
        return

    context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page_obj = context.new_page()
    Stealth().apply_stealth_sync(page_obj)
    
    start_index = 1
    new_jobs = {}
    
    while True:
        url = base_url if start_index == 1 else f"{base_url}&pageSize=25&startIndex={start_index}"
        print(f"[JobsAcUk] Scraping search page (startIndex {start_index})...", file=sys.stderr)
        page_obj.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(3, 6))
        
        links = page_obj.locator('a[href^="/job/"]').all()
        if not links:
            print(f"[JobsAcUk] No results found on startIndex {start_index}. Stopping pagination.", file=sys.stderr)
            break
            
        page_found = False
        for link in links:
            href = link.get_attribute("href")
            title = link.inner_text().strip()
            if not href or not title:
                continue
            full_url = f"https://www.jobs.ac.uk{href}"
            job_id = href.split('/')[2] if len(href.split('/')) > 2 else href
            if job_id not in new_jobs and job_id not in db:
                new_jobs[job_id] = {"title": title, "url": full_url, "status": "unreviewed"}
                page_found = True
                
        if not page_found:
            print(f"[JobsAcUk] No new jobs on startIndex {start_index}. Stopping pagination.", file=sys.stderr)
            break
        start_index += 25

    for job_id, job in new_jobs.items():
        print(f"[JobsAcUk] Fetching full description for {job['url']}...", file=sys.stderr)
        try:
            page_obj.goto(job["url"], wait_until="domcontentloaded")
            page_obj.evaluate("window.scrollBy(0, 500)")
            time.sleep(random.uniform(2, 4))
            page_obj.evaluate("window.scrollBy(0, 500)")
            desc = page_obj.evaluate("document.body.innerText")
            job["description"] = desc.strip() if desc else "Failed to extract description."
        except Exception as e:
            print(f"[JobsAcUk] Failed to fetch {job['url']}: {e}", file=sys.stderr)
            job["description"] = "Failed to fetch."
        db[job_id] = job
        save_db(db)
        time.sleep(random.uniform(5, 10))
    context.close()

def command_scrape():
    db = load_db()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        scrape_findaphd(db, browser)
        scrape_jobsacuk(db, browser)
        browser.close()
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

def command_update(job_id, status, note):
    if not status and not note:
        print("Error: Must provide at least --status or --note to update.", file=sys.stderr)
        sys.exit(1)

    db = load_db()
    if job_id not in db:
        print(f"Error: Job ID '{job_id}' not found.", file=sys.stderr)
        sys.exit(1)
        
    job = db[job_id]
    
    if status:
        job['status'] = status
        
    if note:
        job.setdefault('timeline', []).append({
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "note": note
        })
        
    save_db(db)
    print(f"Successfully updated job '{job_id}'.", file=sys.stderr)

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
            db[job_id] = {
                "title": job.get("title", ""),
                "url": job.get("url", ""),
                "status": "unreviewed",
                "description": job.get("description", "")
            }
            if "supervisors" in job:
                db[job_id]["supervisors"] = job["supervisors"]
            if "institutions" in job:
                db[job_id]["institutions"] = job["institutions"]
            added_count += 1

    save_db(db)
    print(f"Ingested {added_count} new jobs into database (total database size: {len(db)}).", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="PhD Tracker CLI")
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
    
    ingest_cmd = subparsers.add_parser("ingest", help="Ingest external or portal jobs into database as unreviewed")
    ingest_cmd.add_argument("jobs_file", help="JSON file containing jobs to ingest")

    args = parser.parse_args()
    
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
        command_update(args.job_id, args.status, args.note)
    elif args.command == "ingest":
        command_ingest(args.jobs_file)

if __name__ == "__main__":
    main()
