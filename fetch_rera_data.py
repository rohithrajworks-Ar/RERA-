"""Fetch Telangana RERA PrintPreview page and export structured data."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


RERA_URL = (
    "https://rerait.telangana.gov.in/PrintPreview/PrintPreview?"
    "q=WXw3Oe9rZ7IvMv9sFR9WMYkt43pkpCC0APZbcXt0EMTNCwbNYHTF8KdGbwZpWg%2bWb71Js9wiserMkuuXRAouXW7%2bChfbtBFdCb1OkgqkkDvZjAERSMy11nPdRlk%2bAWW1KjTX5RkztCtXcOzg%2fv9HOy1x2ZgOwaJgV3U%2bWOQCwJ%2bUuLNqf6mNZ8xebKdD4EMz3I%2fBmcag%2fEU%3d"
)
OUT_DIR = Path(__file__).resolve().parent


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_label_value_blocks(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for panel in soup.select("div.x_panel"):
        title_el = panel.select_one(".x_title h2")
        section = clean(title_el.get_text(" ", strip=True)) if title_el else "Section"
        cols = panel.select(".col-md-3, .col-md-4, .col-md-6, .col-md-12")
        labels = [clean(c.get_text(" ", strip=True)) for c in cols if clean(c.get_text(" ", strip=True))]
        i = 0
        while i + 1 < len(labels):
            field, value = labels[i], labels[i + 1]
            if field.endswith(":") or value.endswith(":"):
                field = field.rstrip(":")
                value = value.rstrip(":")
                rows.append({"section": section, "field": field, "value": value})
                i += 2
            else:
                rows.append({"section": section, "field": field, "value": value})
                i += 2
    return rows


def parse_tables(soup: BeautifulSoup) -> list[dict]:
    tables_out: list[dict] = []
    for idx, table in enumerate(soup.find_all("table")):
        headers = [clean(th.get_text(" ", strip=True)) for th in table.find_all("th")]
        if not headers:
            first_row = table.find("tr")
            if first_row:
                headers = [clean(td.get_text(" ", strip=True)) for td in first_row.find_all("td")]
        body_rows = []
        for tr in table.find_all("tr"):
            cells = [clean(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
            if not cells:
                continue
            if headers and cells == headers:
                continue
            if headers and len(headers) == len(cells):
                body_rows.append(dict(zip(headers, cells)))
            else:
                body_rows.append({"row": cells})
        tables_out.append({"table_index": idx, "headers": headers, "rows": body_rows})
    return tables_out


def to_markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "_No data extracted._\n"
    lines = ["| Section | Field | Value |", "|---|---|---|"]
    for row in rows:
        section = row.get("section", "").replace("|", "\\|")
        field = row.get("field", "").replace("|", "\\|")
        value = row.get("value", "").replace("|", "\\|")
        lines.append(f"| {section} | {field} | {value} |")
    return "\n".join(lines) + "\n"


def fetch_html(url: str) -> tuple[str, str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto("https://rerait.telangana.gov.in/", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(1500)
        page.goto(url, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3000)
        html = page.content()
        title = page.title()
        browser.close()
        return html, title


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else RERA_URL
    html, title = fetch_html(url)

    html_path = OUT_DIR / "rera_print_preview.html"
    html_path.write_text(html, encoding="utf-8")

    soup = BeautifulSoup(html, "lxml")
    if soup.find(string=re.compile("Unauthorized Access", re.I)):
        print("ERROR: Page returned Unauthorized Access. URL may require an active portal session.")
        return 1

    kv_rows = parse_label_value_blocks(soup)
    tables = parse_tables(soup)

    payload = {
        "source_url": url,
        "page_title": title,
        "key_value_rows": kv_rows,
        "tables": tables,
    }

    json_path = OUT_DIR / "rera_data.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = OUT_DIR / "rera_data_table.md"
    md_parts = [
        f"# Telangana RERA Data\n\n",
        f"**Source:** {url}\n\n",
        "## Key-Value Data\n\n",
        to_markdown_table(kv_rows),
        "\n## HTML Tables\n\n",
    ]
    for table in tables:
        md_parts.append(f"### Table {table['table_index'] + 1}\n\n")
        headers = table.get("headers") or []
        rows = table.get("rows") or []
        if headers:
            md_parts.append("| " + " | ".join(headers) + " |\n")
            md_parts.append("| " + " | ".join(["---"] * len(headers)) + " |\n")
            for row in rows:
                if isinstance(row, dict) and "row" not in row:
                    md_parts.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |\n")
                elif isinstance(row, dict) and "row" in row:
                    md_parts.append("| " + " | ".join(str(x) for x in row["row"]) + " |\n")
        md_parts.append("\n")
    md_path.write_text("".join(md_parts), encoding="utf-8")

    print(f"Saved: {html_path}")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")
    print(f"Extracted {len(kv_rows)} key-value rows and {len(tables)} tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
