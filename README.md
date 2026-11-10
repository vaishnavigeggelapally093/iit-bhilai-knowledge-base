# Personalised Learning Buddy - Knowledge Base (IIT Bhilai, B.Tech CSE)

**Programme:** B.Tech Computer Science and Engineering, legacy curriculum for batches admitted up to 2022-23-W. The course list is based on IIT Bhilai's *Courses of Study, June 2023*. Academic rules are drawn from the UG Manual and Students' Handbook included in this package. The current UG Manual and legacy course list describe different schemes; do not use this legacy course list to advise current-scheme students.

## Run the pipeline

From this folder, using Python 3.8+:

```bash
python run_pipeline.py
```

The pipeline uses only the Python standard library and does not make network, LLM, or embedding calls. It performs ingest (SHA-256 manifest), parsing/normalisation, validation, chunking, and export. Outputs are written to `data/processed/`, including CSV/JSON tables, `chunks.jsonl`, `raw_manifest.json`, and `quality_report.json`.

Validation checks duplicate course codes, code format, numeric credits, source references, prerequisite targets and cycles, prerequisite semester ordering where source semesters are known, skill references, required resource licences, semester credit totals, and category totals. The current run passes with one documented warning: three prerequisite edges involving electives with no source-specified semester cannot be checked for semester ordering.

To check URLs separately (requires internet access):

```bash
python verify_urls.py
```

This writes `data/processed/url_verification.csv`. The raw resource table currently marks 31/31 resource URLs as verified based on the author's earlier checks. The verification log is not included in this package, so rerun the script to reproduce a current check. URL reachability does not prove that a resource's licence or availability terms are correct.

## Package layout

- `data/raw/tables/`: nine required CSV tables plus optional `learning_outcomes.csv` and `exercises.csv`.
- `data/raw/source_docs/`: three supplied PDFs, including the original June 2023 Courses of Study PDF, plus its text extract used for processing.
- `data/processed/`: generated tables, chunks, manifest, and quality report.
- `SOURCES.md`: source and provenance notes.
- `IDEAS.md`: example questions the knowledge base can and cannot answer.
- `DATA_QUALITY.md`: counts, validation results, and limitations.

## Data-entry and AI-use disclosure

The CSV rows were manually transcribed by an AI assistant from the supplied documents; syllabi are abridged topic lists. The 28-skill taxonomy and course-skill/resource-skill mappings are author-created judgements, not official institute classifications. Nine exercises are author-created practice questions. No explicit learning outcomes were supplied, so `learning_outcomes.csv` is intentionally header-only; outcomes have not been invented from topic headings. The user should spot-check records against the source documents before submission.

Claude (Anthropic) was used to read documents and help prepare the tables, pipeline, and documentation. Review and verify the generated data before relying on it.

## Modelling decisions

- Electives without source-specified semesters have blank semester fields and are labelled accordingly; do not infer an offering semester.
- `prereq_consent_required` records consent requirements that are not represented by a course-code prerequisite.
- Prerequisite `kind` distinguishes `hard` from `concurrent_ok` edges.
- `curriculum_slots` represents curriculum slots such as DE I that do not identify one fixed course.
- `Rule.applies_to_scheme` distinguishes legacy, current, and shared rules.
- `modules` are derived syllabus-topic chunks, not official institute modules (`module_kind=derived_syllabus_topic`, `is_official_module=false`).
- `source_type`, `url_specificity`, and `url_verified` make provenance limitations explicit.

## Important limitations

1. The included Courses of Study is the legacy scheme; current-scheme CSE course details are not included.
2. Institute source URLs now point to document-specific PDF-serving endpoints on IIT Bhilai. These are dynamic `index.php?pid=...` routes and may not have a `.pdf` suffix. The original June 2023 PDF and its text extract are both included locally.
3. Elective semester offerings are not specified in the source; the validator skips semester-order checks for three affected edges.
4. Syllabi are abridged, and the data has no student profile/progress records, timetable, instructor assignments, or minor-eligibility policy.
5. Resource licences and live availability need manual review on the provider sites. URL reachability alone is not licence verification.
6. No explicit learning outcomes are present. The nine exercises are optional author-created practice, not official assessment material.
