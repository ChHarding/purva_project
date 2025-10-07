import requests
from bs4 import BeautifulSoup

def fetch_page(url: str):
    """Download the HTML of a webpage."""
    headers = {"User-Agent": "AccessCheck/1.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text

def check_accessibility(html: str):
    """Do very basic accessibility checks (Version 1)."""
    soup = BeautifulSoup(html, "html.parser")

    results = {}

    # 1. Page title
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    results["title"] = title if title else "Missing <title>"

    # 2. Image alt attributes
    imgs = soup.find_all("img")
    total = len(imgs)
    with_alt = sum(1 for img in imgs if img.has_attr("alt") and img["alt"].strip() != "")
    results["images"] = f"{with_alt}/{total} images have alt text"

    return results

def main():
    print("AccessCheck – Basic Accessibility Analyzer (Version 1)")
    url = input("Enter a website URL (include http/https): ").strip()

    try:
        html = fetch_page(url)
        results = check_accessibility(html)

        print("\nResults:")
        print(f"Page title: {results['title']}")
        print(f"Images: {results['images']}")
    except Exception as e:
        print(f"Error fetching or analyzing the site: {e}")

if __name__ == "__main__":
    main()
