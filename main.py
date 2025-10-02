import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm


# ---------------------------
# Data structures
# ---------------------------

@dataclass
class Card:
    id: str
    title: str
    status: str  # "good" | "warn" | "fail"
    summary: str
    details: List[str]
    recommendation: Optional[str] = None

    def traffic(self) -> str:
        return {"good": "🟢", "warn": "🟡", "fail": "🔴"}.get(self.status, "⚪")

    def to_markdown(self) -> str:
        md = [f"### {self.traffic()} {self.title}",
              f"**Status:** {self.status.upper()}",
              f"**Summary:** {self.summary}"]
        if self.details:
            md.append("**Details:**")
            for d in self.details:
                md.append(f"- {d}")
        if self.recommendation:
            md.append(f"**Recommendation:** {self.recommendation}")
        return "\n".join(md)


@dataclass
class Report:
    url: str
    cards: List[Card]

    def score(self) -> Tuple[int, int, int]:
        good = sum(1 for c in self.cards if c.status == "good")
        warn = sum(1 for c in self.cards if c.status == "warn")
        fail = sum(1 for c in self.cards if c.status == "fail")
        return good, warn, fail

    def to_json(self) -> Dict:
        return {"url": self.url, "cards": [asdict(c) for c in self.cards]}

    def to_markdown(self) -> str:
        good, warn, fail = self.score()
        head = [
            f"# AccessCheck – Accessibility Analyzer",
            f"**URL:** {self.url}",
            f"**Summary:** 🟢 {good}  🟡 {warn}  🔴 {fail}",
            "",
            "---",
            ""
        ]
        body = []
        for c in self.cards:
            body.append(c.to_markdown())
            body.append("")
        return "\n".join(head + body)


# ---------------------------
# Helpers
# ---------------------------

def fetch_html(url: str, timeout: int = 15) -> str:
    headers = {
        "User-Agent": "AccessCheck/1.0 (+https://example.org)"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def percent(n: int, d: int) -> float:
    return (n / d * 100) if d else 0.0


def has_meaningful_text(text: str) -> bool:
    stripped = (text or "").strip().lower()
    if not stripped:
        return False
    # avoid generic texts
    bad = {"click here", "here", "more", "link", "learn more", "read more"}
    return stripped not in bad and len(stripped) >= 3


def heading_level_ok(levels: List[int]) -> Tuple[bool, List[str]]:
    """
    Very simple rule: do not jump more than 1 level down at a time.
    e.g., h1 -> h2 -> h3 is fine; h1 -> h3 is a warning.
    """
    warnings = []
    ok = True
    prev = None
    for i, lvl in enumerate(levels):
        if prev is not None and (lvl - prev) > 1:
            ok = False
            warnings.append(f"Heading jump at position {i+1}: h{prev} -> h{lvl}")
        prev = lvl
    return ok, warnings


def find_label_for_input(soup: BeautifulSoup, input_el: Tag) -> bool:
    # by for=id
    el_id = input_el.get("id")
    if el_id and soup.find("label", attrs={"for": el_id}):
        return True
    # wrap case
    parent = input_el.parent
    while parent and isinstance(parent, Tag):
        if parent.name == "label":
            return True
        parent = parent.parent
    return False


# ---------------------------
# Checks (simple, beginner-friendly)
# ---------------------------

def check_page_title(soup: BeautifulSoup) -> Card:
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    if title:
        return Card(
            id="title",
            title="Page has a descriptive <title>",
            status="good",
            summary="The page has a title element.",
            details=[f"Title: “{title[:80]}”" if title else "Title present."]
        )
    return Card(
        id="title",
        title="Missing <title>",
        status="fail",
        summary="No <title> element found.",
        details=[],
        recommendation="Add a clear, concise <title> describing the page."
    )


def check_html_lang(soup: BeautifulSoup) -> Card:
    html = soup.find("html")
    lang = html.get("lang").strip() if html and html.has_attr("lang") else ""
    if lang:
        return Card(
            id="lang",
            title="Document language is declared",
            status="good",
            summary=f"html[lang='{lang}'] is set.",
            details=[]
        )
    return Card(
        id="lang",
        title="Missing document language",
        status="warn",
        summary="html[lang] is not set.",
        details=[],
        recommendation="Add a language code to <html lang=\"en\"> (or appropriate)."
    )


def check_images_alt(soup: BeautifulSoup, base_url: str) -> Card:
    imgs = soup.find_all("img")
    total = len(imgs)
    with_alt = sum(1 for i in imgs if i.has_attr("alt") and str(i.get("alt")).strip() != "")
    empty_alt = sum(1 for i in imgs if i.has_attr("alt") and str(i.get("alt")).strip() == "")
    without_alt = total - with_alt - empty_alt

    if total == 0:
        return Card(
            id="img-alt",
            title="Images have alt text",
            status="good",
            summary="No images found.",
            details=[]
        )

    pct = percent(with_alt, total)
    status = "good" if pct >= 95 else "warn" if pct >= 70 else "fail"
    details = [
        f"Images total: {total}",
        f"With non-empty alt: {with_alt} ({pct:.0f}%)",
        f"With empty alt: {empty_alt}",
        f"Missing alt: {without_alt}"
    ]
    rec = "Ensure informative images have meaningful alt; decorative images may use empty alt (alt=\"\")."
    return Card(
        id="img-alt",
        title="Images have alt text",
        status=status,
        summary="Checked for non-empty alt attributes on <img>.",
        details=details,
        recommendation=rec
    )


def check_links_text(soup: BeautifulSoup) -> Card:
    links = soup.find_all("a")
    total = len(links)
    good = 0
    poor_examples = []
    for a in links[:500]:  # cap to avoid giant pages
        text = (a.get_text(separator=" ", strip=True) or "")
        if has_meaningful_text(text):
            good += 1
        else:
            href = a.get("href") or ""
            sample = text if text else (href[:50] + "…")
            poor_examples.append(f"“{sample}”")
    if total == 0:
        return Card(
            id="link-text",
            title="Links have meaningful text",
            status="warn",
            summary="No links found.",
            details=[]
        )
    pct = percent(good, total)
    status = "good" if pct >= 90 else "warn" if pct >= 70 else "fail"
    details = [f"Links total: {total}", f"Meaningful text: {good} ({pct:.0f}%)"]
    if poor_examples[:5]:
        details.append("Examples needing improvement: " + ", ".join(poor_examples[:5]))
    rec = "Use descriptive link text that makes sense out of context (avoid “click here” or bare URLs)."
    return Card(
        id="link-text",
            title="Links have meaningful text",
            status=status,
            summary="Checked link text for clarity.",
            details=details,
            recommendation=rec
    )


def check_headings(soup: BeautifulSoup) -> Card:
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            headings.append((level, h.get_text(strip=True)[:80]))
    levels = [lvl for (lvl, _) in headings]
    if not levels:
        return Card(
            id="headings",
            title="Heading structure",
            status="warn",
            summary="No headings (h1–h6) found.",
            details=[],
            recommendation="Use headings to structure content; start with a single h1."
        )
    ok, warnings = heading_level_ok(levels)
    status = "good" if ok else "warn"
    details = [f"{len(headings)} headings found. First 3:"]
    for lvl, txt in headings[:3]:
        details.append(f"h{lvl}: “{txt}”")
    rec = None
    if not ok:
        rec = "Avoid skipping levels (e.g., h1 → h3). Nest sections in order."
    # Check for multiple h1s as an extra hint
    h1_count = sum(1 for lvl in levels if lvl == 1)
    if h1_count == 0:
        status = "warn"
        warnings.append("No h1 present.")
    elif h1_count > 1:
        status = "warn"
        warnings.append(f"{h1_count} h1 headings found; usually only one is recommended.")
    details.extend(warnings)
    return Card(
        id="headings",
        title="Heading structure",
        status=status,
        summary="Checked heading order and presence of h1.",
        details=details,
        recommendation=rec
    )


def check_form_labels(soup: BeautifulSoup) -> Card:
    inputs = soup.find_all(["input", "select", "textarea"])
    # exclude hidden inputs
    inputs = [i for i in inputs if i.get("type") != "hidden"]
    if not inputs:
        return Card(
            id="form-labels",
            title="Form controls have labels",
            status="warn",
            summary="No form controls found.",
            details=[]
        )
    labeled = sum(1 for i in inputs if find_label_for_input(soup, i))
    pct = percent(labeled, len(inputs))
    status = "good" if pct >= 95 else "warn" if pct >= 70 else "fail"
    details = [f"Form controls: {len(inputs)}", f"Labeled: {labeled} ({pct:.0f}%)"]
    rec = "Associate each control with a <label for=\"id\"> or wrap the input in a <label>."
    return Card(
        id="form-labels",
        title="Form controls have labels",
        status=status,
        summary="Checked whether inputs/selects/textareas have labels.",
        details=details,
        recommendation=rec
    )


def check_meta_viewport(soup: BeautifulSoup) -> Card:
    mv = soup.find("meta", attrs={"name": "viewport"})
    if mv:
        return Card(
            id="viewport",
            title="Mobile viewport set",
            status="good",
            summary="Meta viewport present.",
            details=[str(mv)]
        )
    return Card(
        id="viewport",
        title="Missing mobile viewport",
        status="warn",
        summary="No meta viewport tag found.",
        details=[],
        recommendation="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> for better mobile access."
    )


# ---------------------------
# Runner
# ---------------------------

def analyze(url: str) -> Report:
    print(f"\nFetching: {url}")
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    checks = [
        check_page_title,
        check_html_lang,
        check_images_alt,
        check_links_text,
        check_headings,
        check_form_labels,
        check_meta_viewport,
    ]

    cards: List[Card] = []
    for fn in tqdm(checks, desc="Analyzing", unit="check"):
        try:
            if fn in (check_images_alt,):
                cards.append(fn(soup, url))  # needs base_url
            else:
                cards.append(fn(soup))
        except Exception as e:
            cards.append(Card(
                id=fn.__name__,
                title=f"{fn.__name__} (error)",
                status="warn",
                summary="Checker failed to run.",
                details=[repr(e)],
                recommendation="Try again or simplify the page for V1."
            ))
    return Report(url=url, cards=cards)


def save_report(report: Report, docs_dir: Path) -> Tuple[Path, Path]:
    docs_dir.mkdir(parents=True, exist_ok=True)
    json_path = docs_dir / "report.json"
    md_path = docs_dir / "report.md"
    json_path.write_text(json.dumps(report.to_json(), indent=2), encoding="utf-8")
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    return json_path, md_path


def print_cards(report: Report) -> None:
    good, warn, fail = report.score()
    print("\n" + "=" * 72)
    print(f"AccessCheck results for {report.url}")
    print(f"Summary: 🟢 {good}  🟡 {warn}  🔴 {fail}")
    print("=" * 72 + "\n")
    for c in report.cards:
        print(f"{c.traffic()} {c.title}  [{c.status.upper()}]")
        print(f"  {c.summary}")
        for d in c.details:
            print(f"  - {d}")
        if c.recommendation:
            print(f"  Recommendation: {c.recommendation}")
        print("")


def main():
    print("AccessCheck – Accessibility Analyzer (V1, CLI)")
    print("Enter a full URL (e.g., https://example.com)")
    url = input("URL: ").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        print("Please provide a full URL starting with http:// or https://")
        sys.exit(1)

    try:
        report = analyze(url)
        print_cards(report)
        json_path, md_path = save_report(report, Path("docs"))
        print(f"Saved JSON report -> {json_path}")
        print(f"Saved Markdown report -> {md_path}")
        print("\nDone.")
    except requests.HTTPError as e:
        print(f"HTTP error: {e}")
    except requests.RequestException as e:
        print(f"Network error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
