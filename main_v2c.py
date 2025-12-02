from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

app = Flask(__name__)


def add_line_numbers_to_html(html: str) -> str:
    """Add data-line attributes to HTML tags for reporting."""
    lines = html.splitlines()
    numbered_lines = []

    for i, line in enumerate(lines, 1):
        if "<" in line and ">" in line:
            line = re.sub(r'<(\w+)([^>]*?)>', rf'<\1\2 data-line="{i}">', line)
        numbered_lines.append(line)

    return "\n".join(numbered_lines)

def get_line_number(element):
    """Return the stored HTML line number."""
    return element.get("data-line", None)


# -------------------------------------------------------
# ACCESSIBILITY CHECKS WITH LINE NUMBERS
# -------------------------------------------------------
def check_img_alt(soup):
    missing = []

    for img in soup.find_all("img"):
        if not img.get("alt") or not img.get("alt").strip():
            line = get_line_number(img)
            if line:
                missing.append(line)

    if not missing:
        return {"check": "Image alt text", "result": "Pass",
                "details": "All images have alt text."}

    return {"check": "Image alt text", "result": "Fail",
            "details": "Missing alt text on lines: " + ", ".join(missing)}


def check_form_labels(soup):
    missing = []

    for inp in soup.find_all("input"):
        if inp.get("type") == "hidden":
            continue

        labeled = (
            inp.get("aria-label")
            or inp.get("aria-labelledby")
            or (inp.get("id") and soup.find("label", attrs={"for": inp.get("id")}))
            or inp.find_parent("label")
        )

        if not labeled:
            line = get_line_number(inp)
            if line:
                missing.append(line)

    if not missing:
        return {"check": "Form labels", "result": "Pass",
                "details": "All form inputs have labels."}

    return {"check": "Form labels", "result": "Fail",
            "details": "Missing labels on lines: " + ", ".join(missing)}


def check_headings(soup):
    headings = soup.find_all(["h1","h2","h3","h4","h5","h6"])
    if not headings:
        return {"check": "Headings", "result": "Fail",
                "details": "No headings found."}

    lines = [get_line_number(h) for h in headings if get_line_number(h)]

    return {"check": "Headings", "result": "Pass",
            "details": "Headings found on lines: " + ", ".join(lines)}


def check_links(soup):
    missing = []

    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        if not text:  # empty anchor text
            line = get_line_number(link)
            if line:
                missing.append(line)

    if not missing:
        return {"check": "Link text", "result": "Pass",
                "details": "All links have descriptive text."}

    return {"check": "Link text", "result": "Fail",
            "details": "Links missing text on lines: " + ", ".join(missing)}



def run_accessibility_checks(url):
    try:
        response = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        response.raise_for_status()

        numbered_html = add_line_numbers_to_html(response.text)
        soup = BeautifulSoup(numbered_html, "lxml")

        return [
            check_img_alt(soup),
            check_form_labels(soup),
            check_headings(soup),
            check_links(soup)
        ]

    except Exception as e:
        return [{"check": "Error", "result": "Fail", "details": str(e)}]



@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    error_message = None
    url = ""

    if request.method == "POST":
        entered_url = request.form.get("url", "").strip()
        url = entered_url

        # -------------------------------------------
        # (1) If missing http(s) → add https://
        # -------------------------------------------
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not url:
            error_message = "Please enter a valid URL."

        else:
            # -------------------------------------------
            # (2) Try HTTPS first
            # -------------------------------------------
            results = run_accessibility_checks(url)

            # -------------------------------------------
            # (3) If HTTPS fails → fallback to HTTP
            # -------------------------------------------
            if results and results[0]["result"] == "Fail":
                error_msg = results[0]["details"]

                if ("HTTPSConnectionPool" in error_msg
                    or "403" in error_msg
                    or "Forbidden" in error_msg):

                    fallback_url = "http://" + entered_url.replace("https://", "").replace("http://", "")
                    results = run_accessibility_checks(fallback_url)
                    url = fallback_url  

    return render_template("index.html", results=results, error=error_message, url=url)


if __name__ == "__main__":
    app.run(debug=True)
