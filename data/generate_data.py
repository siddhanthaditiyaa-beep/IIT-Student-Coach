import csv
import random
import uuid
from datetime import datetime, timedelta
from content_physics import PHYSICS
from content_chemistry import CHEMISTRY
from content_maths import MATHS

from extra_physics import EXTRA_PHYSICS
from extra_chemistry import EXTRA_CHEMISTRY
from extra_maths import EXTRA_MATHS

EXTRA = {**EXTRA_PHYSICS, **EXTRA_CHEMISTRY, **EXTRA_MATHS}
CHAPTERS = []
for subject, chapter, prereq, notes, questions in PHYSICS + CHEMISTRY + MATHS:
    extra_notes, extra_questions = EXTRA[chapter]
    CHAPTERS.append((subject, chapter, prereq, notes + extra_notes, questions + extra_questions))

concept_rows = []
question_rows = []
cn = 0
qn = 0

for subject, chapter, prereq, notes, questions in CHAPTERS:
    first_cn = cn + 1
    for text, difficulty, misconception in notes:
        cn += 1
        concept_rows.append({
            "concept_id": f"CN-{cn:04d}",
            "resource_id": f"RES-{cn:04d}",
            "subject": subject,
            "chapter": chapter,
            "prerequisite_chapter": prereq or "",
            "resource_text": text,
            "difficulty": difficulty,
            "common_misconception": misconception,
        })
    for difficulty, cidx, qtext, steps, answer, hint, err in questions:
        qn += 1
        question_rows.append({
            "question_id": f"Q-{qn:05d}",
            "concept_id": f"CN-{first_cn + cidx - 1:04d}",
            "subject": subject,
            "chapter": chapter,
            "difficulty": difficulty,
            "question_text": qtext,
            "solution_steps": steps,
            "error_type_if_wrong": err,
            "hint": hint,
            "final_answer": answer,
        })

rng = random.Random(2026)
anchor = datetime(2026, 10, 15, 18, 0, 0)
aliases = [f"STU-{i:03d}" for i in range(1, 13)]
chapter_names = [c[1] for c in CHAPTERS]
by_chapter = {}
for q in question_rows:
    by_chapter.setdefault(q["chapter"], []).append(q)

attempt_rows = []
for alias in aliases:
    strong = set(rng.sample(chapter_names, 5))
    weak = set(rng.sample([c for c in chapter_names if c not in strong], 5))
    focus = list(strong | weak) + rng.sample(chapter_names, 8)
    n_attempts = rng.randint(28, 46)
    for _ in range(n_attempts):
        chapter = rng.choice(focus)
        q = rng.choice(by_chapter[chapter])
        p = 0.88 if chapter in strong else 0.22 if chapter in weak else 0.55
        if q["difficulty"] == "hard":
            p -= 0.12
        elif q["difficulty"] == "easy":
            p += 0.07
        ok = rng.random() < p
        ts = anchor - timedelta(days=rng.randint(0, 28), minutes=rng.randint(0, 600))
        attempt_rows.append({
            "attempt_id": uuid.UUID(int=rng.getrandbits(128)).hex[:8],
            "student_alias": alias,
            "question_id": q["question_id"],
            "concept_id": q["concept_id"],
            "subject": q["subject"],
            "chapter": q["chapter"],
            "attempt_status": "correct" if ok else "incorrect",
            "error_type": "" if ok else q["error_type_if_wrong"],
            "time_spent_sec": rng.randint(45, 420),
            "timestamp": ts.isoformat(timespec="seconds"),
        })


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


write_csv("concept_notes.csv", concept_rows)
write_csv("questions.csv", question_rows)
write_csv("seed_attempts.csv", attempt_rows)
print(f"concept_notes.csv: {len(concept_rows)} rows")
print(f"questions.csv: {len(question_rows)} rows")
print(f"seed_attempts.csv: {len(attempt_rows)} rows")
