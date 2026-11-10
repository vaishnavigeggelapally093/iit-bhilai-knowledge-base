# Sources and provenance (retrieval date: 2026-11-10)

| ID | Source | Exact source URL | Local material | Notes |
|---|---|---|---|---|
| S1 | IIT Bhilai UG Manual (current scheme) | https://www.iitbhilai.ac.in/index.php/index.php?pid=ug_manual | `data/raw/source_docs/UG manul.pdf` | Official IIT Bhilai PDF-serving endpoint. The URL is a dynamic institute route rather than a `.pdf`-suffixed file path. |
| S2 | IIT Bhilai Students’ Handbook, July 2023 | https://iitbhilai.ac.in/index.php?pid=aca_handbook_pdf | `data/raw/source_docs/student hand book.pdf` | Official PDF-serving endpoint; the document cover identifies July 2023 and applicability to students admitted till 2022-23-W. |
| S3 | IIT Bhilai Courses of Study, June 2023 | https://www.iitbhilai.ac.in/index.php?pid=schedule_programs | `data/raw/source_docs/Courses of Study June 2023.pdf` and `Courses of Study June 2023.txt` | Official PDF-serving endpoint; the document cover identifies June 2023 and applicability to students admitted till 2022-23-W. Original PDF uploaded by the user; text extract retained for processing. |
| S4 | Open educational resources | Per-resource URLs in `data/raw/tables/resources.csv` | Online resources | Licence values are recorded in the resource table; manually confirm current licence terms. |
| S5 | Author-created mappings and exercises | Not applicable | `data/raw/tables/skills.csv`, `course_skills.csv`, `resource_skills.csv`, `exercises.csv` | Judgement-based taxonomy/mappings and original practice questions; not official institute statements. |

The three institute source records now point to document-specific IIT Bhilai endpoints that serve the corresponding PDFs. The endpoint URLs do not necessarily end in `.pdf`, because the institute serves documents through its `index.php?pid=...` routes. The locally supplied copies are retained in `data/raw/source_docs/`. The resource table contains 31 URLs; rerun `python verify_urls.py` to produce a fresh `data/processed/url_verification.csv`. A successful HTTP response does not establish that a resource is openly licensed or that the recorded licence is accurate.
