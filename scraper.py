import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://coursecatalogue.mcgill.ca/courses/"

def fetch_html(url: str) -> str:
    """Fetch HTML content from a URL."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()  # Raise an error for bad responses
    time.sleep(0.5)  # Be polite and avoid overwhelming the server
    return response.text

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
    prereq_tag = soup.find(text=re.compile(r'Prerequisite[s]?:', re.I))
    if prereq_tag:
        prereq_text = prereq_tag.parent.text.strip()
        prereq_courses = re.findall(r'([A-Z]{4}[- ]?\d{3})', prereq_text)
        for prereq in prereq_courses:
            prereq_edges.append({'src_course_id': prereq, 'dst_course_id': course_data.get('id'), 'kind': 'prereq',})
    
    # Extract corequisites (if any)
    coreq_edges = []
    coreq_text = ""  # <-- Initialize safely
    coreq_tags = soup.find_all(text=re.compile(r'Corequisite[s]?:', re.I))
    for coreq_tag in coreq_tags:
        coreq_text = coreq_tag.parent.text.strip()
        coreq_courses = re.findall(r'([A-Z]{4}[- ]?\d{3})', coreq_text)
        for coreq in coreq_courses:
            coreq_edges.append({'src_course_id': coreq, 'dst_course_id': course_data.get('id'), 'kind': 'coreq',})
    
    # Add to output
    course_data['prereq_edges'] = prereq_edges
    course_data['coreq_edges'] = coreq_edges
    course_data['prereq_text'] = prereq_text
    course_data['coreq_text'] = coreq_text
    return course_data

# Add this function to the end of your scraper.py file

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