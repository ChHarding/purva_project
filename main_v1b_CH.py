import requests
from bs4 import BeautifulSoup
from pathlib import Path



# add line numbers as attributes to HTML elements so we can report them later
 
def add_line_numbers_to_html(html: str) -> str:
    """Add line number attributes to HTML elements."""
    lines = html.splitlines()
    numbered_lines = []
    
    for i, line in enumerate(lines, 1):
        if line.strip() and '<' in line and '>' in line:
            # Add data-line attribute to opening tags
            import re
            # Find opening tags and add line number attribute
            line = re.sub(r'<(\w+)([^>]*?)>', rf'<\1\2 data-line="{i}">', line)
        numbered_lines.append(line)
    
    return "\n".join(numbered_lines)


def get_line_number(element):
    """Get the line number from data-line attribute """
    # Check for our custom line number attribute
    if element.get('data-line'):
        return f" (line {element['data-line']})"
    
    # Check parent elements for line numbers
    current = element.parent
    while current and current.name:
        if current.get('data-line'):
            return f" (near line {current['data-line']})"
        current = current.parent
    
    # Original fallback
    if hasattr(element, 'sourceline') and element.sourceline:
        return f" (line {element.sourceline})"
    
    return ""


# Basic fetcher

def fetch_page(url: str):
    """Download the HTML of a webpage."""
    headers = {"User-Agent": "AccessCheck/1.0"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text




# Tier 1 checks (WCAG 2.2)
def check_page_title(soup: BeautifulSoup):
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    if title:
        return f" Page title found: '{title}'"
    return " Missing or empty <title> tag."


def check_html_lang(soup: BeautifulSoup):
    html = soup.find("html")
    lang = html.get("lang") if html and html.has_attr("lang") else None
    if lang:
        return f" Document language declared: lang='{lang}'."
    return "Missing html[lang] attribute."


def check_image_alts(soup: BeautifulSoup):
    imgs = soup.find_all("img")
    total = len(imgs)
    missing = []
    for img in imgs:
        if not img.has_attr("alt") or not img["alt"].strip():
            src = img.get("src", "No src")
            line_info = get_line_number(img)
            missing.append(f"{src}{line_info}")
    
    if total == 0:
        return "No images found."
    if missing:
        lines = "\n".join(f"  - Missing alt: {m}" for m in missing[:10])
        return f" {len(missing)}/{total} images missing alt text:\n{lines}"
    return f" All {total} images have alt text."


def check_headings(soup: BeautifulSoup):
    heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    headings = []
    for tag in heading_tags:
        level = int(tag.name[1])
        text = tag.get_text(strip=True)
        line_info = get_line_number(tag)
        headings.append((level, text, line_info))
    
    if not headings:
        return " No headings (h1–h6) found."
    
    # Check for h1 existence and sequence jumps
    levels = [lvl for lvl, _, _ in headings]
    h1_count = levels.count(1)
    messages = []
    
    if h1_count == 0:
        messages.append(" Missing <h1> heading.")
    elif h1_count > 1:
        h1_locations = [line_info for lvl, _, line_info in headings if lvl == 1]
        locations_str = ", ".join(h1_locations) if any(h1_locations) else ""
        messages.append(f" {h1_count} <h1> headings found (usually only one is recommended){locations_str}.")
    
    for i in range(1, len(levels)):
        if levels[i] - levels[i - 1] > 1:
            line_info = headings[i][2]
            messages.append(f" Heading jump: h{levels[i-1]} → h{levels[i]}{line_info}.")
    
    if not messages:
        messages.append(" Headings present and appear sequential.")
    
    return "\n".join(messages)


def check_link_text(soup: BeautifulSoup):
    bad_words = {"click here", "here", "more", "read more", "learn more"}
    links = soup.find_all("a")
    bad_links = []
    for a in links:
        text = (a.get_text(" ", strip=True) or "").lower()
        if text in bad_words or text.strip() == "":
            href = a.get("href", "no href")
            line_info = get_line_number(a)
            bad_links.append(f"{href}{line_info}")
    
    if not links:
        return "ℹ No links found."
    if bad_links:
        lines = "\n".join(f"  - Weak link text: {l}" for l in bad_links[:10])
        return f" {len(bad_links)}/{len(links)} links have non-descriptive text:\n{lines}"
    return " All links have meaningful text."


def check_form_labels(soup: BeautifulSoup):
    inputs = soup.find_all(["input", "select", "textarea"])
    visible_inputs = [i for i in inputs if i.get("type") != "hidden"]
    if not visible_inputs:
        return "ℹ No form fields found."
    unlabeled = []
    for inp in visible_inputs:
        if not (
            inp.get("aria-label")
            or inp.get("aria-labelledby")
            or (inp.get("id") and soup.find("label", attrs={"for": inp["id"]}))
            or inp.find_parent("label")
        ):
            field_name = inp.get("name", inp.get("id", "unnamed field"))
            line_info = get_line_number(inp)
            unlabeled.append(f"{field_name}{line_info}")
    
    if unlabeled:
        lines = "\n".join(f"  - Unlabeled control: {u}" for u in unlabeled[:10])
        return f" {len(unlabeled)}/{len(visible_inputs)} form controls lack labels:\n{lines}"
    return f" All {len(visible_inputs)} form controls have accessible names."



# Reporter

def save_report(url: str, results: list[str]) -> None:
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    path = docs / "accessibility_report_v1b.txt"
    with path.open("w", encoding="utf-8") as f:
        f.write(f"Accessibility Report for {url}\n")
        f.write("=" * 60 + "\n\n")
        for res in results:
            f.write(res + "\n\n")
    print(f"\n Results saved to {path}")



# Main CLI

def main():
    print("AccessCheck – Accessibility Analyzer (Version 1B)")
    url = input("Enter website URL (include http/https): ").strip()

    try:
        html = fetch_page(url)
        
        # Add line numbers to HTML for better debugging
        numbered_html = add_line_numbers_to_html(html)
        
        # Use lxml parser 
        soup = BeautifulSoup(numbered_html, "lxml")

        results = [
            check_page_title(soup),
            check_html_lang(soup),
            check_image_alts(soup),
            check_headings(soup),
            check_link_text(soup),
            check_form_labels(soup),
        ]

        print("\nAccessibility Results:\n")
        for r in results:
            print(r + "\n")

        save_report(url, results)

    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
