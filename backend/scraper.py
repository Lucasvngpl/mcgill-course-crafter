import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from db_connection import Session
from db_setup import Course

BASE_URL = "https://coursecatalogue.mcgill.ca/courses/"

def fetch_html(url: str, retries: int = 3) -> str:
    """Fetch HTML content from a URL with retry logic."""
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            time.sleep(0.5)  # Be polite and avoid overwhelming the server
            return response.text
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                print(f"      ⏱️  Timeout, retrying ({attempt + 1}/{retries})...")
                time.sleep(2)
            else:
                raise
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                print(f"      ⚠️  Network error, retrying ({attempt + 1}/{retries})...")
                time.sleep(2)
            else:
                raise
    return ""

def parse_course_list(html: str) -> list[str]:
    """Parse the main course list page to extract course links."""
    soup = BeautifulSoup(html, 'html.parser')
    course_links = []

    # look for anchor tags whose href starts with "/courses/<some-course>"
    for a in soup.select('a[href^="/courses/"]'):
        href = a['href']
        # match lowercase or uppercase course codes + optional index.html
        if re.match(r"^/courses/[A-Za-z]{4}-\d{3}(/index\.html)?$", href):
            # normalize URL (strip trailing /index.html)
            href = re.sub(r"/index\.html$", "", href)
            course_links.append(urljoin(BASE_URL, href))
    return list(set(course_links))  # Remove duplicates

def parse_course_page(html: str, url: str = "") -> dict:
    """Parse an individual course page to extract course details."""
    soup = BeautifulSoup(html, 'html.parser')
    course_data = {}

    # Extract course code and title
    title_tag = soup.find('title')
    if title_tag:
        # Try first pattern: "COMP 273. Introduction to Computer Systems. | McGill..."
        match = re.match(r'([A-Z]{3,4}[- ]?\d{3}[A-Z]?)\.\s+(.+?)\s+\|', title_tag.text.strip())
        if match:
            course_data['id'] = match.group(1).replace('-', ' ')   # e.g., "COMP 273"
            course_data['title'] = match.group(2).strip()  # e.g., "Introduction to Computer Systems."
        else:
            # Try alternate pattern: "COMP 273 - Introduction to Computer Systems | McGill..."
            match = re.match(r'([A-Z]{3,4}[- ]?\d{3}[A-Z]?)\s*[-–]\s*(.+?)\s+\|', title_tag.text.strip())
            if match:
                course_data['id'] = match.group(1).replace('-', ' ')
                course_data['title'] = match.group(2).strip()

    # Fallback: Extract ID from URL if not found in page
    if 'id' not in course_data and url:
        match = re.search(r'/courses/([a-z]{3,4})-(\d{3}[a-z]?)/?', url, re.IGNORECASE)
        if match:
            dept, num = match.groups()
            course_data['id'] = f"{dept.upper()} {num.upper()}"

    # Set default values for required fields if they're missing
    if 'id' not in course_data:
        course_data['id'] = "UNKNOWN"
    if 'title' not in course_data:
        course_data['title'] = "Untitled Course"


    # Extract description
    desc_tag = soup.find('div', class_='section__content')
    if desc_tag:
        course_data['description'] = desc_tag.text.strip()
    else:
        course_data['description'] = "No description available"  # Default value


    # Extract credits
    credits_tag = soup.find('div', class_='text detail-credits')
    if credits_tag:
        credits_text = credits_tag.get_text(strip=True)  # e.g., "Credits: 3.0"
        match = re.search(r'(\d+\.?\d*)', credits_text)
        if match:
            course_data['credits'] = float(match.group(1))
        else:
            course_data['credits'] = 0.0  # fallback
    else:
        course_data['credits'] = 0.0  # fallback
        
  
    # Extract "offered by"
    offered_by_tag = soup.find('div', class_='text detail-offered_by margin--tiny')
    if offered_by_tag:
        value_span = offered_by_tag.find('span', class_='value')
        if value_span:
            course_data['offered_by'] = value_span.text.strip()
    # Add this default value
    else:
        course_data['offered_by'] = f"{course_data.get('id', '').split()[0]} Department"


    # Extract offerings
    offerings = {'offered_fall': False, 'offered_winter': False, 'offered_summer': False}
    terms_tag = soup.select_one('div.detail-terms_offered span.value')
    if terms_tag:
        terms_text = terms_tag.get_text(strip=True)
        if 'Fall' in terms_text:
            offerings['offered_fall'] = True
        if 'Winter' in terms_text:
            offerings['offered_winter'] = True
        if 'Summer' in terms_text:
            offerings['offered_summer'] = True
    course_data.update(offerings)


    # Extract prerequisites
    prereq_edges = []
    prereq_text = ""  # <-- Initialize safely
    
    # First, try to find in detail-note_text (newer format)
    note_div = soup.find('div', class_='detail-note_text')
    if note_div:
        for li in note_div.find_all('li'):
            li_text = li.get_text(strip=True)
            # Match various prerequisite patterns
            if re.match(r'Prerequisite[s()\s]*:', li_text, re.I):
                prereq_text = li_text
                break
    
    # Fallback: old method
    if not prereq_text:
        prereq_tag = soup.find(text=re.compile(r'Prerequisite[\s(s)]*:', re.I))
        if prereq_tag:
            prereq_text = prereq_tag.parent.text.strip()
    
    # Extract course codes from prereq text
    if prereq_text:
        prereq_courses = re.findall(r'([A-Z]{3,4}[- ]?\d{3})', prereq_text)
        for prereq in prereq_courses:
            prereq_edges.append({'src_course_id': prereq, 'dst_course_id': course_data.get('id'), 'kind': 'prereq',})
    
    # Extract corequisites (if any)
    coreq_edges = []
    coreq_text = ""  # <-- Initialize safely
    
    # First, try to find in detail-note_text (newer format)
    if note_div:
        for li in note_div.find_all('li'):
            li_text = li.get_text(strip=True)
            if re.match(r'Corequisite[s()\s]*:', li_text, re.I):
                coreq_text = li_text
                break
    
    # Fallback: old method
    if not coreq_text:
        coreq_tags = soup.find_all(text=re.compile(r'Corequisite[\s(s)]*:', re.I))
        for coreq_tag in coreq_tags:
            coreq_text = coreq_tag.parent.text.strip()
            break
    
    # Extract course codes from coreq text
    if coreq_text:
        coreq_courses = re.findall(r'([A-Z]{3,4}[- ]?\d{3})', coreq_text)
        for coreq in coreq_courses:
            coreq_edges.append({'src_course_id': coreq, 'dst_course_id': course_data.get('id'), 'kind': 'coreq',})
    
    # Add to output
    course_data['prereq_edges'] = prereq_edges
    course_data['coreq_edges'] = coreq_edges
    course_data['prereq_text'] = prereq_text
    course_data['coreq_text'] = coreq_text
    return course_data

def get_all_course_links() -> list[str]:
    """Get all course links directly from the main catalog page."""
    print("Fetching main catalog page...")
    main_html = fetch_html(BASE_URL)
    soup = BeautifulSoup(main_html, 'html.parser')
    
    course_links = []
    seen_courses = set()  # Track unique course codes to avoid duplicates
    
    # Look for all links on the page
    for a in soup.find_all('a', href=True):
        href = a['href']
        
        # Check if it matches our course pattern - be more specific
        if re.match(r"^/courses/[a-z]{3,4}-\d{3}[a-z]?(/index\.html)?$", href, re.IGNORECASE):
            # Extract the course code from the URL (e.g., "comp-202" -> "COMP 202")
            match = re.search(r'/courses/([a-z]{3,4})-(\d{3}[a-z]?)/?', href, re.IGNORECASE)
            if match:
                dept, num = match.groups()
                course_code = f"{dept.upper()} {num}"
                
                # Skip if we've seen this course already
                if course_code in seen_courses:
                    continue
                    
                seen_courses.add(course_code)
                full_url = urljoin(BASE_URL, href)
                course_links.append(full_url)
                
                # Print first 5 courses for debugging
                if len(course_links) <= 5:
                    print(f"Found course: {course_code} - {full_url}")
    
    print(f"Total unique courses found: {len(course_links)}")
    return course_links

def scrape_and_update_db():
    """Scrape all courses and update the database."""
    from db_connection import Session
    from db_setup import Course
    
    print("=" * 60)
    print("McGill Course Scraper")
    print("=" * 60)
    
    # Get all course links
    course_links = get_all_course_links()
    total = len(course_links)
    
    if total == 0:
        print("No courses found! Check the scraper.")
        return
    
    print(f"\nStarting to scrape {total} courses...")
    print("-" * 60)
    
    updated = 0
    created = 0
    errors = 0
    
    with Session() as session:
        for i, url in enumerate(course_links, 1):
            try:
                # Progress update every 50 courses
                if i % 50 == 0 or i == 1:
                    print(f"[{i}/{total}] Processing... ({100*i//total}%)")
                
                html = fetch_html(url)
                data = parse_course_page(html, url)
                
                course_id = data.get('id')
                if not course_id or course_id == "UNKNOWN":
                    print(f"  ⚠️  Skipping {url} - no valid ID")
                    errors += 1
                    continue
                
                # Check if course exists
                course = session.query(Course).filter_by(id=course_id).first()
                
                if course:
                    # Update existing course
                    course.title = data.get('title', course.title)
                    course.description = data.get('description', course.description)
                    course.credits = data.get('credits', course.credits)
                    course.offered_by = data.get('offered_by', course.offered_by)
                    course.offered_fall = data.get('offered_fall', course.offered_fall)
                    course.offered_winter = data.get('offered_winter', course.offered_winter)
                    course.offered_summer = data.get('offered_summer', course.offered_summer)
                    course.prereq_text = data.get('prereq_text', course.prereq_text)
                    course.coreq_text = data.get('coreq_text', course.coreq_text)
                    updated += 1
                else:
                    # Create new course
                    course = Course(
                        id=course_id,
                        title=data.get('title', 'Unknown'),
                        description=data.get('description', ''),
                        credits=data.get('credits', 0.0),
                        offered_by=data.get('offered_by', ''),
                        offered_fall=data.get('offered_fall', False),
                        offered_winter=data.get('offered_winter', False),
                        offered_summer=data.get('offered_summer', False),
                        prereq_text=data.get('prereq_text', ''),
                        coreq_text=data.get('coreq_text', ''),
                    )
                    session.add(course)
                    created += 1
                
                # Commit every 100 courses
                if i % 100 == 0:
                    session.commit()
                    print(f"  ✓ Committed batch (updated: {updated}, created: {created})")
                    
            except Exception as e:
                print(f"  ❌ Error scraping {url}: {e}")
                errors += 1
                continue
        
        # Final commit
        session.commit()
    
    print("-" * 60)
    print(f"✅ Scraping complete!")
    print(f"   Updated: {updated}")
    print(f"   Created: {created}")
    print(f"   Errors:  {errors}")
    print("=" * 60)

def scrape_missing_only():
    """Only scrape courses that have placeholder titles or missing prereqs."""
    from db_connection import Session
    from db_setup import Course
    from sqlalchemy import or_
    
    print("=" * 60)
    print("🔍 McGill Course Scraper - UPDATE MISSING DATA ONLY")
    print("=" * 60)
    
    # Find courses that need updating
    with Session() as session:
        missing = session.query(Course).filter(
            or_(
                Course.title.like('%Placeholder%'),
                Course.prereq_text.is_(None),
                Course.prereq_text == ''
            )
        ).all()
        
        course_ids = [c.id for c in missing]
    
    total = len(course_ids)
    print(f"Found {total} courses with missing data")
    
    if not course_ids:
        print("✅ All courses have complete data!")
        return
    
    print("-" * 60)
    
    updated = 0
    skipped = 0
    errors = 0
    
    with Session() as session:
        for i, course_id in enumerate(course_ids, 1):
            # Build URL from course ID (e.g., "COMP 250" -> "comp-250")
            url_slug = course_id.lower().replace(' ', '-')
            url = f"https://coursecatalogue.mcgill.ca/courses/{url_slug}/"
            
            print(f"({i}/{total}) 📄 Fetching {course_id}...")
            
            try:
                html = fetch_html(url)
                data = parse_course_page(html, url)
                
                # Check if we got valid data
                if not data or data.get('title') == 'Untitled Course':
                    print(f"   ⚠️  No valid data found for {course_id}, skipping.")
                    skipped += 1
                    continue
                
                # Update existing course
                course = session.query(Course).filter_by(id=course_id).first()
                if course:
                    old_title = course.title
                    course.title = data.get('title', course.title)
                    course.description = data.get('description', course.description)
                    course.credits = data.get('credits', course.credits)
                    course.offered_by = data.get('offered_by', course.offered_by)
                    course.offered_fall = data.get('offered_fall', course.offered_fall)
                    course.offered_winter = data.get('offered_winter', course.offered_winter)
                    course.offered_summer = data.get('offered_summer', course.offered_summer)
                    course.prereq_text = data.get('prereq_text', course.prereq_text)
                    course.coreq_text = data.get('coreq_text', course.coreq_text)
                    
                    print(f"   💾 Updated: {course_id} - {data.get('title', 'Unknown')}")
                    if data.get('prereq_text'):
                        print(f"      Prereqs: {data.get('prereq_text')[:60]}...")
                    updated += 1
                
                # Commit every 50 courses
                if i % 50 == 0:
                    session.commit()
                    print(f"   ✅ Committed batch ({updated} updated so far)")
                    
            except Exception as e:
                print(f"   ❌ Error scraping {course_id}: {e}")
                errors += 1
                continue
        
        # Final commit
        session.commit()
    
    print("-" * 60)
    print(f"✅ Update complete!")
    print(f"   Updated: {updated}")
    print(f"   Skipped: {skipped}")
    print(f"   Errors:  {errors}")
    print("=" * 60)


if __name__ == "__main__":
    scrape_missing_only()