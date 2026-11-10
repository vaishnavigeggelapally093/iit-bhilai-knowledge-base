#!/usr/bin/env python3
"""Knowledge-base pipeline: IIT Bhilai B.Tech CSE.

One command:  python run_pipeline.py
Stages: ingest -> parse/normalise -> validate -> chunk -> export.
Standard library only. No network, no LLM, no embedding calls.
"""
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
TABLES = RAW / "tables"
OUT = ROOT / "data" / "processed"

MAX_CHUNK_CHARS = 700
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
CODE_RE = re.compile(r"^[A-Z]{2}\d{3}$")
PREREQ_KINDS = {"hard", "concurrent_ok"}
SCHEMES = {"legacy", "current", "both"}
SLOT_TO_RULE_SUBJECT = {"IC": "IC", "PC": "PC", "DE": "DE", "OE": "OE", "CA": "CALA", "CALA": "CALA"}

errors, warnings = [], []
skipped_order = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


# ---------------------------------------------------------------- ingest
def ingest():
    """Record a hash manifest of everything under data/raw (files stay untouched)."""
    manifest = {}
    for p in sorted(RAW.rglob("*")):
        if p.is_file():
            manifest[str(p.relative_to(RAW))] = hashlib.sha256(p.read_bytes()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "raw_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    needed = ["sources", "courses", "prerequisites", "curriculum_slots", "skills",
              "course_skills", "rules", "resources", "resource_skills"]
    for n in needed:
        if not (TABLES / f"{n}.csv").exists():
            sys.exit(f"INGEST FAILED: missing data/raw/tables/{n}.csv")
    expected_docs = {
        "UG manual": ["UG manul.pdf", "UG manual.pdf"],
        "Students' handbook": ["student hand book.pdf", "Students' Handbook.pdf"],
        "Courses of Study": ["Courses of Study June 2023.txt", "Course of Study.pdf", "Course of Study.pdf.txt", "Courses of Study.pdf"],
    }
    for label, candidates in expected_docs.items():
        if not any((RAW / "source_docs" / name).exists() for name in candidates):
            warn(f"source document not present in data/raw/source_docs: {label}")
    return manifest


def read(name, required=True):
    path = TABLES / f"{name}.csv"
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing required input: {path.relative_to(ROOT)}")
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


# ---------------------------------------------------------------- parse
def norm_code(c):
    return re.sub(r"\s+", "", c).upper()


def norm_text(t):
    return re.sub(r"\s+", " ", t).strip()


def to_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_sems(v):
    out = []
    for p in v.split(";"):
        p = p.strip()
        if not p:
            continue  # empty = semester not specified in source
        if p.isdigit():
            out.append(int(p))
        else:
            err(f"non-numeric semester value '{v}'")
    return out


def attach_source(rec, sources):
    s = sources.get(rec.get("source_id", ""))
    if not s:
        return
    rec["source_type"] = s["source_type"]
    rec["retrieved_on"] = s["retrieved_on"]
    rec["source_url"] = rec.get("url") or s["url"]


def parse(sources):
    d = {}
    d["courses"] = []
    for r in read("courses"):
        r["code"] = norm_code(r["code"])
        r["title"] = norm_text(r["title"])
        r["credits_raw"] = r["credits"]
        r["credits"] = to_num(r["credits"])
        r["semesters"] = parse_sems(r["semester_offered"])
        r["semester_labels"] = [f"Sem {ROMAN.get(s, s)}" for s in r["semesters"]]
        r["objectives"] = norm_text(r["objectives"])
        r["prereq_consent_required"] = r["prereq_consent_required"].lower() == "yes"
        attach_source(r, sources)
        d["courses"].append(r)
    d["prerequisites"] = []
    for r in read("prerequisites"):
        r["course"], r["requires"] = norm_code(r["course"]), norm_code(r["requires"])
        attach_source(r, sources)
        d["prerequisites"].append(r)
    d["slots"] = []
    for r in read("curriculum_slots"):
        r["course_code"] = norm_code(r["course_code"])
        r["semester_n"] = int(r["semester"]) if r["semester"].isdigit() else None
        r["credits_n"] = to_num(r["credits"])
        attach_source(r, sources)
        d["slots"].append(r)
    d["skills"] = read("skills")
    d["course_skills"] = read("course_skills")
    d["rules"] = read("rules")
    d["resources"] = read("resources")
    d["resource_skills"] = read("resource_skills")
    # Optional tables: leave empty until source-backed outcomes/exercises are added.
    d["learning_outcomes"] = read("learning_outcomes", required=False)
    d["exercises"] = read("exercises", required=False)
    for k in ["skills", "course_skills", "rules", "resources", "resource_skills", "learning_outcomes", "exercises"]:
        for r in d[k]:
            if "course" in r:
                r["course"] = norm_code(r["course"])
            attach_source(r, sources)
    res_url = {r["resource_id"]: r["url"] for r in d["resources"]}
    for r in d["resource_skills"]:
        # S4 is a row-level source: the traceable URL is the resource's own URL
        if r["source_id"] == "S4":
            r["source_url"] = res_url.get(r["resource"], "")
    for r in d["rules"]:
        r["numeric_limit_n"] = to_num(r["numeric_limit"])
    # These are derived syllabus-topic records, NOT official institute modules.
    d["modules"] = []
    for c in d["courses"]:
        for i, topic in enumerate([t.strip() for t in c["objectives"].split(";") if t.strip()], 1):
            d["modules"].append({"module_id": f"{c['code']}-TOPIC-{i:02d}", "parent_course": c["code"],
                                 "order": i, "summary": topic, "module_kind": "derived_syllabus_topic",
                                 "is_official_module": False,
                                 "derivation_method": "split_semicolon_separated_course_syllabus_text",
                                 "source_id": c["source_id"], "source_ref": c["source_ref"],
                                 "source_url": c.get("source_url", ""),
                                 "retrieved_on": c.get("retrieved_on", ""),
                                 "source_type": "derived"})
    return d


# ---------------------------------------------------------------- validate
def find_cycle(edges):
    graph = defaultdict(list)
    for a, b in edges:
        graph[a].append(b)
    state = {}

    def dfs(n, path):
        state[n] = 1
        for m in graph[n]:
            if state.get(m) == 1:
                return path + [n, m]
            if m not in state:
                c = dfs(m, path + [n])
                if c:
                    return c
        state[n] = 2
        return None

    for n in list(graph):
        if n not in state:
            c = dfs(n, [])
            if c:
                return c
    return None


def validate(d, sources):
    codes = {}
    for c in d["courses"]:
        if c["code"] in codes:
            err(f"duplicate course code {c['code']}")
        codes[c["code"]] = c
        if not CODE_RE.match(c["code"]):
            err(f"bad course code format '{c['code']}'")
        if c["credits"] is None or c["credits"] <= 0:
            err(f"{c['code']}: non-numeric or non-positive credits '{c['credits_raw']}'")
        if not c["objectives"]:
            warn(f"{c['code']}: empty syllabus text")
    for name in ["courses", "prerequisites", "slots", "skills", "course_skills", "rules", "resources", "resource_skills", "learning_outcomes", "exercises"]:
        for r in d[name]:
            if r.get("source_id") not in sources:
                err(f"{name}: record without valid source_id: {r}")
            elif not r.get("source_url"):
                err(f"{name}: record with no source URL: {r.get('code') or r.get('rule_id') or r.get('resource_id') or r.get('skill_id') or r.get('course')}")
            if not r.get("source_ref"):
                err(f"{name}: record missing source_ref")
    # Relationships must carry their OWN provenance, not merely inherit the
    # provenance of the linked course/resource. This is especially important
    # for author-curated skill mappings.
    for table in ("prerequisites", "course_skills", "resource_skills"):
        for row in d[table]:
            label = row.get("course") or row.get("resource") or "relationship"
            if not row.get("source_id") or row.get("source_id") not in sources:
                err(f"{table} {label}: relationship has no valid source_id")
            if not row.get("source_ref"):
                err(f"{table} {label}: relationship has no source_ref explaining the evidence")
            if not row.get("source_url"):
                err(f"{table} {label}: relationship has no source_url")
    # Explicit learning outcomes are optional. Never infer them from topic lists.
    outcome_ids = set()
    for row in d["learning_outcomes"]:
        oid = row.get("outcome_id", "")
        if not oid or oid in outcome_ids:
            err(f"learning_outcomes: missing or duplicate outcome_id '{oid}'")
        outcome_ids.add(oid)
        if row.get("course") not in codes:
            err(f"learning_outcomes {oid}: unknown course {row.get('course')}")
        if not row.get("outcome"):
            err(f"learning_outcomes {oid}: empty outcome")
        if not row.get("source_id") or row.get("source_id") not in sources or not row.get("source_ref") or not row.get("source_url"):
            err(f"learning_outcomes {oid}: missing traceable source_id/source_ref/source_url")
    # Exercises are bonus content. Keep author-created exercises explicitly labelled.
    exercise_ids = set()
    for row in d["exercises"]:
        eid = row.get("exercise_id", "")
        if not eid or eid in exercise_ids:
            err(f"exercises: missing or duplicate exercise_id '{eid}'")
        exercise_ids.add(eid)
        if row.get("skill") not in {x["skill_id"] for x in d["skills"]}:
            err(f"exercise {eid}: unknown skill {row.get('skill')}")
        if not row.get("question") or not row.get("difficulty"):
            err(f"exercise {eid}: question and difficulty are required")
        if not row.get("source_id") or row.get("source_id") not in sources or not row.get("source_ref") or not row.get("source_url"):
            err(f"exercise {eid}: missing traceable source_id/source_ref/source_url")
    # prerequisites
    edges = []
    for p in d["prerequisites"]:
        a, b = p["course"], p["requires"]
        if a not in codes:
            err(f"prerequisite row for unknown course {a}")
        if b not in codes:
            err(f"{a} requires missing course {b}")
        if a == b:
            err(f"{a} requires itself")
        if p["kind"] not in PREREQ_KINDS:
            err(f"{a}->{b}: bad prerequisite kind '{p['kind']}'")
        edges.append((a, b))
        if a in codes and b in codes:
            a_sems, b_sems = codes[a]["semesters"], codes[b]["semesters"]
            if not a_sems or not b_sems:
                skipped_order.append(f"{a}->{b}")
            else:
                sa, sb = min(a_sems), min(b_sems)
                if sb > sa:
                    err(f"{a} (Sem {sa}) requires {b} offered later (Sem {sb})")
                elif sb == sa and p["kind"] != "concurrent_ok":
                    err(f"{a} and prerequisite {b} are in the same semester {sa} but edge is not concurrent_ok")
    if skipped_order:
        warn(f"semester-order check skipped for {len(skipped_order)} edges (course has no semester in source): " + ", ".join(skipped_order))
    cyc = find_cycle(edges)
    if cyc:
        err("prerequisite cycle: " + " -> ".join(cyc))
    # skills
    skills = {s["skill_id"] for s in d["skills"]}
    for s in d["skills"]:
        if s["parent_skill"] and s["parent_skill"] not in skills:
            err(f"skill {s['skill_id']} has missing parent {s['parent_skill']}")
    cs_by_course = defaultdict(int)
    skill_cov = defaultdict(int)
    for l in d["course_skills"]:
        if l["course"] not in codes:
            err(f"course_skills references unknown course {l['course']}")
        if l["skill"] not in skills:
            err(f"course_skills references unknown skill {l['skill']}")
        cs_by_course[l["course"]] += 1
        skill_cov[l["skill"]] += 1
    rids = {r["resource_id"] for r in d["resources"]}
    for l in d["resource_skills"]:
        if l["resource"] not in rids:
            err(f"resource_skills references unknown resource {l['resource']}")
        if l["skill"] not in skills:
            err(f"resource_skills references unknown skill {l['skill']}")
        skill_cov[l["skill"]] += 1
    for c in d["courses"]:
        if not cs_by_course[c["code"]]:
            warn(f"{c['code']}: no skill mapping (foundation or non-CS course)")
    for s in skills:
        if not skill_cov[s]:
            warn(f"skill {s} has no course or resource")
    # resources
    seen = set()
    for r in d["resources"]:
        if r["resource_id"] in seen:
            err(f"duplicate resource id {r['resource_id']}")
        seen.add(r["resource_id"])
        if not r["licence"]:
            err(f"{r['resource_id']}: missing licence")
        if not r["url"].startswith("https://"):
            err(f"{r['resource_id']}: url is not https")
        if to_num(r["duration_hours_est"]) is None:
            err(f"{r['resource_id']}: non-numeric duration")
        if r["url_verified"].lower() != "true":
            warn(f"{r['resource_id']}: URL not yet verified")
    # rules
    rseen = set()
    for r in d["rules"]:
        if r["rule_id"] in rseen:
            err(f"duplicate rule id {r['rule_id']}")
        rseen.add(r["rule_id"])
        if r["applies_to_scheme"] not in SCHEMES:
            err(f"{r['rule_id']}: bad scheme")
        if r["numeric_limit"] and r["numeric_limit_n"] is None:
            err(f"{r['rule_id']}: non-numeric limit")
    # curriculum slots
    per_sem = defaultdict(float)
    per_cat = defaultdict(float)
    for s in d["slots"]:
        if s["credits_n"] is None:
            err(f"slot with non-numeric credits: {s}")
            continue
        per_sem[s["semester_n"]] += s["credits_n"]
        per_cat[SLOT_TO_RULE_SUBJECT.get(s["category"], s["category"])] += s["credits_n"]
        if s["course_code"]:
            c = codes.get(s["course_code"])
            if not c:
                err(f"slot references unknown course {s['course_code']}")
            else:
                if c["credits"] != s["credits_n"]:
                    err(f"slot credits {s['credits_n']} != course credits {c['credits']} for {c['code']}")
                if s["semester_n"] not in c["semesters"]:
                    err(f"{c['code']} slotted in Sem {s['semester_n']} but offered {c['semesters']}")
    load_rule = next((r for r in d["rules"] if r["rule_id"] == "R009"), None)
    if load_rule is None or load_rule["numeric_limit_n"] is None:
        warn("semester-load check skipped: rule R009 with a numeric limit is missing")
    else:
        legacy_load = load_rule["numeric_limit_n"]
        for sem, tot in sorted(per_sem.items()):
            if tot != legacy_load:
                err(f"Sem {sem} slot credits sum to {tot}, expected {legacy_load}")
    for r in d["rules"]:
        if r["category"] == "credit_requirement" and r["applies_to_scheme"] == "legacy":
            tot = sum(per_cat.values()) if r["subject"] == "TOTAL" else per_cat.get(r["subject"], 0)
            if tot != r["numeric_limit_n"]:
                err(f"curriculum {r['subject']} credits {tot} != rule {r['rule_id']} limit {r['numeric_limit_n']}")
    return per_sem, per_cat


# ---------------------------------------------------------------- chunk
def split_topics(topics, header):
    chunks, cur = [], []
    for t in topics:
        trial = "; ".join(cur + [t])
        if cur and len(header) + len(trial) > MAX_CHUNK_CHARS:
            chunks.append("; ".join(cur))
            cur = [t]
        else:
            cur.append(t)
    if cur:
        chunks.append("; ".join(cur))
    return chunks


def chunk(d):
    skills_by_course = defaultdict(list)
    for l in d["course_skills"]:
        skills_by_course[l["course"]].append(l["skill"])
    prereq = defaultdict(list)
    for p in d["prerequisites"]:
        prereq[p["course"]].append(f"{p['requires']}" + (" (may be concurrent)" if p["kind"] == "concurrent_ok" else ""))
    out = []
    for c in d["courses"]:
        header = (f"{c['code']} {c['title']} ({int(c['credits'])} credits, {', '.join(c['semester_labels']) or 'semester not specified in source'}, "
                  f"{c['category']}). Prerequisites: {', '.join(prereq[c['code']]) or 'none listed'}"
                  + (" (instructor consent required)." if c["prereq_consent_required"] else ".") + " Topics: ")
        topics = [t.strip() for t in c["objectives"].split(";") if t.strip()]
        for i, body in enumerate(split_topics(topics, header), 1):
            out.append({"chunk_id": f"{c['code']}-syl-{i:02d}", "parent_id": c["code"], "type": "syllabus",
                        "text": header + body,
                        "meta": {"course_code": c["code"], "semesters": c["semesters"], "category": c["category"],
                                 "course_type": c["course_type"], "programme_scope": c["programme_scope"],
                                 "skills": skills_by_course[c["code"]], "source_id": c["source_id"],
                                 "source_url": c.get("source_url", ""), "source_ref": c["source_ref"],
                                 "retrieved_on": c.get("retrieved_on", "")}})
    for outcome in d["learning_outcomes"]:
        out.append({"chunk_id": f"{outcome['outcome_id']}-outcome", "parent_id": outcome["course"],
                    "type": "learning_outcome", "text": outcome["outcome"],
                    "meta": {"course_code": outcome["course"], "outcome_id": outcome["outcome_id"],
                             "source_id": outcome["source_id"], "source_ref": outcome["source_ref"],
                             "source_url": outcome.get("source_url", ""),
                             "retrieved_on": outcome.get("retrieved_on", "")}})
    for exercise in d["exercises"]:
        out.append({"chunk_id": f"{exercise['exercise_id']}-exercise", "parent_id": exercise["exercise_id"],
                    "type": "exercise", "text": exercise["question"],
                    "meta": {"skill": exercise["skill"], "difficulty": exercise["difficulty"],
                             "answer_key": exercise.get("answer_key", ""),
                             "source_id": exercise["source_id"], "source_ref": exercise["source_ref"],
                             "source_url": exercise.get("source_url", ""),
                             "retrieved_on": exercise.get("retrieved_on", "")}})
    for r in d["rules"]:
        out.append({"chunk_id": f"{r['rule_id']}-rule", "parent_id": r["rule_id"], "type": "rule",
                    "text": f"[{r['category']}/{r['subject']}] {r['text']} (applies to: {r['applies_to_scheme']} scheme)",
                    "meta": {"category": r["category"], "subject": r["subject"], "scheme": r["applies_to_scheme"],
                             "numeric_limit": r["numeric_limit_n"], "unit": r["unit"], "source_id": r["source_id"],
                             "source_url": r.get("source_url", ""), "source_ref": r["source_ref"],
                             "retrieved_on": r.get("retrieved_on", "")}})
    rs = defaultdict(list)
    for l in d["resource_skills"]:
        rs[l["resource"]].append(l["skill"])
    for r in d["resources"]:
        out.append({"chunk_id": f"{r['resource_id']}-res", "parent_id": r["resource_id"], "type": "resource",
                    "text": f"{r['title']} by {r['provider']} ({r['format']}, about {r['duration_hours_est']} hours, licence {r['licence']}). {r['description']}.",
                    "meta": {"skills": rs[r["resource_id"]], "licence": r["licence"], "format": r["format"],
                             "duration_hours_est": to_num(r["duration_hours_est"]), "url_verified": r["url_verified"].lower() == "true",
                             "source_id": r["source_id"], "source_url": r["url"], "retrieved_on": r.get("retrieved_on", "")}})
    return out


# ---------------------------------------------------------------- export
def write_csv(name, rows, cols):
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(r[k]) if isinstance(r.get(k), (list, dict)) else r.get(k, "")) for k in cols})
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


def fill_rates(rows, cols):
    if not rows:
        return {}
    return {c: round(100 * sum(1 for r in rows if str(r.get(c, "")).strip() not in ("", "None")) / len(rows), 1) for c in cols}


def export(d, chunks, per_sem, per_cat):
    src = ["source_id", "source_ref", "source_url", "source_type", "retrieved_on"]
    spec = {
        "courses": (d["courses"], ["code", "title", "department", "credits", "semesters", "semester_basis", "course_type", "category", "mode", "programme_scope", "prereq_consent_required", "objectives"] + src),
        "prerequisites": (d["prerequisites"], ["course", "requires", "kind"] + src),
        "curriculum_slots": (d["slots"], ["semester", "slot_label", "course_code", "category", "credits"] + src),
        "skills": (d["skills"], ["skill_id", "name", "level", "parent_skill"] + src),
        "course_skills": (d["course_skills"], ["course", "skill", "depth"] + src),
        "rules": (d["rules"], ["rule_id", "category", "subject", "text", "numeric_limit", "unit", "applies_to_scheme"] + src),
        "resources": (d["resources"], ["resource_id", "title", "provider", "licence", "format", "duration_hours_est", "url", "url_verified", "description"] + src),
        "resource_skills": (d["resource_skills"], ["resource", "skill", "level"] + src),
        "modules": (d["modules"], ["module_id", "parent_course", "order", "summary", "module_kind", "is_official_module", "derivation_method"] + src),
        "learning_outcomes": (d["learning_outcomes"], ["outcome_id", "course", "outcome"] + src),
        "exercises": (d["exercises"], ["exercise_id", "skill", "difficulty", "question", "answer_key"] + src),
    }
    quality = {"counts": {}, "fill_rate_pct": {}}
    for name, (rows, cols) in spec.items():
        write_csv(name, rows, cols)
        quality["counts"][name] = len(rows)
        quality["fill_rate_pct"][name] = fill_rates(rows, cols)
    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    quality["counts"]["chunks"] = len(chunks)
    quality["chunks_by_type"] = {t: sum(1 for c in chunks if c["type"] == t) for t in {c["type"] for c in chunks}}
    quality["max_chunk_chars"] = max(len(c["text"]) for c in chunks)
    quality["credits_per_semester"] = {str(k): v for k, v in sorted(per_sem.items())}
    quality["credits_per_category"] = dict(per_cat)
    quality["urls_unverified"] = sum(1 for r in d["resources"] if r["url_verified"].lower() != "true")
    quality["derived_topics_not_official_modules"] = len(d["modules"])
    quality["explicit_learning_outcomes"] = len(d["learning_outcomes"])
    quality["optional_exercises"] = len(d["exercises"])
    quality["source_url_specificity"] = {s: v for s, v in [(s["source_id"], s["url_specificity"]) for s in read("sources")]}
    quality["errors"], quality["warnings"] = errors, warnings
    (OUT / "quality_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    return quality


def main():
    ingest()
    sources = {s["source_id"]: s for s in read("sources")}
    d = parse(sources)
    per_sem, per_cat = validate(d, sources)
    chunks = chunk(d)
    q = export(d, chunks, per_sem, per_cat)
    print(f"courses={q['counts']['courses']} rules={q['counts']['rules']} resources={q['counts']['resources']} "
          f"chunks={q['counts']['chunks']} modules={q['counts']['modules']}")
    for w in warnings:
        print("WARN ", w)
    if errors:
        for e in errors:
            print("ERROR", e)
        sys.exit(f"VALIDATION FAILED with {len(errors)} error(s); see data/processed/quality_report.json")
    print("validation passed")


if __name__ == "__main__":
    main()
