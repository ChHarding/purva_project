import requests
from bs4 import BeautifulSoup
from pathlib import Path



# Basic fetcher

def fetch_page(url: str):
    """Download the HTML of a webpage."""
    headers = {"User-Agent": "AccessCheck/1.0"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text



# Tier 1 checks (WCAG 2.2)

def check_page_title(soup):
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    if title:
        return f" Page title found: '{title}'"
    return " Missing or empty <title> tag."


def check_html_lang(soup):
    html = soup.find("html")
    lang = html.get("lang") if html and html.has_attr("lang") else None
    if lang:
        return f" Document language declared: lang='{lang}'."
    return "Missing html[lang] attribute."


def check_image_alts(soup):
    imgs = soup.find_all("img")
    total = len(imgs)
    missing = [img.get("src", "No src") for img in imgs if not img.has_attr("alt") or not img["alt"].strip()]
    if total == 0:
        return "No images found."
    if missing:
        lines = "\n".join(f"  - Missing alt: {m}" for m in missing[:10])
        return f" {len(missing)}/{total} images missing alt text:\n{lines}"
    return f" All {total} images have alt text."


def check_headings(soup):
    headings = [(int(tag.name[1]), tag.get_text(strip=True)) for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    if not headings:
        return " No headings (h1–h6) found."
    # Check for h1 existence and sequence jumps
    levels = [lvl for lvl, _ in headings]
    h1_count = levels.count(1)
    messages = []
    if h1_count == 0:
        messages.append(" Missing <h1> heading.")
    elif h1_count > 1:
        messages.append(f" {h1_count} <h1> headings found (usually only one is recommended).")
    for i in range(1, len(levels)):
        if levels[i] - levels[i - 1] > 1:
            messages.append(f" Heading jump: h{levels[i-1]} → h{levels[i]}.")
    if not messages:
        messages.append(" Headings present and appear sequential.")
    return "\n".join(messages)


def check_link_text(soup):
    bad_words = {"click here", "here", "more", "read more", "learn more"}
    links = soup.find_all("a")
    bad_links = []
    for a in links:
        text = (a.get_text(" ", strip=True) or "").lower()
        if text in bad_words or text.strip() == "":
            bad_links.append(a.get("href", "no href"))
    if not links:
        return "ℹ No links found."
    if bad_links:
        lines = "\n".join(f"  - Weak link text: {l}" for l in bad_links[:10])
        return f" {len(bad_links)}/{len(links)} links have non-descriptive text:\n{lines}"
    return " All links have meaningful text."


def check_form_labels(soup):
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
            unlabeled.append(inp.get("name", inp.get("id", "unnamed field")))
    if unlabeled:
        lines = "\n".join(f"  - Unlabeled control: {u}" for u in unlabeled[:10])
        return f" {len(unlabeled)}/{len(visible_inputs)} form controls lack labels:\n{lines}"
    return f" All {len(visible_inputs)} form controls have accessible names."



# Reporter

def save_report(url, results):
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
        soup = BeautifulSoup(html, "html.parser")

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
