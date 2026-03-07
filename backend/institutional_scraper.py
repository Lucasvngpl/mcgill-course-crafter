#!/usr/bin/env python3
"""
institutional_scraper.py — Scrapes McGill undergraduate program requirements
from the Course Catalogue and saves them as JSON files.

Run from the backend/ directory:
    python institutional_scraper.py              # scrape all majors/honours
    python institutional_scraper.py science      # test with Science faculty only

Each program is saved to:
    institutional_data/programs/{faculty}_{program-slug}.json

Programs are skipped if the file already exists (aggressive caching).
To re-scrape a program, delete its JSON file and re-run.

How it works:
1. Fetch the main undergraduate index page — its navigation tree contains a
   complete sitemap of every program URL (all ~1266 of them in one request).
2. Filter to major/honours programs only (skip minors, concentrations, etc.)
3. For each program URL, parse:
   - #programoverviewtextcontainer → faculty name + program description
   - #coursestextcontainer        → required and complementary course codes
4. Save as JSON. No LLM needed — the HTML structure is clean enough.
"""

import json
import os
import re
import sys
import time
import pathlib
import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────────

BASE_URL = "https://coursecatalogue.mcgill.ca"
UNDERGRAD_INDEX = f"{BASE_URL}/en/undergraduate/"

# Output directory (relative to this file)
OUTPUT_DIR = pathlib.Path(__file__).parent / "institutional_data" / "programs"

# Mimic a real browser so we don't get blocked
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Polite delay between requests (seconds). McGill's servers are not fast.
REQUEST_DELAY = 0.5

# Program types to INCLUDE — anything with these strings in the URL slug.
# We skip: minor, concentration, certificate, diploma, component (core components of joint programs)
INCLUDE_TYPE_KEYWORDS = {"major", "honours"}


# ── Step 1: Discover all program URLs ───────────────────────────────────────

def get_all_program_urls(faculty_filter: str = None) -> list[str]:
    """
    Fetch the undergraduate index page and extract all program page URLs.

    The page's navigation embeds a complete sitemap of all programs as a <ul>
    tree. We grab all depth-7 hrefs (individual program pages) and filter to
    the program types we care about.

    A URL looks like:
      /en/undergraduate/science/programs/computer-science/computer-science-major-bsc/
      depth:  1  2           3      4        5               6                         7 slashes

    Args:
        faculty_filter: If set, only return URLs for that faculty slug (e.g. "science").
                        Useful for testing one faculty before running all.
    """
    print(f"Fetching programme URL list from {UNDERGRAD_INDEX} ...")
    resp = requests.get(UNDERGRAD_INDEX, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract every href that looks like a program page (7 slashes = depth 7)
    all_links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if href.startswith("/en/undergraduate/") and href.count("/") == 7:
            all_links.add(href)

    print(f"Found {len(all_links)} total depth-7 URLs in the nav tree.")

    # Filter to major/honours programs
    filtered = []
    for link in sorted(all_links):
        slug = link.rstrip("/").split("/")[-1]  # last path segment
        if any(kw in slug for kw in INCLUDE_TYPE_KEYWORDS):
            filtered.append(link)

    print(f"After filtering to major/honours: {len(filtered)} programs.")

    # Optionally restrict to one faculty for testing
    if faculty_filter:
        filtered = [u for u in filtered if f"/undergraduate/{faculty_filter}/" in u]
        print(f"After faculty filter ({faculty_filter!r}): {len(filtered)} programs.")

    return filtered


# ── Step 2: Parse a single program page ─────────────────────────────────────

def parse_program_page(url: str) -> dict | None:
    """
    Fetch and parse one program page, returning a structured dict.

    The page has three tab panels:
      #textcontainer                → (often empty in practice)
      #programoverviewtextcontainer → faculty, degree, description
      #coursestextcontainer         → required + complementary course tables

    Course codes live in <td class="codecol"> within <table class="sc_courselist">.
    The section heading (h2) tells us whether a course is required or complementary.

    Returns None if the page 404s or lacks the expected structure.
    """
    full_url = BASE_URL + url
    resp = requests.get(full_url, headers=HEADERS, timeout=30)

    if resp.status_code == 404:
        print(f"  404: {url}")
        return None

    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Soft 404 check — some 404s return HTTP 200 with a "Page Not Found" title
    title_tag = soup.title
    if not title_tag or "Page Not Found" in (title_tag.string or ""):
        print(f"  Soft 404 (Page Not Found in title): {url}")
        return None

    # ── Program name ────────────────────────────────────────────────────────
    h1 = soup.find("h1", class_="page-title")
    program_name = h1.get_text(strip=True) if h1 else ""

    # ── Faculty and description ──────────────────────────────────────────────
    # #programoverviewtextcontainer typically starts with:
    # "Offered by: <unit> (<Faculty Name>) Degree: ... Program Description <text>"
    faculty = ""
    description = ""
    overview = soup.find(id="programoverviewtextcontainer")
    if overview:
        raw = overview.get_text(separator=" ", strip=True)

        # Extract faculty from "Offered by: Unit (Faculty Name)"
        offered_match = re.search(
            r"Offered by:\s*(.+?)(?:Degree:|Program credit weight|$)", raw
        )
        if offered_match:
            offered_by = offered_match.group(1).strip()
            # Faculty name is usually in parentheses: "Computer Science (Faculty of Science)"
            fac_match = re.search(r"\(([^)]+)\)", offered_by)
            faculty = fac_match.group(1).strip() if fac_match else offered_by

        # Extract the narrative description that follows "Program Description"
        desc_match = re.search(
            r"Program Description\s+(.+?)(?:Quick links|Advisors|Student Advisors|$)",
            raw,
            re.DOTALL,
        )
        if desc_match:
            description = " ".join(desc_match.group(1).split())  # normalize whitespace

    # ── Required and complementary courses ──────────────────────────────────
    # Walk the #coursestextcontainer, tracking the current h2 section heading.
    # When we're under a "Required" heading, collect codes into required_courses.
    # When under "Complementary" or "Elective", collect into complementary_courses.
    required_courses: list[str] = []
    complementary_courses: list[str] = []

    courses_div = soup.find(id="coursestextcontainer")
    if courses_div:
        current_section = None  # "required" | "complementary" | None

        for el in courses_div.find_all(["h2", "h3", "h4", "td"]):
            if el.name in ("h2", "h3", "h4"):
                heading_lower = el.get_text(strip=True).lower()
                if "required" in heading_lower:
                    current_section = "required"
                elif any(kw in heading_lower for kw in ("complementary", "elective", "restricted")):
                    current_section = "complementary"
                else:
                    # Sub-headings within a section (e.g. "Group A") don't reset the section
                    pass

            elif el.name == "td" and "codecol" in el.get("class", []):
                code = el.get_text(strip=True)
                # Only collect well-formed course codes like "COMP 250" or "MATH 223"
                # (avoid or-separators and other non-course text)
                if re.match(r"^[A-Z]{3,4}\s+\d{3}[A-Z]?$", code):
                    if current_section == "required":
                        required_courses.append(code)
                    elif current_section == "complementary":
                        complementary_courses.append(code)

    # ── Infer program type from URL slug ────────────────────────────────────
    slug = url.rstrip("/").split("/")[-1]
    if "joint-honours" in slug:
        program_type = "joint_honours"
    elif "honours" in slug:
        program_type = "honours"
    else:
        program_type = "major"

    return {
        "faculty": faculty,
        "program_name": program_name,
        "program_type": program_type,
        "description": description,
        "required_courses": required_courses,
        "complementary_courses": complementary_courses,
        "source_url": full_url,
    }


# ── Step 3: URL → filename slug ──────────────────────────────────────────────

def slug_from_url(url: str) -> str:
    """
    Convert a program URL path to a safe filename.

    /en/undergraduate/science/programs/computer-science/computer-science-major-bsc/
    →  science_computer-science-major-bsc
    """
    parts = url.strip("/").split("/")
    # parts[2] = faculty slug (e.g. "science")
    # parts[-1] = program slug (e.g. "computer-science-major-bsc")
    return f"{parts[2]}_{parts[-1]}"


# ── Main ─────────────────────────────────────────────────────────────────────

def main(faculty_filter: str = None):
    """
    Scrape all major/honours programs and save them as JSON files.

    Args:
        faculty_filter: Optional faculty slug to limit scope (e.g. "science").
                        If None, scrapes all faculties.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    urls = get_all_program_urls(faculty_filter)
    total = len(urls)

    saved = 0
    skipped = 0
    failed = 0

    for i, url in enumerate(urls, 1):
        slug = slug_from_url(url)
        output_file = OUTPUT_DIR / f"{slug}.json"

        # Skip if already scraped (delete the file to force re-scrape)
        if output_file.exists():
            print(f"[{i}/{total}] SKIP (cached): {slug}")
            skipped += 1
            continue

        print(f"[{i}/{total}] Scraping: {slug} ...")

        try:
            program = parse_program_page(url)
            if program:
                with open(output_file, "w") as f:
                    json.dump(program, f, indent=2)
                req = len(program["required_courses"])
                comp = len(program["complementary_courses"])
                print(f"  OK — {req} required, {comp} complementary courses.")
                saved += 1
            else:
                failed += 1  # parse_program_page already printed the reason
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

        # Polite delay between requests
        time.sleep(REQUEST_DELAY)

    print(f"\n{'='*50}")
    print(f"Done. Saved: {saved} | Skipped (cached): {skipped} | Failed: {failed}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    # Optional: pass a faculty slug as a CLI arg for targeted scraping
    # e.g.  python institutional_scraper.py science
    faculty_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(faculty_arg)
