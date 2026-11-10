#!/usr/bin/env python3
"""Check institute source URLs and learning-resource URLs; does not edit raw data."""
import csv
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TABLES = ROOT / "data" / "raw" / "tables"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)


def check(url):
    if not url.startswith(("https://", "http://")):
        return "INVALID_URL", "URL must start with http:// or https://"
    headers = {"User-Agent": "IIT-Bhilai-KB-url-check/1.0"}
    try:
        req = urllib.request.Request(url, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            return str(response.status), "HEAD"
    except urllib.error.HTTPError as exc:
        # Some academic sites reject HEAD; retry with a small GET request.
        if exc.code not in (403, 405, 501):
            return str(exc.code), "HEAD"
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={**headers, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            return str(response.status), "GET fallback"
    except Exception as exc:
        return "FAIL", str(exc)[:180]


records = []
for filename, id_field, url_field, kind in (
    ("sources.csv", "source_id", "url", "institute_source"),
    ("resources.csv", "resource_id", "url", "learning_resource"),
):
    path = TABLES / filename
    if not path.exists():
        print(f"SKIP: {path.relative_to(ROOT)} not found")
        continue
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            status, method = check((row.get(url_field) or "").strip())
            records.append({"kind": kind, "id": row.get(id_field, ""), "url": row.get(url_field, ""),
                            "status": status, "method_or_error": method})
            print(f"{kind:18} {row.get(id_field, ''):16} {status:12} {row.get(url_field, '')}")

if records:
    out = OUT / "url_verification.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"\nSaved results to {out.relative_to(ROOT)}")
else:
    print("No URLs checked. Add sources.csv and/or resources.csv first.")
