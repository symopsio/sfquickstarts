#!/usr/bin/env python3
"""
Builds a gap report comparing the live snowflake.com developer guides
against the sfquickstarts repo to identify:
  - Guides on the live site with no repo markdown (need conversion)
  - Confirmed duplicate pages (slug mismatches to clean up)
  - Guides in the repo but missing from the manifest (need regeneration)

Usage:
    python3 scripts/migration/build_gap_report.py

Outputs:
    scripts/migration/output/gap_report.csv
    scripts/migration/output/duplicates.csv
    scripts/migration/output/needs_verification.csv
    scripts/migration/output/manifest_only.csv
    scripts/migration/output/summary.txt
"""

import json
import os
import re
import ssl
import sys
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "site" / "sfguides" / "src"
MANIFEST_PATH = SRC_DIR / "_shared_assets" / "quickstart-manifest.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

AEM_FILTER_URL = (
    "https://publish-p57963-e462109.adobeaemcloud.com"
    "/content/snowflake-site/global/en/developers/guides"
    "/_jcr_content/root/responsivegrid/container_211721158"
    "/flexible_column_cont/flexible_column_content_container_1"
    "/filterable_resources.filter.json"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.snowflake.com/en/developers/guides/",
}


def fetch_aem_inventory():
    """Paginate through the AEM filterable resources API to get all guide slugs."""
    all_guides = []
    offset = 0
    page_size = 12
    ctx = ssl.create_default_context()

    while True:
        url = f"{AEM_FILTER_URL}?offset={offset}" if offset else AEM_FILTER_URL
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, context=ctx)
        data = json.loads(resp.read().decode())

        hits = data.get("hits", [])
        total = data.get("totalMatches", 0)

        for hit in hits:
            btn = hit.get("button", {})
            link = btn.get("buttonLink", {})
            raw_url = link.get("url", "")
            title_lines = hit.get("title", {}).get("lines", [""])
            title = title_lines[0] if title_lines else ""
            ht = hit.get("highlightedTags", [])
            content_type = ", ".join(t.get("tagText", "") for t in ht) if ht else ""
            tags = [t.get("tagText", "") for t in hit.get("tags", [])]

            slug_match = re.search(r"/developers/guides/([^/]+)/?$", raw_url)
            if slug_match:
                all_guides.append({
                    "slug": slug_match.group(1),
                    "title": title,
                    "content_type": content_type,
                    "tags": ", ".join(tags),
                    "url": f"https://www.snowflake.com{raw_url}",
                })

        print(f"  Fetched offset={offset}, got {len(hits)} hits (total so far: {len(all_guides)}/{total})")
        offset += page_size
        if offset >= total or not hits:
            break

    return all_guides


def get_repo_dirs():
    """Get all guide directory names under site/sfguides/src/."""
    return {
        d.name
        for d in SRC_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    }


def get_manifest_slugs():
    """Extract slugs from the quickstart manifest."""
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    slugs = set()
    for entry in manifest.get("quickstartMetadata", []):
        m = re.search(r"/developers/guides/([^/]+)/?$", entry.get("url", ""))
        if m:
            slugs.add(m.group(1))
    return slugs


def get_repo_titles():
    """Read the H1 title from each guide's markdown file."""
    titles = {}
    for d in SRC_DIR.iterdir():
        if not d.is_dir() or d.name.startswith("_"):
            continue
        md_path = d / f"{d.name}.md"
        if md_path.exists():
            try:
                content = md_path.read_text(errors="replace")[:3000]
                for line in content.split("\n"):
                    if line.startswith("# "):
                        titles[d.name] = line[2:].strip()
                        break
            except Exception:
                pass
    return titles


def find_duplicates(gap_slugs, aem_by_slug, repo_dirs, repo_titles):
    """Classify gap guides into confirmed duplicates, likely duplicates, and truly missing."""
    title_to_dir = {t.lower().strip(): d for d, t in repo_titles.items()}

    confirmed = []
    likely = []
    missing = []

    for slug in sorted(gap_slugs):
        g = aem_by_slug[slug]
        aem_title = g.get("title", "").strip()
        found = False

        # 1. Near-exact slug variants
        variants = [
            slug.replace("_", "-"),
            slug.rstrip("md").rstrip("-"),
            slug.replace("--", "-"),
            re.sub(r"^sfguide-", "", slug),
        ]
        for v in variants:
            if v != slug and v in repo_dirs:
                confirmed.append({
                    **g,
                    "repo_dir": v,
                    "repo_title": repo_titles.get(v, ""),
                    "match_type": "slug variant",
                })
                found = True
                break
        if found:
            continue

        # 2. Exact title match
        if aem_title.lower().strip() in title_to_dir:
            repo_dir = title_to_dir[aem_title.lower().strip()]
            confirmed.append({
                **g,
                "repo_dir": repo_dir,
                "repo_title": repo_titles.get(repo_dir, ""),
                "match_type": "exact title",
            })
            continue

        # 3. Title similarity
        best_sim, best_dir = 0, None
        for d, t in repo_titles.items():
            sim = SequenceMatcher(None, aem_title.lower(), t.lower()).ratio()
            if sim > best_sim:
                best_sim, best_dir = sim, d

        if best_sim >= 0.80:
            confirmed.append({
                **g,
                "repo_dir": best_dir,
                "repo_title": repo_titles.get(best_dir, ""),
                "match_type": f"title similarity ({best_sim:.0%})",
            })
        elif best_sim >= 0.60:
            likely.append({
                **g,
                "repo_dir": best_dir or "",
                "repo_title": repo_titles.get(best_dir, "") if best_dir else "",
                "similarity": f"{best_sim:.0%}",
            })
        else:
            missing.append(g)

    return confirmed, likely, missing


def write_csv(path, rows, fieldnames):
    """Write a simple CSV (no csv module dependency issues)."""
    with open(path, "w") as f:
        f.write(",".join(fieldnames) + "\n")
        for row in rows:
            values = []
            for fn in fieldnames:
                val = str(row.get(fn, "")).replace('"', '""')
                if "," in val or '"' in val or "\n" in val:
                    val = f'"{val}"'
                values.append(val)
            f.write(",".join(values) + "\n")


def main():
    print("=" * 60)
    print("Developer Guides Gap Report Builder")
    print("=" * 60)

    # Step 1: Fetch AEM inventory
    print("\n[1/4] Fetching live site inventory from AEM...")
    aem_guides = fetch_aem_inventory()
    aem_slugs = {g["slug"] for g in aem_guides}
    aem_by_slug = {g["slug"]: g for g in aem_guides}
    print(f"  -> {len(aem_guides)} guides on the live site")

    # Step 2: Build repo inventory
    print("\n[2/4] Scanning repo directories and manifest...")
    repo_dirs = get_repo_dirs()
    manifest_slugs = get_manifest_slugs()
    repo_titles = get_repo_titles()
    print(f"  -> {len(repo_dirs)} guide directories in repo")
    print(f"  -> {len(manifest_slugs)} entries in manifest")
    print(f"  -> {len(repo_titles)} guides with readable titles")

    # Step 3: Compute gaps
    print("\n[3/4] Computing gaps...")
    gap_slugs = aem_slugs - repo_dirs
    in_repo_not_manifest = (aem_slugs & repo_dirs) - manifest_slugs
    repo_only = repo_dirs - aem_slugs

    confirmed, likely, missing = find_duplicates(
        gap_slugs, aem_by_slug, repo_dirs, repo_titles
    )

    # Step 4: Write output
    print("\n[4/4] Writing reports...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        OUTPUT_DIR / "gap_report.csv",
        missing,
        ["slug", "title", "content_type", "tags", "url"],
    )

    write_csv(
        OUTPUT_DIR / "duplicates.csv",
        confirmed,
        ["slug", "repo_dir", "title", "repo_title", "match_type", "content_type", "url"],
    )

    write_csv(
        OUTPUT_DIR / "needs_verification.csv",
        likely,
        ["slug", "repo_dir", "title", "repo_title", "similarity", "content_type", "url"],
    )

    manifest_rows = [
        {"slug": s, "title": repo_titles.get(s, ""), "in_repo": True}
        for s in sorted(in_repo_not_manifest)
    ]
    write_csv(
        OUTPUT_DIR / "manifest_only.csv",
        manifest_rows,
        ["slug", "title", "in_repo"],
    )

    # Summary
    summary_lines = [
        "DEVELOPER GUIDES GAP REPORT",
        "=" * 40,
        f"Date: {__import__('datetime').date.today()}",
        "",
        "INVENTORY",
        f"  Live site (AEM):        {len(aem_guides)}",
        f"  Repo directories:       {len(repo_dirs)}",
        f"  Repo manifest:          {len(manifest_slugs)}",
        "",
        "GAP ANALYSIS",
        f"  On site, not in repo:   {len(gap_slugs)}",
        f"    Confirmed duplicates: {len(confirmed)}",
        f"    Needs verification:   {len(likely)}",
        f"    Truly missing:        {len(missing)}",
        f"  In repo, not on site:   {len(repo_only)}",
        f"  On site, not in manifest (but in repo): {len(in_repo_not_manifest)}",
        "",
        "TRULY MISSING (need markdown conversion)",
    ]
    for g in missing:
        summary_lines.append(f"  [{g.get('content_type', '') or 'untagged'}] {g['slug']}")
        summary_lines.append(f"    {g['title']}")
    summary_lines.append("")
    summary_lines.append("CONFIRMED DUPLICATES (redirect + unpublish)")
    for d in confirmed:
        summary_lines.append(f"  {d['slug']} -> {d['repo_dir']} ({d['match_type']})")

    summary_text = "\n".join(summary_lines)
    (OUTPUT_DIR / "summary.txt").write_text(summary_text)
    print(f"\n{summary_text}")

    print(f"\nReports written to: {OUTPUT_DIR}/")
    print("  gap_report.csv          - Guides needing markdown conversion")
    print("  duplicates.csv          - Confirmed duplicates to clean up")
    print("  needs_verification.csv  - Needs manual review")
    print("  manifest_only.csv       - In repo but missing from manifest")
    print("  summary.txt             - Human-readable summary")


if __name__ == "__main__":
    main()
