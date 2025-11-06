

from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)

# --- Accessibility Check Functions ---

def check_img_alt(soup):
    """Check if all images have alt attributes."""
    images = soup.find_all('img')
    missing_alt = [img for img in images if not img.get('alt')]
    return {
        "check": "Image alt text",
        "result": "Pass" if not missing_alt else "Fail",
        "details": f"{len(missing_alt)} images missing alt text" if missing_alt else "All images have alt text"
    }

def check_form_labels(soup):
    """Check if input elements have associated labels."""
    inputs = soup.find_all('input')
    missing_label = []
    for i in inputs:
        if not i.get('id'):
            missing_label.append(i)
        elif not soup.find('label', attrs={'for': i.get('id')}):
            missing_label.append(i)
    return {
        "check": "Form labels",
        "result": "Pass" if not missing_label else "Fail",
        "details": f"{len(missing_label)} form fields missing labels" if missing_label else "All inputs have labels"
    }

def check_headings(soup):
    """Check heading structure."""
    headings = [h.name for h in soup.find_all(['h1','h2','h3','h4','h5','h6'])]
    return {
        "check": "Headings present",
        "result": "Pass" if headings else "Fail",
        "details": f"Found {len(headings)} headings" if headings else "No headings found"
    }

def check_links(soup):
    """Check for meaningful link text."""
    links = soup.find_all('a')
    bad_links = [a for a in links if not a.get_text(strip=True)]
    return {
        "check": "Link text",
        "result": "Pass" if not bad_links else "Fail",
        "details": f"{len(bad_links)} links missing text" if bad_links else "All links have descriptive text"
    }

def run_accessibility_checks(url):
    """Fetch the page and run all accessibility checks."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        checks = [
            check_img_alt(soup),
            check_form_labels(soup),
            check_headings(soup),
            check_links(soup)
        ]
        return checks

    except requests.exceptions.RequestException as e:
        return [{"check": "Connection error", "result": "Error", "details": str(e)}]

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    error_message = None

    if request.method == 'POST':
        url = request.form.get('url')
        if not url:
            error_message = "Please enter a valid URL."
        elif not urlparse(url).scheme:
            error_message = "URL must include http:// or https://"
        else:
            results = run_accessibility_checks(url)

    return render_template('index.html', results=results, error=error_message)

# --- Run Flask App ---
if __name__ == '__main__':
    app.run(debug=True)
