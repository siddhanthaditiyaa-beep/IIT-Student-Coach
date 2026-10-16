from datetime import datetime
import json
import uuid

DECAY = 0.85
WEAK_THRESHOLD = 0.55
PRIOR_WEIGHT = 2.0

def recalc_mastery(conn, student_alias: str, concept_id: str):
    rows = conn.execute(
        "SELECT attempt_status, timestamp FROM attempts "
        "WHERE student_alias=? AND concept_id=? ORDER BY timestamp DESC",
        (student_alias, concept_id)
    ).fetchall()

    if not rows:
        score = 0.5
    else:
        weighted_sum, weight_total = 0.5 * PRIOR_WEIGHT, PRIOR_WEIGHT
        weight = 1.0
        for r in rows:
            val = 1.0 if r["attempt_status"] == "correct" else 0.0
            weighted_sum += val * weight
            weight_total += weight
            weight *= DECAY
        score = round(weighted_sum / weight_total, 3)

    chapter_row = conn.execute(
        "SELECT subject, chapter FROM concept_notes WHERE concept_id=?", (concept_id,)
    ).fetchone()
    subject, chapter = (chapter_row["subject"], chapter_row["chapter"]) if chapter_row else ("", "")

    conn.execute(
        "INSERT INTO mastery (student_alias, concept_id, chapter, subject, mastery_score, updated_at) "
        "VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(student_alias, concept_id) DO UPDATE SET "
        "mastery_score=excluded.mastery_score, updated_at=excluded.updated_at",
        (student_alias, concept_id, chapter, subject, score, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    return score

def chapter_mastery(conn, student_alias: str):
    all_chapters = conn.execute(
        "SELECT DISTINCT subject, chapter, prerequisite_chapter FROM concept_notes"
    ).fetchall()

    scored = conn.execute(
        "SELECT chapter, AVG(mastery_score) as avg_score FROM mastery "
        "WHERE student_alias=? GROUP BY chapter", (student_alias,)
    ).fetchall()
    scored_map = {r["chapter"]: r["avg_score"] for r in scored}

    result = []
    for row in all_chapters:
        chapter = row["chapter"]
        result.append({
            "subject": row["subject"],
            "chapter": chapter,
            "prerequisite_chapter": row["prerequisite_chapter"] or None,
            "mastery_score": round(scored_map.get(chapter, 0.5), 3),
            "attempted": chapter in scored_map,
        })
    return result

def build_study_plan(conn, student_alias: str, top_n: int = 5):
    chapters = chapter_mastery(conn, student_alias)
    by_name = {c["chapter"]: c for c in chapters}
    has_any_data = any(c["attempted"] for c in chapters)

    plan, seen = [], set()

    def add(info, reason):
        if info["chapter"] in seen or len(plan) >= top_n:
            return
        plan.append(_plan_item(info, reason=reason, personalized=has_any_data))
        seen.add(info["chapter"])

    if not has_any_data:
        for c in chapters:
            add(c, "standard order - no attempts yet to personalize on")
    else:
        weak = sorted(
            [c for c in chapters if c["attempted"] and c["mastery_score"] < WEAK_THRESHOLD],
            key=lambda c: c["mastery_score"],
        )
        for c in weak:
            prereq = by_name.get(c["prerequisite_chapter"]) if c["prerequisite_chapter"] else None
            if prereq and prereq["chapter"] not in seen:
                if prereq["attempted"] and prereq["mastery_score"] < WEAK_THRESHOLD:
                    add(prereq, "weak prerequisite - resolve first")
                elif not prereq["attempted"]:
                    add(prereq, "prerequisite not practised yet - build the foundation first")
            add(c, "low mastery")
        fresh = [c for c in chapters if not c["attempted"]]
        for c in fresh:
            add(c, "not started yet")
        improving = sorted(
            [c for c in chapters if c["attempted"] and c["mastery_score"] < 0.75],
            key=lambda c: c["mastery_score"],
        )
        for c in improving:
            add(c, "keep improving")

    plan_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO study_plans (plan_id, student_alias, plan_json, generated_at) VALUES (?,?,?,?)",
        (plan_id, student_alias, json.dumps(plan), datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    return {"plan_id": plan_id, "student_alias": student_alias, "personalized": has_any_data, "plan": plan}

def _plan_item(chapter_info, reason, personalized=True):
    n_problems = 5 if chapter_info["mastery_score"] < 0.4 else 3
    verb = "Learn the concept and solve" if not chapter_info.get("attempted") else "Revise concept and solve"
    return {
        "subject": chapter_info["subject"],
        "chapter": chapter_info["chapter"],
        "mastery_score": chapter_info["mastery_score"],
        "reason": reason,
        "personalized": personalized,
        "recommended_task": f"{verb} {n_problems} problems",
    }
