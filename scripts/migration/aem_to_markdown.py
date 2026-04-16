#!/usr/bin/env python3
"""
Convert AEM-published developer guides to repo-format markdown.

Handles two AEM page templates:
1. Quickstart template — rich step-by-step guides rendered via snowflake-markdown div
2. Solution Center template — shorter solution pages with hero, overview, architecture sections

Usage:
    python3 scripts/migration/aem_to_markdown.py --csv scripts/migration/output/gap_report.csv
    python3 scripts/migration/aem_to_markdown.py --slugs slug1 slug2 ...
    python3 scripts/migration/aem_to_markdown.py --csv scripts/migration/output/gap_report.csv --dry-run
"""

import argparse
import csv
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as md

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "site" / "sfguides" / "src"

BASE_GUIDE_URL = "https://www.snowflake.com/en/developers/guides"
AEM_FILTER_URL = (
    "https://publish-p57963-e462109.adobeaemcloud.com"
    "/content/snowflake-site/global/en/developers/guides"
    "/_jcr_content/root/responsivegrid/container_211721158"
    "/flexible_column_cont/flexible_column_content_container_1"
    "/filterable_resources.filter.json"
)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.snowflake.com/en/developers/guides/",
}

SECTION_DELIMITER = "<!-- ------------------------ -->"

CONTENT_TYPE_MAP = {
    "CERTIFIED SOLUTION": "snowflake-site:taxonomy/solution-center/certification/certified-solution",
    "COMMUNITY SOLUTION": "snowflake-site:taxonomy/solution-center/certification/community-solution",
    "PARTNER SOLUTION": "snowflake-site:taxonomy/solution-center/certification/partner-solution",
    "QUICKSTART": "snowflake-site:taxonomy/solution-center/certification/quickstart",
    "WELL ARCHITECTED FRAMEWORK": "snowflake-site:taxonomy/solution-center/certification/well-architected-framework",
    "Certified Solution": "snowflake-site:taxonomy/solution-center/certification/certified-solution",
    "Community Solution": "snowflake-site:taxonomy/solution-center/certification/community-solution",
    "Partner Solution": "snowflake-site:taxonomy/solution-center/certification/partner-solution",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def http_get(url, headers=None, timeout=30):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers or HTTP_HEADERS)
    return urllib.request.urlopen(req, context=ctx, timeout=timeout)


def fetch_aem_metadata_batch():
    """Fetch all guide metadata from AEM filter API (paginated)."""
    metadata = {}
    offset = 0
    while True:
        url = f"{AEM_FILTER_URL}?offset={offset}" if offset else AEM_FILTER_URL
        try:
            resp = http_get(url, headers=JSON_HEADERS)
            data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  WARNING: AEM API error at offset {offset}: {e}")
            break

        for hit in data.get("hits", []):
            link_url = hit.get("button", {}).get("buttonLink", {}).get("url", "")
            slug = link_url.rstrip("/").split("/")[-1] if link_url else ""
            if not slug:
                continue

            title_lines = hit.get("title", {}).get("lines", [""])
            ct_tags = hit.get("highlightedTags", [])
            tags = [t.get("tagText", "") for t in hit.get("tags", [])]

            metadata[slug] = {
                "title": title_lines[0] if title_lines else "",
                "content_type": ", ".join(t.get("tagText", "") for t in ct_tags),
                "tags": tags,
            }

        total = data.get("totalMatches", 0)
        offset += 12
        if offset >= total or not data.get("hits"):
            break

    return metadata


def sanitize_filename(name):
    name = name.split("?")[0]
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name).lower()


# ---------------------------------------------------------------------------
# Template detection
# ---------------------------------------------------------------------------

def detect_template(soup):
    """Detect which AEM page template is used."""
    if soup.find("div", class_="snowflake-markdown"):
        return "quickstart"
    if soup.find("div", class_=lambda c: c and "sc-hero" in c):
        return "solution-center"
    return "unknown"


# ---------------------------------------------------------------------------
# Quickstart template extractor
# ---------------------------------------------------------------------------

def extract_quickstart(soup):
    """Extract content from the quickstart (markdown-rendered) template."""
    meta = {}
    images = []

    # Hero metadata
    hero = soup.find("div", class_="snowflake-quickstart-hero-wrapper")
    if hero:
        title_el = hero.find("h2")
        if title_el:
            meta["title"] = title_el.get_text(strip=True)

        info_tags = hero.find_all("div", class_="snowflake-quickstart-hero-info-tag")
        tag_texts = [t.get_text(strip=True) for t in info_tags]
        if len(tag_texts) >= 2:
            meta["signature_tag"] = tag_texts[0]
            meta["author"] = tag_texts[-1]
        elif len(tag_texts) == 1:
            text = tag_texts[0]
            if "," in text or " " in text:
                meta["author"] = text
            else:
                meta["signature_tag"] = text

    # Body content
    content_div = soup.find("div", class_="snowflake-markdown")
    if not content_div:
        return meta, "", images

    # Remove empty spacer divs
    for empty in content_div.find_all("div", class_="body-1"):
        if not empty.get_text(strip=True):
            empty.decompose()

    body_md = md(str(content_div), heading_style="ATX", strip=[])
    body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()

    # Collect images from the content area's parent
    if content_div.parent:
        for img in content_div.parent.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src and "/content/dam/" in src:
                images.append({"src": src, "alt": alt})

    return meta, body_md, images


# ---------------------------------------------------------------------------
# Solution Center template extractor
# ---------------------------------------------------------------------------

def extract_solution_center(soup):
    """Extract content from the Solution Center page template."""
    meta = {}
    images = []
    sections = []

    # Hero metadata
    title_el = soup.find("div", class_="sc-hero__headline")
    if title_el:
        meta["title"] = title_el.get_text(strip=True)

    byline_el = soup.find("div", class_="sc-hero__byline")
    if byline_el:
        byline = byline_el.get_text(strip=True)
        # Byline formats: "By: Name | Published: Date" or "By: NamePublished: Date" or "By: NameUpdated: Date"
        author_match = re.search(r"By:\s*(.+?)(?:\s*\|?\s*(?:Published|Updated):|\s*$)", byline)
        if author_match:
            meta["author"] = author_match.group(1).strip().rstrip("|").strip()

    cert_el = soup.find("div", class_=lambda c: c and "solution-center-hero__certification" in c)
    if cert_el:
        cert_text = cert_el.get_text(strip=True).upper()
        # Normalize to title case for CONTENT_TYPE_MAP lookup
        for key in CONTENT_TYPE_MAP:
            if key.upper() == cert_text:
                meta["content_type"] = key
                break

    # Overview section
    overview_titles = soup.find_all(class_="solution-overview-title")
    overview_text = soup.find(class_="solution-overview-text")
    if overview_titles and overview_text:
        section_title = overview_titles[0].get_text(strip=True)
        section_body = md(str(overview_text), heading_style="ATX").strip()
        sections.append(f"## {section_title}\n\n{section_body}")

    # Architecture image (uses Adobe Dynamic Media URLs)
    arch_img_div = soup.find("div", class_=lambda c: c and "solution-architecture-main-image" in c)
    arch_img_ref = ""
    if arch_img_div:
        img = arch_img_div.find("img")
        if img:
            src = img.get("src", "")
            alt = img.get("alt", "") or "Architecture Diagram"
            if src:
                images.append({"src": src, "alt": alt})
                fname_match = re.search(r'/([^/?]+\.(?:png|jpg|jpeg|gif|webp|svg))', src, re.IGNORECASE)
                fname = fname_match.group(1) if fname_match else "architecture.png"
                fname = re.sub(r'[^a-zA-Z0-9._-]', '_', fname).lower()
                arch_img_ref = f"\n![{alt}](assets/{fname})\n"

    # Architecture section
    arch_text = soup.find(class_="solution-architecture-text")
    if len(overview_titles) > 1 and arch_text:
        section_title = overview_titles[1].get_text(strip=True)
        section_body = md(str(arch_text), heading_style="ATX").strip()
        sections.append(f"## {section_title}\n{arch_img_ref}\n{section_body}")
    elif arch_img_ref:
        sections.append(f"## Solution Architecture\n{arch_img_ref}")

    # About / additional overview sections
    about_sections = soup.find_all(class_=lambda c: c and "solution-about" in c)
    for i, div in enumerate(about_sections):
        title_el = div.find(class_="solution-overview-title") or div.find(["h3", "h4"])
        text_el = div.find(class_="snowflake-text")
        if title_el and text_el:
            sections.append(
                f"## {title_el.get_text(strip=True)}\n\n{md(str(text_el), heading_style='ATX').strip()}"
            )

    # Handle any remaining overview titles beyond the first two
    if len(overview_titles) > 2:
        for ot in overview_titles[2:]:
            section_title = ot.get_text(strip=True)
            parent = ot.parent
            if parent:
                text_el = parent.find("div", class_="snowflake-text")
                if text_el:
                    sections.append(
                        f"## {section_title}\n\n{md(str(text_el), heading_style='ATX').strip()}"
                    )

    # The hero code snippet is auto-pulled from the linked GitHub repo;
    # it's not authored content, so we skip it here.

    # Related Resources
    resource_cards = soup.find_all("h4", class_=lambda c: not c or "snowflake-title-v2-line" in " ".join(c) if c else True)
    resources = []
    for card in resource_cards:
        card_text = card.get_text(strip=True)
        if not card_text or "what's next" in card_text.lower():
            continue
        link_parent = card.find_parent("a")
        href = link_parent.get("href", "") if link_parent else ""
        if href:
            resources.append(f"- [{card_text}]({href})")
        else:
            link = card.find("a")
            href = link.get("href", "") if link else ""
            resources.append(f"- [{card_text}]({href})" if href else f"- {card_text}")

    if resources:
        sections.append("## Related Resources\n\n" + "\n".join(resources))

    # Collect any additional content images (DAM or Dynamic Media)
    content_area = soup.find("div", class_="responsivegrid")
    seen_srcs = {img["src"] for img in images}
    if content_area:
        for img in content_area.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src and src not in seen_srcs and ("/content/dam/" in src or "/dynamicmedia/" in src):
                images.append({"src": src, "alt": alt})
                seen_srcs.add(src)

    body_md = "\n\n".join(sections)
    return meta, body_md, images


# ---------------------------------------------------------------------------
# Common formatting
# ---------------------------------------------------------------------------

def extract_summary(body_md):
    """Extract a summary from the first section."""
    match = re.search(
        r"## (?:Overview|Introduction)?\s*\n+(.*?)(?=\n## |\n### (?:Prerequisites|What You|The ))",
        body_md, re.DOTALL,
    )
    if not match:
        match = re.search(r"##.*?\n\n(.+?)(?:\n\n|\n##)", body_md, re.DOTALL)

    if match:
        text = match.group(1).strip()
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # strip bold for summary
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # strip links
        text = re.sub(r"\n\*\s+", " ", text)  # collapse bullet lists
        text = re.sub(r"\n+", " ", text)  # collapse newlines to single line
        text = re.sub(r"\s+", " ", text).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        summary = sentences[0]
        if len(summary) < 100 and len(sentences) > 1:
            summary += " " + sentences[1]
        return summary[:250].strip()

    return ""


def build_categories(content_type):
    cats = []
    for ct in content_type.split(","):
        ct = ct.strip()
        if ct in CONTENT_TYPE_MAP:
            cats.append(CONTENT_TYPE_MAP[ct])
    if not cats:
        cats.append("snowflake-site:taxonomy/solution-center/certification/quickstart")
    return ", ".join(cats)


def add_section_delimiters(body_md):
    lines = body_md.split("\n")
    result = []
    for line in lines:
        if line.startswith("## "):
            if result and result[-1].strip() != SECTION_DELIMITER:
                if result and result[-1].strip():
                    result.append("")
                result.append(SECTION_DELIMITER)
        result.append(line)
    return "\n".join(result)


def format_frontmatter(slug, title, author, summary, categories):
    lines = []
    if author:
        lines.append(f"author: {author}")
    lines.append(f"id: {slug}")
    if summary:
        lines.append(f"summary: {summary}")
    lines.append(f"categories: {categories}")
    lines.append("environments: web")
    lines.append("language: en")
    lines.append("status: Published")
    lines.append("feedback link: https://github.com/Snowflake-Labs/sfguides/issues")
    lines.append(f"fork repo link: https://github.com/Snowflake-Labs/sfquickstarts/tree/master/site/sfguides/src/{slug}")
    return "\n".join(lines)


def download_images(images, output_dir):
    if not images:
        return 0

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    downloaded = 0
    for img in images:
        src = img["src"]
        if not src.startswith(("http://", "https://")):
            src = f"https://www.snowflake.com{src}"

        filename = sanitize_filename(src.split("/")[-1])
        if not filename:
            continue

        local_path = assets_dir / filename
        if local_path.exists():
            continue

        try:
            resp = http_get(src, timeout=15)
            data = resp.read()
            if data:
                local_path.write_bytes(data)
                downloaded += 1
        except Exception as e:
            print(f"    WARNING: Image download failed {filename}: {e}")

    return downloaded


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert_guide(slug, aem_metadata=None, csv_row=None, dry_run=False):
    """Convert a single guide from AEM to repo markdown."""
    print(f"\n  [{slug}]")

    output_dir = SRC_DIR / slug
    md_path = output_dir / f"{slug}.md"

    if md_path.exists():
        print(f"    SKIP: Already exists")
        return "skip"

    # Fetch page
    print(f"    Fetching...")
    url = f"{BASE_GUIDE_URL}/{slug}/"
    try:
        resp = http_get(url)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    ERROR: {e}")
        return "fail"

    soup = BeautifulSoup(html, "html.parser")
    template = detect_template(soup)
    print(f"    Template: {template}")

    # Extract content based on template
    if template == "quickstart":
        hero_meta, body_md, images = extract_quickstart(soup)
    elif template == "solution-center":
        hero_meta, body_md, images = extract_solution_center(soup)
    else:
        print(f"    FAILED: Unknown template")
        return "fail"

    if not body_md or len(body_md) < 100:
        print(f"    FAILED: Content too short ({len(body_md or '')} chars)")
        return "fail"

    # Resolve metadata: prefer hero, then AEM API, then CSV
    title = hero_meta.get("title", "")
    if not title and aem_metadata:
        title = aem_metadata.get("title", "")
    if not title and csv_row:
        title = csv_row.get("title", "")
    if not title:
        title = slug.replace("-", " ").title()

    author = hero_meta.get("author", "")

    content_type = hero_meta.get("content_type", "")
    if not content_type and aem_metadata:
        content_type = aem_metadata.get("content_type", "")
    if not content_type and csv_row:
        content_type = csv_row.get("content_type", "")

    summary = extract_summary(body_md)
    categories = build_categories(content_type)
    body_with_delimiters = add_section_delimiters(body_md)
    frontmatter = format_frontmatter(slug, title, author, summary, categories)
    full_md = f"{frontmatter}\n\n# {title}\n{SECTION_DELIMITER}\n{body_with_delimiters}\n"

    if dry_run:
        print(f"    DRY RUN: {md_path.relative_to(REPO_ROOT)}")
        print(f"    Title:      {title}")
        print(f"    Author:     {author}")
        print(f"    Type:       {content_type}")
        print(f"    Summary:    {summary[:80]}...")
        print(f"    Categories: {categories}")
        print(f"    Body:       {len(body_md)} chars, {len(images)} images")
        return "ok"

    # Write
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(full_md, encoding="utf-8")
    print(f"    Wrote: {md_path.relative_to(REPO_ROOT)}")

    img_count = download_images(images, output_dir)
    if img_count:
        print(f"    Downloaded {img_count} images")

    print(f"    OK: \"{title}\" ({len(body_md)} chars, {template})")
    return "ok"


def load_csv(csv_path):
    rows = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("slug"):
                rows[row["slug"]] = row
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Convert AEM developer guides to repo markdown"
    )
    parser.add_argument("--slugs", nargs="+", help="Guide slugs to convert")
    parser.add_argument("--csv", help="Path to gap_report.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-api", action="store_true")

    args = parser.parse_args()

    if not args.slugs and not args.csv:
        parser.error("Provide --slugs or --csv")

    csv_rows = {}
    slugs = list(args.slugs or [])
    if args.csv:
        csv_rows = load_csv(args.csv)
        slugs.extend(s for s in csv_rows if s not in slugs)

    if not slugs:
        print("No slugs to convert.")
        return

    print("=" * 60)
    print("AEM to Markdown Converter")
    print("=" * 60)
    print(f"Guides to convert: {len(slugs)}")
    if args.dry_run:
        print("MODE: Dry run")

    aem_metadata = {}
    if not args.skip_api:
        print("\nFetching AEM metadata...")
        aem_metadata = fetch_aem_metadata_batch()
        matched = sum(1 for s in slugs if s in aem_metadata)
        print(f"  Matched {matched}/{len(slugs)} slugs")

    results = {"ok": 0, "skip": 0, "fail": 0}
    for slug in slugs:
        status = convert_guide(
            slug,
            aem_metadata=aem_metadata.get(slug),
            csv_row=csv_rows.get(slug),
            dry_run=args.dry_run,
        )
        results[status] += 1
        time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"Done: {results['ok']} converted, {results['skip']} skipped, {results['fail']} failed")
    print("=" * 60)


if __name__ == "__main__":
    main()
