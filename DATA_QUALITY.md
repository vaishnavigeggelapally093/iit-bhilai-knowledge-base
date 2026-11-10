# Data Quality Report

**Scope:** IIT Bhilai B.Tech CSE legacy curriculum (students admitted up to 2022-23-W). Generated counts from `data/processed/quality_report.json` after running `python run_pipeline.py`.

## Dataset counts

- 48 courses (37 CSE core, 7 electives, 4 DSAI cross-listed)
- 40 prerequisite edges; 50 curriculum slots
- 28 skills; 57 course-skill links
- 46 academic rules
- 31 learning resources; 36 resource-skill links
- 271 derived syllabus-topic records (not official modules)
- 0 explicit learning outcomes
- 9 author-created exercises
- 134 chunks: 48 syllabus, 46 rule, 31 resource, 9 exercise; longest chunk 459 characters

## Validation result

**Pipeline status: PASS.** No validation errors were reported. Checks include unique course codes, numeric credits, source identifiers/URLs/retrieval dates, prerequisite target integrity and cycle detection, semester/category credit totals, and skill references.

**One warning:** semester-order validation was skipped for three edges (`CS550->MA605`, `CS550->DS250`, `CS550->DS251`) because the elective course has no semester specified in the source. This is a documented source limitation, not a validation pass for those semester-order relationships.

Credit totals: each semester is 30 credits; category totals are IC 60, PC 60, DE 60, OE 30, CA/LA 30; total 240, matching the legacy curriculum rules represented in the data.

## Known limitations / risks

- Data was manually transcribed with AI assistance and has not been independently double-checked. Spot-check course details, prerequisites, and rule wording against the source documents before submission.
- The course list is for the legacy scheme, while the supplied UG Manual describes the current scheme. Do not present this as the current CSE curriculum.
- Institute source URLs now point to document-specific IIT Bhilai PDF-serving endpoints (`pid=ug_manual`, `pid=aca_handbook_pdf`, and `pid=schedule_programs`). These dynamic routes do not necessarily end in `.pdf`. The original June 2023 Courses of Study PDF and its text extract are both included locally.
- Elective semester information is absent from the source; syllabi are abridged topic lists.
- Skills and course-skill/resource-skill mappings are author-created judgements, not official institute statements.
- All 31 resource rows currently have `url_verified=true` based on earlier checks recorded by the author. The earlier verification log is not bundled; rerun `python verify_urls.py` for a reproducible current check. URL reachability does not validate licence terms.
- Resource licences should be manually checked on each provider site. No NPTEL resources or minor-eligibility policy are included.
- There are no explicit learning outcomes. The optional exercises table has nine author-created questions; there are no student records or progress data for personalised readiness assessment.

## Interpretation

The validator tests internal consistency (for example, graph integrity and credit arithmetic). Internally consistent data can still contain transcription or interpretation errors. Human source review remains necessary.
