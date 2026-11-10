# Pipeline test record

Test date: 2026-11-10

Command:

```bash
python run_pipeline.py
```

Result: **PASS** (exit code 0).

Summary printed by the pipeline:

```text
courses=48 rules=46 resources=31 chunks=134 modules=271
WARN semester-order check skipped for 3 edges (course has no semester in source): CS550->MA605, CS550->DS250, CS550->DS251
validation passed
```

The warning is retained intentionally because the source does not state the elective semester. It should not be hidden or interpreted as a verified semester-order check.
