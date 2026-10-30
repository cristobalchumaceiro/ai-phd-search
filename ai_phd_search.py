import argparse
import json
import time
import sys
import re
import os
import random
import sqlite3
import datetime
from contextlib import contextmanager
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
DATA_DIR = os.environ.get("AI_PHD_SEARCH_DATA_DIR") or os.environ.get("PHD_TRACKER_DATA_DIR") or SCRIPT_DIR
DB_FILENAME = "jobs.db"
PROFILE_PATH = os.path.join(DATA_DIR, "user_profile.md")
DB_PATH = os.path.join(DATA_DIR, DB_FILENAME)
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, ".browser_profile")

def set_data_dir(data_dir):
    global DATA_DIR, PROFILE_PATH, DB_PATH, BROWSER_PROFILE_DIR
    DATA_DIR = os.path.abspath(data_dir)
    os.makedirs(DATA_DIR, exist_ok=True)
    PROFILE_PATH = os.path.join(DATA_DIR, "user_profile.md")
    DB_PATH = os.path.join(DATA_DIR, DB_FILENAME)
    BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, ".browser_profile")

# ---------------------------------------------------------------------------
# SQLite storage layer (jobs.db)
#
# All SQL lives in this module. Agents must interact with the database only
# through the CLI subcommands defined in main(), never through raw SQL.
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL,
    title                   TEXT NOT NULL,
    url                     TEXT NOT NULL,
    institution             TEXT,
    location                TEXT,
    deadline                TEXT,
    description             TEXT,
    needs_full_description  INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'unreviewed',
    reason                  TEXT,
    research_notes          TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supervisors (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL COLLATE NOCASE,
    academic_title          TEXT,
    email                   TEXT,
    institution             TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
    department              TEXT,
    profile_url             TEXT,
    research_notes          TEXT,
    UNIQUE(name, institution)
);

CREATE TABLE IF NOT EXISTS job_supervisors (
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    supervisor_id           INTEGER NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, supervisor_id)
);

CREATE TABLE IF NOT EXISTS timeline (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    timestamp               TEXT NOT NULL,
    note                    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at                  TEXT NOT NULL,
    source                  TEXT NOT NULL,
    search_url              TEXT NOT NULL,
    pages_scanned           INTEGER NOT NULL,
    total_found             INTEGER NOT NULL,
    new_jobs_added          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS job_postings (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source                  TEXT NOT NULL,
    external_id             TEXT NOT NULL,
    url                     TEXT NOT NULL,
    scraped_at              TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_timeline_job ON timeline(job_id);
CREATE INDEX IF NOT EXISTS idx_job_supervisors_sup ON job_supervisors(supervisor_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_job ON job_postings(job_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_ext ON job_postings(external_id);
"""

JOB_COLUMNS = (
    "source", "title", "url", "institution", "location", "deadline", "description",
    "needs_full_description", "status", "reason", "research_notes",
)
SUPERVISOR_COLUMNS = ("academic_title", "email", "department", "profile_url", "research_notes")

VALID_STATUSES = (
    "unreviewed", "pending", "shortlisted", "contacted",
    "applied", "interviewing", "offer", "rejected",
)

def validate_status(status):
    if status is None:
        return None
    norm = status.strip().lower()
    if norm not in VALID_STATUSES:
        print(
            f"Error: Invalid status '{status}'. Valid statuses: {', '.join(VALID_STATUSES)}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return norm

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def connect_db(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO job_postings (job_id, source, external_id, url, scraped_at) "
        "SELECT id, source, id, url, created_at FROM jobs"
    )
    conn.commit()
    return conn

@contextmanager
def db_session(path=None):
    """Opens jobs.db, commits on success, rolls back on error, always closes."""
    conn = connect_db(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()

def infer_source(job_id, url=""):
    lower_url = (url or "").lower()
    if "findaphd.com" in lower_url:
        return "findaphd"
    if "jobs.ac.uk" in lower_url:
        return "jobsacuk"
    prefix = job_id.split("_", 1)[0] if "_" in job_id else ""
    return f"portal:{prefix}" if prefix else "portal"

def get_canonical_job_id(conn, any_id):
    """Resolves any job_id or external posting id to the canonical job id."""
    if not any_id:
        return None
    row = conn.execute("SELECT id FROM jobs WHERE id = ?", (any_id,)).fetchone()
    if row:
        return row["id"]
    row = conn.execute("SELECT job_id FROM job_postings WHERE external_id = ?", (any_id,)).fetchone()
    if row:
        return row["job_id"]
    return any_id

def job_exists(conn, any_id):
    canon_id = get_canonical_job_id(conn, any_id)
    return conn.execute("SELECT 1 FROM jobs WHERE id = ?", (canon_id,)).fetchone() is not None

def insert_job(conn, job_id, title, url, source=None, description="", status="unreviewed",
               deadline=None, needs_full_description=False, institution=None, location=None,
               reason=None, created_at=None, updated_at=None):
    """Inserts a job if its id is new. Also registers its primary posting in job_postings."""
    created = created_at or now_iso()
    src = source or infer_source(job_id, url)
    clean_title = clean_job_title(title) if title else ""
    dl = deadline or parse_deadline(description or "")
    cur = conn.execute(
        "INSERT OR IGNORE INTO jobs (id, source, title, url, institution, location, deadline, description, "
        "needs_full_description, status, reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id, src, clean_title or title or "", url or "", institution, location,
            dl, description or "", 1 if needs_full_description else 0, status or "unreviewed",
            reason, created, updated_at or created,
        ),
    )
    if cur.rowcount == 1:
        conn.execute(
            "INSERT OR IGNORE INTO job_postings (job_id, source, external_id, url, scraped_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, src, job_id, url or "", created),
        )
        return True
    return False

def add_job_posting(conn, job_id, source, external_id, url, scraped_at=None):
    canon_id = get_canonical_job_id(conn, job_id)
    cur = conn.execute(
        "INSERT OR IGNORE INTO job_postings (job_id, source, external_id, url, scraped_at) VALUES (?, ?, ?, ?, ?)",
        (canon_id, source, external_id, url, scraped_at or now_iso()),
    )
    return cur.rowcount == 1

def update_job(conn, job_id, **fields):
    """Updates whitelisted job columns and bumps updated_at. Returns True if the job exists."""
    canon_id = get_canonical_job_id(conn, job_id)
    fields = {k: v for k, v in fields.items() if k in JOB_COLUMNS}
    if not fields:
        return job_exists(conn, canon_id)
    if "needs_full_description" in fields:
        fields["needs_full_description"] = 1 if fields["needs_full_description"] else 0
    assignments = ", ".join(f"{col} = ?" for col in fields)
    cur = conn.execute(
        f"UPDATE jobs SET {assignments}, updated_at = ? WHERE id = ?",
        (*fields.values(), now_iso(), canon_id),
    )
    return cur.rowcount == 1

def delete_job(conn, job_id):
    canon_id = get_canonical_job_id(conn, job_id)
    return conn.execute("DELETE FROM jobs WHERE id = ?", (canon_id,)).rowcount == 1

def add_timeline(conn, job_id, note, timestamp=None, touch=True):
    canon_id = get_canonical_job_id(conn, job_id)
    ts = timestamp or now_iso()
    conn.execute("INSERT INTO timeline (job_id, timestamp, note) VALUES (?, ?, ?)", (canon_id, ts, note))
    if touch:
        conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (now_iso(), canon_id))

def get_job(conn, job_id):
    canon_id = get_canonical_job_id(conn, job_id)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (canon_id,)).fetchone()
    return dict(row) if row else None

def get_job_postings(conn, job_id):
    canon_id = get_canonical_job_id(conn, job_id)
    rows = conn.execute(
        "SELECT source, external_id, url, scraped_at FROM job_postings WHERE job_id = ? ORDER BY id",
        (canon_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def get_timeline(conn, job_id):
    canon_id = get_canonical_job_id(conn, job_id)
    rows = conn.execute("SELECT timestamp, note FROM timeline WHERE job_id = ? ORDER BY id", (canon_id,)).fetchall()
    return [dict(r) for r in rows]

def get_job_supervisors(conn, job_id):
    canon_id = get_canonical_job_id(conn, job_id)
    rows = conn.execute(
        "SELECT s.* FROM supervisors s JOIN job_supervisors js ON js.supervisor_id = s.id "
        "WHERE js.job_id = ? ORDER BY s.id",
        (canon_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def log_scrape_run(conn, source, search_url, pages_scanned, total_found, new_jobs_added):
    conn.execute(
        "INSERT INTO scrape_runs (ran_at, source, search_url, pages_scanned, total_found, new_jobs_added) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now_iso(), source, search_url, pages_scanned, total_found, new_jobs_added),
    )

# --- Supervisor normalisation ------------------------------------------------

HONORIFIC_RE = re.compile(r"^(?:(?:assoc(?:iate)?\.?\s+)?prof(?:essor)?\.?|dr\.?|mr\.?|mrs\.?|ms\.?|miss|d)\s+", re.I)

def clean_supervisor_name(name):
    """Strips honorifics (Dr, Prof, Assoc Prof, ...) so 'Dr A Smith' and 'A Smith' map to one profile."""
    name = re.sub(r"\s+", " ", name or "").strip(" ,;")
    previous = None
    while previous != name:
        previous = name
        name = HONORIFIC_RE.sub("", name).strip()
    return name

def honorific_title(name):
    lowered = (name or "").strip().lower()
    if re.match(r"^assoc(?:iate)?\.?\s+prof", lowered):
        return "Associate Professor"
    if re.match(r"^prof(?:essor)?\.?\s", lowered):
        return "Professor"
    return None

def upsert_supervisor(conn, name, institution=None, **fields):
    """Creates or enriches a supervisor profile keyed on (name, institution). Returns the supervisor id."""
    clean_name = clean_supervisor_name(name)
    if not clean_name:
        return None
    inst = re.sub(r"\s+", " ", institution or "").strip()
    fields = {
        k: (v.strip() if isinstance(v, str) else v)
        for k, v in fields.items()
        if k in SUPERVISOR_COLUMNS and v not in (None, "")
    }

    row = conn.execute("SELECT id FROM supervisors WHERE name = ? AND institution = ?", (clean_name, inst)).fetchone()
    if not row and inst:
        # Upgrade a profile previously stored without an institution
        row = conn.execute("SELECT id FROM supervisors WHERE name = ? AND institution = ''", (clean_name,)).fetchone()
        if row:
            conn.execute("UPDATE supervisors SET institution = ? WHERE id = ?", (inst, row["id"]))
    if not row and not inst:
        # Reuse an existing profile when the name is unambiguous
        matches = conn.execute("SELECT id FROM supervisors WHERE name = ?", (clean_name,)).fetchall()
        if len(matches) == 1:
            row = matches[0]

    if row:
        if fields:
            assignments = ", ".join(f"{col} = ?" for col in fields)
            conn.execute(f"UPDATE supervisors SET {assignments} WHERE id = ?", (*fields.values(), row["id"]))
        return row["id"]

    columns = ["name", "institution", *fields.keys()]
    placeholders = ", ".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO supervisors ({', '.join(columns)}) VALUES ({placeholders})",
        (clean_name, inst, *fields.values()),
    )
    return cur.lastrowid

def link_supervisor(conn, job_id, supervisor_id):
    canon_id = get_canonical_job_id(conn, job_id)
    conn.execute(
        "INSERT OR IGNORE INTO job_supervisors (job_id, supervisor_id) VALUES (?, ?)",
        (canon_id, supervisor_id),
    )

SUPERVISOR_STRING_RE = re.compile(
    r"\s*(?P<name>[^<(,]+?)\s*"
    r"(?:<\s*(?P<email>[^<>]+?)\s*>)?\s*"
    r"(?:\((?P<aff>(?:[^()]|\([^()]*\))*)\))?\s*"
    r"(?:,|$)"
)

def _split_affiliation(aff):
    if not aff:
        return None, None
    parts = aff.split(",", 1)
    inst = parts[0].split(";")[0].strip()
    dept = parts[1].strip() if len(parts) > 1 else None
    return inst or None, dept or None

def parse_supervisor_entries(raw, default_institution=None):
    """Normalises supervisor data from portals/ingest files into dicts.

    Accepts a list of dicts ({name, email, university|institution, department, profile_url})
    or strings like 'Dr A Smith < a@uni.ac.uk > (Uni, Dept), B Jones < b@uni.ac.uk >'.
    """
    if not raw:
        return []
    if isinstance(raw, (str, dict)):
        raw = [raw]
    entries = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name", "")
            if clean_supervisor_name(name):
                entries.append({
                    "name": name,
                    "email": item.get("email"),
                    "institution": item.get("institution") or item.get("university") or default_institution,
                    "department": item.get("department"),
                    "profile_url": item.get("profile_url") or item.get("url"),
                    "academic_title": item.get("academic_title") or honorific_title(name),
                })
        elif isinstance(item, str):
            text = item.strip()
            pos = 0
            while pos < len(text):
                match = SUPERVISOR_STRING_RE.match(text, pos)
                if not match or match.end() == pos:
                    break
                pos = match.end()
                name = match.group("name")
                if not clean_supervisor_name(name):
                    continue
                inst, dept = _split_affiliation(match.group("aff"))
                entries.append({
                    "name": name,
                    "email": match.group("email"),
                    "institution": inst or default_institution,
                    "department": dept,
                    "academic_title": honorific_title(name),
                })
    return entries

def link_supervisors_for_job(conn, job_id, raw_supervisors, default_institution=None):
    linked = 0
    for entry in parse_supervisor_entries(raw_supervisors, default_institution):
        sup_id = upsert_supervisor(
            conn,
            entry["name"],
            entry.get("institution"),
            email=entry.get("email"),
            department=entry.get("department"),
            profile_url=entry.get("profile_url"),
            academic_title=entry.get("academic_title"),
        )
        if sup_id:
            link_supervisor(conn, job_id, sup_id)
            linked += 1
    return linked

def primary_institution(institutions):
    """Returns the first institution name, stripping trailing '(Department)' qualifiers."""
    if isinstance(institutions, str):
        institutions = [institutions]
    for inst in institutions or []:
        name = re.sub(r"\s*\(.*\)\s*$", "", inst or "")
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            return name
    return None

def fold_description(description, training=None, trajectory=None):
    """Folds portal-specific Training / Career Trajectory sections into the main description."""
    parts = [(description or "").strip()]
    if training and training.strip():
        parts.append("Training:\n\n" + training.strip())
    if trajectory and trajectory.strip():
        parts.append("Career Trajectory:\n\n" + trajectory.strip())
    return "\n\n".join(p for p in parts if p)

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

DEADLINE_KEYWORDS_RE = re.compile(
    r"(?:deadline|closing date|closes|apply by|applications?\s+close|applications?\s+until|open\s+(?:for\s+applications\s+)?until)",
    re.I,
)

DEADLINE_DATE_RE = re.compile(
    r"(?:"
    r"(?P<iso>\d{4}-\d{2}-\d{2})"
    r"|"
    r"(?P<day>\d{1,2})[ \t]*(?:st|nd|rd|th)?[ \t]+(?P<month>[A-Za-z]+)[ \t]+(?P<year>202\d)"
    r"|"
    r"(?P<month_mdy>[A-Za-z]+)[ \t]+(?P<day_mdy>\d{1,2})[ \t]*(?:st|nd|rd|th)?,?[ \t]+(?P<year_mdy>202\d)"
    r"|"
    r"(?P<day_sl>\d{1,2})/(?P<month_sl>\d{1,2})/(?P<year_sl>202\d)"
    r")",
    re.I,
)

DEADLINE_REV_RE = re.compile(
    r"(\d{1,2})[ \t]*(?:st|nd|rd|th)?[ \t]+([A-Za-z]+)[ \t]+(202\d)[^.\n]{0,45}?(?:deadline|closing date|applications close|closes)",
    re.I,
)

def _is_valid_deadline_bridge(bridge):
    if len(bridge) > 45 or bridge.count("\n") > 2:
        return False
    if re.search(r"(?<!\b[ap]\.m)\.\s+[A-Z]", bridge, re.I) or bridge.strip().endswith("."):
        return False
    return True

def _parse_date_match(m):
    iso = m.group("iso")
    if iso:
        return iso
    if m.group("day") and m.group("month") and m.group("year"):
        day = int(m.group("day"))
        month = MONTHS_MAP.get(m.group("month").lower())
        year = int(m.group("year"))
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    if m.group("month_mdy") and m.group("day_mdy") and m.group("year_mdy"):
        day = int(m.group("day_mdy"))
        month = MONTHS_MAP.get(m.group("month_mdy").lower())
        year = int(m.group("year_mdy"))
        if month and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    if m.group("day_sl") and m.group("month_sl") and m.group("year_sl"):
        day = int(m.group("day_sl"))
        month = int(m.group("month_sl"))
        year = int(m.group("year_sl"))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None

def parse_deadline(text):
    """Parses standard UK PhD application closing dates into ISO YYYY-MM-DD.
    Returns None if no unambiguous deadline date is detected.
    """
    if not text:
        return None

    candidates = []

    # 1. Forward search: deadline keywords followed by bounded bridge and date
    for m in DEADLINE_KEYWORDS_RE.finditer(text):
        sub = text[m.end():m.end() + 100]
        for m_date in DEADLINE_DATE_RE.finditer(sub):
            bridge = sub[:m_date.start()]
            if not _is_valid_deadline_bridge(bridge):
                continue
            iso = _parse_date_match(m_date)
            if iso:
                candidates.append(iso)
                break

    # 2. Reverse pattern: Date first then deadline keyword on same line
    m_rev = DEADLINE_REV_RE.search(text)
    if m_rev:
        day = int(m_rev.group(1))
        month = MONTHS_MAP.get(m_rev.group(2).lower())
        year = int(m_rev.group(3))
        if month and 1 <= day <= 31:
            candidates.append(f"{year:04d}-{month:02d}-{day:02d}")

    return min(candidates) if candidates else None

INLINE_TAGS = (
    "a", "strong", "b", "em", "i", "u", "span", "sup", "sub",
    "small", "mark", "abbr", "code", "font",
)

INSTITUTION_KEYWORD_RE = re.compile(
    r"\b(?:University|College|Imperial|UCL|QMUL|KCL|LSE|Institute|School\s+of|Academy|Conservatoire)\b",
    re.I,
)

def extract_findaphd_metadata(html_or_soup):
    """Extracts structured header and key-info badges (institution, department,
    supervisors, closing date, funding) from FindAPhD project and programme pages.
    """
    soup = html_or_soup if hasattr(html_or_soup, "select_one") else BeautifulSoup(html_or_soup or "", "html.parser")
    inst_el = soup.select_one(
        ".phd-header__institution, .phd-programme__institution, .programme-header__institution, "
        ".phd-institution, .instProgDesc .inst-name"
    )
    dept_el = soup.select_one(".phd-header__department, .phd-programme__department, .programme-header__department")
    institution = inst_el.get_text(" ", strip=True) if inst_el else None
    department = dept_el.get_text(" ", strip=True) if dept_el else None

    if not institution:
        # Fallback to heading pattern: e.g. "President’s PhD Scholarships at Imperial College London"
        h_el = soup.select_one("h1, .phd-header__phd-title, .phd-programme-description h1, .phd-programme-description h2")
        if h_el:
            h_text = h_el.get_text(" ", strip=True)
            m_at = re.search(r"\bat\s+(?:the\s+)?([A-Z][A-Za-z0-9'’&.,\-\s]+?)(?:\s*\(.*?\))?$", h_text)
            if m_at:
                candidate = re.sub(r"\s+", " ", m_at.group(1)).strip(" .,;")
                if candidate and INSTITUTION_KEYWORD_RE.search(candidate):
                    institution = candidate

    supervisors = []
    closing_text = None
    funding = None
    for span in soup.select(".key-info .key-info__content"):
        text = re.sub(r"\s+", " ", span.get_text(" ", strip=True)).strip()
        if not text:
            continue
        icon_classes = " ".join(" ".join(i.get("class", [])) for i in span.find_all("i")).lower()
        if "fa-calendar" in icon_classes:
            closing_text = text
        elif any(k in icon_classes for k in ("fa-wallet", "fa-pound", "fa-sterling", "fa-coins", "fa-money")):
            funding = text
        elif not icon_classes or "fa-user" in icon_classes:
            links = [a.get_text(" ", strip=True) for a in span.find_all("a") if a.get_text(" ", strip=True)]
            candidates = links if links else [s.strip() for s in re.split(r"\s*,\s*", text) if s.strip()]
            for cand in candidates:
                low = cand.lower()
                if any(bad in low for bad in ("funded", "project", "students", "year round", "deadline")):
                    continue
                if clean_supervisor_name(cand):
                    supervisors.append(cand)

    deadline = parse_deadline(f"Closing Date: {closing_text}") if closing_text else None
    return {
        "institution": institution or None,
        "department": department or None,
        "supervisors": supervisors,
        "closing_text": closing_text,
        "deadline": deadline,
        "funding": funding,
    }

def sanitise_html_text(html_content):
    """Sanitises raw HTML by decomposing non-content tags (form, select, option,
    nav, footer, header, script, style, modals, cookies) and returning clean body text.
    Preserves structured FindAPhD header/key-info fields placed outside .phd-sections__description.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup.select(
        "form, select, option, nav, footer, header, script, style, noscript, "
        ".modal, [class*='modal'], [id*='modal'], [class*='cookie'], [id*='cookie'], "
        ".breadcrumb, [class*='breadcrumb'], [class*='promo-banner'], [class*='study-fair'], "
        "[class*='studyfair'], .phd-enquiry-form"
    ):
        tag.decompose()

    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if "All PhD Opportunities Pages" in heading.get_text(" ", strip=True):
            nxt = heading.find_next_sibling()
            if nxt and nxt.name in ("ul", "ol"):
                nxt.decompose()
            heading.decompose()

    meta = extract_findaphd_metadata(soup)
    header_lines = []
    if meta["institution"]:
        header_lines.append(f"Institution: {meta['institution']}")
    if meta["department"]:
        header_lines.append(f"Department: {meta['department']}")
    if meta["supervisors"]:
        header_lines.append(f"Supervisors: {', '.join(meta['supervisors'])}")
    if meta["closing_text"]:
        header_lines.append(f"Closing Date: {meta['closing_text']}")
    if meta["funding"]:
        header_lines.append(f"Funding: {meta['funding']}")

    desc_elem = soup.select_one(
        ".phd-sections__description, .phd-project-description, .project-description, "
        ".phd-programme-description, .programme-description, .course-description, .instProgDesc, "
        ".dept-desc, article, main"
    )
    if not desc_elem:
        desc_elem = soup.find("body") or soup

    for br in desc_elem.find_all("br"):
        br.replace_with("\n")
    for inline in desc_elem.find_all(INLINE_TAGS):
        inline.unwrap()
    desc_elem.smooth()

    raw_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in desc_elem.get_text("\n").splitlines()]
    lines = []
    in_subject_dir = False
    for ln in raw_lines:
        if not ln:
            continue
        if ln == "All PhD Opportunities Pages":
            in_subject_dir = True
            continue
        if in_subject_dir:
            if re.match(r"^[A-Za-z][A-Za-z ,&\-]+\(\d+\)$", ln):
                continue
            in_subject_dir = False
        if re.search(r"^(?:FREE\s+)?PhD\s+Study\s+Fair\b|^\|\s*REGISTER\s+NOW\b", ln, re.I):
            continue
        if re.match(r"^(?:Apply Online|Visit website)$", ln, re.I):
            continue
        lines.append(ln)

    cleaned_text = "\n\n".join(lines)
    cut_idx = cleaned_text.find("Register your interest for this PhD")
    if cut_idx != -1:
        cleaned_text = cleaned_text[:cut_idx].strip()
    if header_lines:
        header_block = "\n".join(header_lines)
        return f"{header_block}\n\n{cleaned_text}" if cleaned_text else header_block
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

def scrape_findaphd(conn, browser_or_context):
    base_url = get_target_url("FindAPhD_URL")
    if not base_url:
        print("Warning: FindAPhD_URL not found, skipping.", file=sys.stderr)
        return (0, 0)

    owns_context = False
    if hasattr(browser_or_context, "new_context"):
        context = browser_or_context.new_context()
        owns_context = True
    else:
        context = browser_or_context

    page_obj = context.new_page()

    page = 1
    pages_scanned = 0
    new_total = 0
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
        pages_scanned += 1

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
            if insert_job(
                conn, job_id, title, job_url, source="findaphd", description=snippet,
                deadline=parse_deadline(snippet), needs_full_description=True,
            ):
                new_on_page += 1
        conn.commit()
        new_total += new_on_page

        if not page_job_ids or page_job_ids.issubset(seen_this_run):
            print(f"[FindAPhD] No new listings on page {page} compared to current session. Reached end of pagination.", file=sys.stderr)
            break

        print(f"[FindAPhD] Page {page}: {len(page_job_ids)} listings found ({new_on_page} new to database).", file=sys.stderr)
        seen_this_run.update(page_job_ids)
        page += 1

    log_scrape_run(conn, "findaphd", base_url, pages_scanned, len(seen_this_run), new_total)
    conn.commit()

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

    def _apply_findaphd_detail(job_id, raw_html):
        desc_text = sanitise_html_text(raw_html)
        if not desc_text or is_cloudflare_blocked_text(desc_text):
            return False
        meta = extract_findaphd_metadata(raw_html)
        fields = {"description": desc_text, "needs_full_description": False}
        if meta["institution"]:
            fields["institution"] = meta["institution"]
        dl = meta["deadline"] or parse_deadline(desc_text)
        if dl:
            fields["deadline"] = dl
        update_job(conn, job_id, **fields)
        if meta["supervisors"]:
            sup_entries = [
                {"name": s, "institution": meta["institution"], "department": meta["department"]}
                for s in meta["supervisors"]
            ]
            link_supervisors_for_job(conn, job_id, sup_entries, default_institution=meta["institution"])
        conn.commit()
        return True

    rows = conn.execute(
        "SELECT id, url, status, description, needs_full_description FROM jobs WHERE url LIKE '%findaphd%' ORDER BY rowid"
    ).fetchall()
    for row in rows:
        needs_desc = (
            (row["status"] == "unreviewed" and row["needs_full_description"])
            or is_cloudflare_blocked_text(row["description"] or "")
        )
        if not needs_desc:
            continue
        job_id, job_url = row["id"], row["url"]
        print(f"[FindAPhD] Fetching full description for {job_url}...", file=sys.stderr)
        description_extracted = False

        # Fast Description Fetching via TLS Fingerprinting (curl_cffi)
        if curl_session:
            try:
                time.sleep(random.uniform(0.5, 1.5))
                resp = curl_session.get(job_url, timeout=12)
                if resp.status_code == 200 and not is_cloudflare_blocked_text(resp.text):
                    description_extracted = _apply_findaphd_detail(job_id, resp.text)
                elif resp.status_code in (403, 503):
                    curl_session = None
            except Exception as e:
                print(f"[FindAPhD] curl_cffi fetch failed ({e}), falling back to browser...", file=sys.stderr)
                curl_session = None

        # Fallback to browser navigation if curl_cffi did not extract description
        if not description_extracted:
            try:
                time.sleep(random.uniform(1.5, 3.0))
                page_obj.goto(job_url, wait_until="domcontentloaded")
                wait_for_cloudflare(page_obj, timeout_ms=20000)
                try:
                    page_obj.wait_for_selector(".phd-sections__description, .phd-project-description, .project-description, .phd-programme-description, .programme-description, .course-description, .instProgDesc", timeout=4000)
                except Exception:
                    pass
                page_obj.evaluate("window.scrollBy(0, 500)")
                time.sleep(0.5)
                _apply_findaphd_detail(job_id, page_obj.content())
            except Exception as e:
                print(f"[FindAPhD] Failed to fetch {job_url}: {e}", file=sys.stderr)

    page_obj.close()
    if owns_context:
        context.close()
    return (len(seen_this_run), new_total)

def scrape_jobsacuk(conn, browser_or_context):
    base_url = get_target_url("JobsAcUk_URL")
    if not base_url:
        print("Warning: JobsAcUk_URL not found, skipping.", file=sys.stderr)
        return (0, 0)

    owns_context = False
    if hasattr(browser_or_context, "new_context"):
        context = browser_or_context.new_context()
        owns_context = True
    else:
        context = browser_or_context

    page_obj = context.new_page()

    start_index = 1
    pages_scanned = 0
    new_jobs = {}
    seen_this_run = set()

    while True:
        url = base_url if start_index == 1 else f"{base_url}&pageSize=25&startIndex={start_index}"
        print(f"[JobsAcUk] Scraping search page (startIndex {start_index})...", file=sys.stderr)
        page_obj.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(3, 6))
        pages_scanned += 1

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
            if job_id not in new_jobs and not job_exists(conn, job_id):
                new_jobs[job_id] = {"title": title, "url": full_url}
                new_on_page += 1

        if not page_job_ids or page_job_ids.issubset(seen_this_run):
            print(f"[JobsAcUk] StartIndex {start_index} contains only previously seen listings from current session. Reached end of pagination.", file=sys.stderr)
            break

        print(f"[JobsAcUk] StartIndex {start_index}: {len(page_job_ids)} listings found ({new_on_page} new to database).", file=sys.stderr)
        seen_this_run.update(page_job_ids)
        start_index += 25

    for job_id, job in new_jobs.items():
        print(f"[JobsAcUk] Fetching full description for {job['url']}...", file=sys.stderr)
        description, deadline = "Failed to fetch.", None
        try:
            page_obj.goto(job["url"], wait_until="domcontentloaded")
            page_obj.evaluate("window.scrollBy(0, 500)")
            time.sleep(random.uniform(2, 4))
            page_obj.evaluate("window.scrollBy(0, 500)")
            clean_desc = sanitise_html_text(page_obj.content())
            description = clean_desc if clean_desc else "Failed to extract description."
            deadline = parse_deadline(clean_desc)
        except Exception as e:
            print(f"[JobsAcUk] Failed to fetch {job['url']}: {e}", file=sys.stderr)
        insert_job(conn, job_id, job["title"], job["url"], source="jobsacuk", description=description, deadline=deadline)
        conn.commit()
        time.sleep(random.uniform(5, 10))

    log_scrape_run(conn, "jobsacuk", base_url, pages_scanned, len(seen_this_run), len(new_jobs))
    conn.commit()

    page_obj.close()
    if owns_context:
        context.close()
    return (len(seen_this_run), len(new_jobs))

def _clean_stale_singleton_locks(profile_dir, force=False):
    """Removes stale Chrome SingletonLock/Socket/Cookie files in profile_dir.
    On macOS/Linux, SingletonLock is a symlink whose target ends with '-<pid>'.
    If force=False, only removes locks when the target PID is no longer alive.
    """
    lock_path = os.path.join(profile_dir, "SingletonLock")
    should_clean = force
    if not should_clean and (os.path.islink(lock_path) or os.path.exists(lock_path)):
        try:
            target = os.readlink(lock_path)
            pid_str = target.rsplit("-", 1)[-1]
            pid = int(pid_str)
            os.kill(pid, 0)  # Checks if process exists; raises OSError if dead
        except (OSError, ValueError):
            should_clean = True

    if should_clean:
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            p = os.path.join(profile_dir, name)
            if os.path.islink(p) or os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass
    return should_clean

def command_scrape():
    user_data_dir = BROWSER_PROFILE_DIR
    os.makedirs(user_data_dir, exist_ok=True)
    _clean_stale_singleton_locks(user_data_dir, force=False)
    launch_kwargs = {
        "user_data_dir": user_data_dir,
        "headless": False,
        "no_viewport": True,
    }

    with db_session() as conn, sync_playwright() as p:
        try:
            browser_or_context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
        except Exception as chrome_err:
            err_msg = str(chrome_err)
            if "Opening in existing browser session" in err_msg or "ProcessSingleton" in err_msg:
                print(
                    "[Scraper] Detected stale Chrome profile lock in .browser_profile; cleaning up and retrying once...",
                    file=sys.stderr,
                )
                _clean_stale_singleton_locks(user_data_dir, force=True)
                time.sleep(1)
                try:
                    browser_or_context = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
                except Exception as retry_err:
                    print(f"[Scraper] Error: Failed to launch system Google Chrome: {retry_err}", file=sys.stderr)
                    raise
            else:
                print(f"[Scraper] Error: Failed to launch system Google Chrome: {chrome_err}", file=sys.stderr)
                raise

        res_find = scrape_findaphd(conn, browser_or_context)
        res_jobs = scrape_jobsacuk(conn, browser_or_context)
        browser_or_context.close()

    if (
        isinstance(res_find, tuple) and len(res_find) == 2
        and isinstance(res_jobs, tuple) and len(res_jobs) == 2
    ):
        found_f, new_f = res_find
        found_j, new_j = res_jobs
        total_found = found_f + found_j
        total_new = new_f + new_j
        print(
            f"Scraping complete: {total_found} scraped ({found_f} findaphd, {found_j} jobsacuk), "
            f"{total_new} new ingested.",
            file=sys.stderr,
        )
    else:
        print("Scraping complete.", file=sys.stderr)

def _supervisor_label(sup):
    return sup["name"] + (f" ({sup['institution']})" if sup.get("institution") else "")

def command_update(job_ids, status=None, note=None, deadline=None, title=None,
                   reason=None, research_notes=None, institution=None, location=None):
    raw_ids = [job_ids] if isinstance(job_ids, str) else list(job_ids)
    job_id_list = list(dict.fromkeys(raw_ids))
    if not job_id_list:
        print("Error: Must provide at least one job ID to update.", file=sys.stderr)
        sys.exit(1)

    if not any([status, note, deadline, title, reason, research_notes, institution, location]):
        print("Error: Must provide at least one of --status, --note, --deadline, --title, --reason, "
              "--research-notes, --institution, or --location to update.", file=sys.stderr)
        sys.exit(1)

    norm_status = validate_status(status)

    with db_session() as conn:
        for jid in job_id_list:
            if not job_exists(conn, jid):
                print(f"Error: Job ID '{jid}' not found.", file=sys.stderr)
                sys.exit(1)

        fields = {}
        if norm_status:
            fields["status"] = norm_status
        if title:
            fields["title"] = clean_job_title(title)
        if deadline:
            fields["deadline"] = parse_deadline(deadline) or deadline
        if reason:
            fields["reason"] = reason
        if research_notes:
            fields["research_notes"] = research_notes
        if institution:
            fields["institution"] = institution
        if location:
            fields["location"] = location

        for jid in job_id_list:
            update_job(conn, jid, **fields)
            if note:
                add_timeline(conn, jid, note)

    if len(job_id_list) == 1:
        print(f"Successfully updated job '{job_id_list[0]}'.", file=sys.stderr)
    else:
        ids_str = ", ".join(job_id_list)
        print(f"Successfully updated {len(job_id_list)} jobs: {ids_str}.", file=sys.stderr)

def command_supervisor(job_id=None, name=None, academic_title=None, email=None, institution=None,
                       department=None, profile_url=None, notes=None, list_mode=False, search=None):
    if list_mode or (not job_id and not name):
        command_supervisors(search=search)
        return
    if not job_id:
        print("Error: Must provide a job_id to link a supervisor (or use --list to list supervisors).", file=sys.stderr)
        sys.exit(1)
    if not name:
        print("Error: --name must contain a supervisor name.", file=sys.stderr)
        sys.exit(1)
    with db_session() as conn:
        if not job_exists(conn, job_id):
            print(f"Error: Job ID '{job_id}' not found.", file=sys.stderr)
            sys.exit(1)
        sup_id = upsert_supervisor(
            conn, name, institution,
            academic_title=academic_title, email=email, department=department,
            profile_url=profile_url, research_notes=notes,
        )
        if not sup_id:
            print("Error: --name must contain a supervisor name.", file=sys.stderr)
            sys.exit(1)
        link_supervisor(conn, job_id, sup_id)
    print(f"Saved supervisor '{clean_supervisor_name(name)}' (id {sup_id}) and linked to job '{job_id}'.", file=sys.stderr)

def command_supervisors(search=None):
    with db_session() as conn:
        params = []
        where = ""
        if search:
            like = f"%{search}%"
            where = ("WHERE s.name LIKE ? OR s.institution LIKE ? OR s.department LIKE ? "
                     "OR s.email LIKE ? OR s.research_notes LIKE ?")
            params = [like] * 5
        rows = conn.execute(
            "SELECT s.*, GROUP_CONCAT(js.job_id, ', ') AS job_ids FROM supervisors s "
            f"LEFT JOIN job_supervisors js ON js.supervisor_id = s.id {where} "
            "GROUP BY s.id ORDER BY s.name",
            params,
        ).fetchall()

    header = f"Supervisors matching '{search}'" if search else "All Supervisors"
    print(f"\n=== {header} ({len(rows)} found) ===")
    for s in rows:
        title = f" — {s['academic_title']}" if s["academic_title"] else ""
        affiliation = ", ".join(x for x in (s["institution"], s["department"]) if x)
        print(f"\n[{s['id']}] {s['name']}{title}")
        if affiliation:
            print(f"  Affiliation: {affiliation}")
        if s["email"]:
            print(f"  Email: {s['email']}")
        if s["profile_url"]:
            print(f"  Profile: {s['profile_url']}")
        print(f"  Jobs: {s['job_ids'] or 'none'}")
        if s["research_notes"]:
            notes = s["research_notes"].replace("\n", " ")
            print(f"  Research Notes: {notes[:200]}{'...' if len(notes) > 200 else ''}")
    print()

def command_delete(job_id):
    with db_session() as conn:
        if not delete_job(conn, job_id):
            print(f"Error: Job ID '{job_id}' not found.", file=sys.stderr)
            sys.exit(1)
    print(f"Deleted job '{job_id}' (timeline and supervisor links removed; supervisor profiles kept).", file=sys.stderr)

def command_merge(keep_id, duplicate_id):
    with db_session() as conn:
        k_id = get_canonical_job_id(conn, keep_id)
        d_id = get_canonical_job_id(conn, duplicate_id)
        if not k_id or not job_exists(conn, k_id):
            print(f"Error: Target job '{keep_id}' not found.", file=sys.stderr)
            sys.exit(1)
        if not d_id or not job_exists(conn, d_id):
            print(f"Error: Duplicate job '{duplicate_id}' not found.", file=sys.stderr)
            sys.exit(1)
        if k_id == d_id:
            print(f"Error: '{keep_id}' and '{duplicate_id}' already resolve to the same job ('{k_id}').", file=sys.stderr)
            sys.exit(1)

        keep_job = get_job(conn, k_id)
        dup_job = get_job(conn, d_id)

        # 1. Transfer postings
        conn.execute(
            "INSERT OR IGNORE INTO job_postings (job_id, source, external_id, url, scraped_at) VALUES (?, ?, ?, ?, ?)",
            (k_id, dup_job["source"], d_id, dup_job["url"], dup_job.get("created_at") or now_iso()),
        )
        conn.execute("UPDATE job_postings SET job_id = ? WHERE job_id = ?", (k_id, d_id))

        # 2. Transfer supervisors
        dup_sups = conn.execute("SELECT supervisor_id FROM job_supervisors WHERE job_id = ?", (d_id,)).fetchall()
        for sup_row in dup_sups:
            link_supervisor(conn, k_id, sup_row["supervisor_id"])

        # 3. Transfer timeline entries, deduplicating identical notes
        existing_notes = {r["note"].strip() for r in get_timeline(conn, k_id)}
        dup_timeline = get_timeline(conn, d_id)
        for t in dup_timeline:
            if t["note"].strip() not in existing_notes:
                add_timeline(conn, k_id, t["note"], timestamp=t["timestamp"], touch=False)
                existing_notes.add(t["note"].strip())

        # 4. Enrich fields on keep_job if dup_job has cleaner or more complete data
        fields = {}
        if len(keep_job["title"]) > 100 and len(dup_job["title"]) < len(keep_job["title"]):
            fields["title"] = dup_job["title"]
        if not keep_job["institution"] and dup_job["institution"]:
            fields["institution"] = dup_job["institution"]
        if not keep_job["location"] and dup_job["location"]:
            fields["location"] = dup_job["location"]
        if not keep_job["deadline"] and dup_job["deadline"]:
            fields["deadline"] = dup_job["deadline"]
        if not keep_job["research_notes"] and dup_job["research_notes"]:
            fields["research_notes"] = dup_job["research_notes"]
        if fields:
            update_job(conn, k_id, **fields)

        add_timeline(conn, k_id, f"Merged duplicate job '{d_id}' into '{k_id}'")

        # 5. Delete duplicate job row
        conn.execute("DELETE FROM jobs WHERE id = ?", (d_id,))

    print(f"Successfully merged job '{duplicate_id}' into canonical job '{keep_id}'.", file=sys.stderr)

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

    added_count = 0
    with db_session() as conn:
        for job_id, job in jobs_dict.items():
            if job_exists(conn, job_id):
                continue
            desc = fold_description(job.get("description", ""), job.get("training"), job.get("trajectory"))
            institution = job.get("institution") or primary_institution(job.get("institutions"))
            insert_job(
                conn, job_id, job.get("title", ""), job.get("url", ""),
                source=job.get("source"), description=desc,
                deadline=job.get("deadline") or parse_deadline(desc),
                institution=institution, location=job.get("location"),
            )
            link_supervisors_for_job(conn, job_id, job.get("supervisors"), default_institution=institution)
            added_count += 1
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"Ingested {added_count} new jobs into database (total database size: {total}).", file=sys.stderr)

def command_summary():
    with db_session() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        counts = conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY n DESC, status"
        ).fetchall()
        last_runs = conn.execute(
            "SELECT ran_at, source, total_found, new_jobs_added FROM scrape_runs "
            "WHERE id IN (SELECT MAX(id) FROM scrape_runs GROUP BY source) ORDER BY source"
        ).fetchall()
        sup_count = conn.execute("SELECT COUNT(*) FROM supervisors").fetchone()[0]

    print(f"\n{'='*20} AI PhD Search Summary {'='*20}")
    print(f"Total Jobs in Database: {total}")
    print(f"Supervisor Profiles: {sup_count}")
    for lr in last_runs:
        print(f"Last Scrape ({lr['source']}): {lr['ran_at'][:19]} "
              f"({lr['total_found']} found, {lr['new_jobs_added']} new)")
    print(f"{'-'*55}")
    for row in counts:
        print(f"  • {row['status']:<18} : {row['n']} jobs")
    print(f"{'='*55}\n")

def command_list(status=None, urgent=False, supervisors=False, search=None, full=False):
    if supervisors:
        command_supervisors(search=search)
        return
    norm_status = validate_status(status)
    with db_session() as conn:
        if norm_status:
            where, params = "WHERE status = ?", [norm_status]
        else:
            where, params = "WHERE status != 'rejected'", []
        order = "ORDER BY deadline IS NULL, deadline ASC, rowid" if urgent else "ORDER BY rowid"
        rows = conn.execute(f"SELECT * FROM jobs {where} {order}", params).fetchall()
        matches = []
        for row in rows:
            sups = get_job_supervisors(conn, row["id"])
            latest = conn.execute(
                "SELECT note, timestamp FROM timeline WHERE job_id = ? ORDER BY id DESC LIMIT 1", (row["id"],)
            ).fetchone()
            matches.append((row, sups, latest))

    urgent_tag = " [Sorted by Nearest Deadline]" if urgent else ""
    header = f"Jobs with Status '{norm_status}'{urgent_tag}" if norm_status else f"Active Tracked Jobs (Excluding Rejected){urgent_tag}"
    print(f"\n=== {header} ({len(matches)} found) ===")
    if not matches:
        print("No matching jobs found.\n")
        return

    for row, sups, latest in matches:
        print(f"\n[{row['id']}] {row['title'] or 'Untitled'}")
        inst_str = f" | Institution: {row['institution']}" if row["institution"] else ""
        loc_str = f" ({row['location']})" if row["location"] else ""
        dl_str = f" | Deadline: {row['deadline']}" if row["deadline"] else " | Deadline: Unstated"
        print(f"  Status: {row['status']}{inst_str}{loc_str}{dl_str} | URL: {row['url']}")
        if sups:
            print(f"  Supervisors: {', '.join(_supervisor_label(s) for s in sups)}")
        if row["reason"]:
            print(f"  Reason: {row['reason']}")
        if latest:
            print(f"  Latest Note: {latest['note']} ({latest['timestamp'][:10]})")
        if full and row["description"]:
            print(f"  Description:\n    " + "\n    ".join(row["description"].splitlines()))
    print()

def command_show(job_id):
    with db_session() as conn:
        j = get_job(conn, job_id)
        if not j:
            print(f"Error: Job ID '{job_id}' not found in database.", file=sys.stderr)
            sys.exit(1)
        canon_id = j["id"]
        postings = get_job_postings(conn, canon_id)
        sups = get_job_supervisors(conn, canon_id)
        timeline = get_timeline(conn, canon_id)

    print(f"\n{'='*70}")
    print(f"JOB ID: {canon_id}")
    if job_id != canon_id:
        print(f"ALIAS:  {job_id}")
    print(f"TITLE:  {j['title']}")
    print(f"STATUS: {j['status']}")
    print(f"SOURCE: {j['source']}")
    if j["institution"]:
        print(f"INSTITUTION: {j['institution']}")
    if j["location"]:
        print(f"LOCATION: {j['location']}")
    if j["deadline"]:
        print(f"DEADLINE: {j['deadline']}")
    if postings and len(postings) > 1:
        print("\nPOSTINGS & URLS:")
        for p in postings:
            print(f"  • [{p['source']}] (id: {p['external_id']}) {p['url']}")
    else:
        print(f"URL:    {j['url']}")
    if j["reason"]:
        print(f"REASON: {j['reason']}")

    if sups:
        print("\nSUPERVISORS:")
        for s in sups:
            details = [f"[{s['id']}] {s['name']}"]
            if s["academic_title"]:
                details.append(s["academic_title"])
            affiliation = ", ".join(x for x in (s["institution"], s["department"]) if x)
            if affiliation:
                details.append(affiliation)
            details.append(f"Email: {s['email'] or 'N/A'}")
            print(f"  • {' | '.join(details)}")
            if s["profile_url"]:
                print(f"    Profile: {s['profile_url']}")
            if s["research_notes"]:
                print(f"    Research Notes: {s['research_notes']}")

    if timeline:
        print("\nTIMELINE:")
        for t in timeline:
            print(f"  • [{t['timestamp'][:19]}] {t['note']}")

    if j["research_notes"]:
        print(f"\nRESEARCH NOTES:\n{j['research_notes']}")

    if j["description"]:
        print(f"\nDESCRIPTION:\n{j['description']}")
    print(f"{'='*70}\n")

def main():
    parser = argparse.ArgumentParser(description="AI PhD Search CLI")
    parser.add_argument("--data-dir", help="Directory for user_profile.md, jobs.db, and .browser_profile (useful for isolated E2E tests)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scrape", help="Scrape new jobs and add to database")

    update_cmd = subparsers.add_parser("update", help="Update a job's fields and/or add a timeline note")
    update_cmd.add_argument("job_ids", nargs="+", metavar="job_id", help="One or more job IDs to update")
    update_cmd.add_argument("--status", help="New status for the job")
    update_cmd.add_argument("--note", help="Note to append to the job's timeline")
    update_cmd.add_argument("--deadline", help="Application deadline date (YYYY-MM-DD)")
    update_cmd.add_argument("--title", help="Updated clean title for the job")
    update_cmd.add_argument("--reason", help="Fit / evaluation rationale")
    update_cmd.add_argument("--research-notes", dest="research_notes", help="Project research notes from /research (replaces existing)")
    update_cmd.add_argument("--institution", help="Host institution")
    update_cmd.add_argument("--location", help="City / campus")

    sup_cmd = subparsers.add_parser("supervisor", help="Create, enrich, or list supervisor profiles")
    sup_cmd.add_argument("job_id", nargs="?", default=None, help="The ID of the job this supervisor is attached to")
    sup_cmd.add_argument("--name", help="Supervisor name (honorifics like Dr/Prof are stripped)")
    sup_cmd.add_argument("--title", dest="academic_title", help="Academic title, e.g. Professor, Lecturer")
    sup_cmd.add_argument("--email", help="Email address")
    sup_cmd.add_argument("--institution", help="University / organisation")
    sup_cmd.add_argument("--department", help="Department / school")
    sup_cmd.add_argument("--url", dest="profile_url", help="Staff page or Google Scholar URL")
    sup_cmd.add_argument("--notes", help="Research interests, lab, key publications (replaces existing)")
    sup_cmd.add_argument("--list", action="store_true", help="List supervisor profiles and their linked jobs")
    sup_cmd.add_argument("--search", help="Filter supervisors by name, institution, department, email, or notes")

    sups_cmd = subparsers.add_parser("supervisors", help="List supervisor profiles and their linked jobs (alias for 'list --supervisors')")
    sups_cmd.add_argument("--search", help="Filter by name, institution, department, email, or notes")

    delete_cmd = subparsers.add_parser("delete", help="Delete a job (cascades to its timeline and supervisor links)")
    delete_cmd.add_argument("job_id", help="The ID of the job to delete")

    merge_cmd = subparsers.add_parser("merge", help="Merge a duplicate job into a canonical job")
    merge_cmd.add_argument("keep_id", help="Canonical job ID to keep")
    merge_cmd.add_argument("duplicate_id", help="Duplicate job ID to merge and delete")

    ingest_cmd = subparsers.add_parser("ingest", help="Ingest external or portal jobs into database as unreviewed")
    ingest_cmd.add_argument("jobs_file", help="JSON file containing jobs to ingest")

    subparsers.add_parser("summary", help="Print summary counts of all jobs in the database by status")

    list_cmd = subparsers.add_parser("list", help="List jobs filtered by status (defaults to all non-rejected jobs)")
    list_cmd.add_argument("--status", help="Status to filter by (e.g. pending, shortlisted, applied)")
    list_cmd.add_argument("--urgent", action="store_true", help="Sort active jobs by nearest application deadline")
    list_cmd.add_argument("--supervisors", action="store_true", help="List supervisor profiles instead of jobs")
    list_cmd.add_argument("--search", help="Filter supervisors by query string (used with --supervisors)")
    list_cmd.add_argument("--full", action="store_true", help="Include full project description and complete metadata for each listed job")

    show_cmd = subparsers.add_parser("show", help="Show complete record, supervisors, and timeline for a specific job")
    show_cmd.add_argument("job_id", help="The ID of the job to display")

    args = parser.parse_args()
    if args.data_dir:
        set_data_dir(args.data_dir)

    if args.command == "scrape":
        command_scrape()
    elif args.command == "update":
        command_update(args.job_ids, args.status, args.note, args.deadline, args.title,
                       args.reason, args.research_notes, args.institution, args.location)
    elif args.command == "supervisor":
        command_supervisor(args.job_id, args.name, args.academic_title, args.email, args.institution,
                           args.department, args.profile_url, args.notes,
                           list_mode=args.list, search=args.search)
    elif args.command == "supervisors":
        command_supervisors(args.search)
    elif args.command == "delete":
        command_delete(args.job_id)
    elif args.command == "merge":
        command_merge(args.keep_id, args.duplicate_id)
    elif args.command == "ingest":
        command_ingest(args.jobs_file)
    elif args.command == "summary":
        command_summary()
    elif args.command == "list":
        command_list(args.status, args.urgent, supervisors=args.supervisors, search=args.search, full=args.full)
    elif args.command == "show":
        command_show(args.job_id)

if __name__ == "__main__":
    main()
