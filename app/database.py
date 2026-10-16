import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "coach.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SCHEMA = """
CREATE TABLE IF NOT EXISTS concept_notes (
    concept_id TEXT PRIMARY KEY,
    resource_id TEXT,
    subject TEXT,
    chapter TEXT,
    prerequisite_chapter TEXT,
    resource_text TEXT,
    difficulty TEXT,
    common_misconception TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    concept_id TEXT,
    subject TEXT,
    chapter TEXT,
    difficulty TEXT,
    question_text TEXT,
    solution_steps TEXT,
    error_type_if_wrong TEXT,
    hint TEXT,
    final_answer TEXT,
    FOREIGN KEY(concept_id) REFERENCES concept_notes(concept_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    student_alias TEXT,
    question_id TEXT,
    concept_id TEXT,
    subject TEXT,
    chapter TEXT,
    attempt_status TEXT,       -- 'correct' | 'incorrect'
    error_type TEXT,
    time_spent_sec INTEGER,
    timestamp TEXT,
    model_version TEXT DEFAULT 'rules-v1'
);

CREATE TABLE IF NOT EXISTS mastery (
    student_alias TEXT,
    concept_id TEXT,
    chapter TEXT,
    subject TEXT,
    mastery_score REAL,
    updated_at TEXT,
    PRIMARY KEY (student_alias, concept_id)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT PRIMARY KEY,
    student_alias TEXT,
    role TEXT,                 -- 'user' | 'assistant'
    message TEXT,
    guardrail_flag TEXT,
    citations TEXT,
    confidence REAL,
    token_estimate INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS study_plans (
    plan_id TEXT PRIMARY KEY,
    student_alias TEXT,
    plan_json TEXT,
    generated_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_alias TEXT,
    actor_role TEXT DEFAULT 'student',
    action TEXT,
    target TEXT,
    details TEXT,
    timestamp TEXT
);
"""

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _needs_rebuild(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
    return bool(cols) and "hint" not in cols

def init_db():
    conn = get_conn()
    if _needs_rebuild(conn):
        for table in ("audit_log", "study_plans", "chat_sessions", "mastery", "attempts", "questions", "concept_notes"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    conn.executescript(SCHEMA)
    conn.commit()

    cur = conn.execute("SELECT COUNT(*) FROM concept_notes")
    if cur.fetchone()[0] == 0:
        _load_csv(conn, "concept_notes.csv", "concept_notes",
                  ["concept_id", "resource_id", "subject", "chapter",
                   "prerequisite_chapter", "resource_text", "difficulty", "common_misconception"])
        _load_csv(conn, "questions.csv", "questions",
                  ["question_id", "concept_id", "subject", "chapter", "difficulty",
                   "question_text", "solution_steps", "error_type_if_wrong", "hint", "final_answer"])
        _load_seed_attempts(conn)
        conn.commit()
        print("Seed data loaded into coach.db")
    conn.close()

def _load_csv(conn, filename, table, columns):
    path = os.path.join(DATA_DIR, filename)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        placeholders = ",".join(["?"] * len(columns))
        col_list = ",".join(columns)
        rows = [[row[c] for c in columns] for row in reader]
        conn.executemany(f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})", rows)

def _load_seed_attempts(conn):
    path = os.path.join(DATA_DIR, "seed_attempts.csv")
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append([
                row["attempt_id"], row["student_alias"], row["question_id"], row["concept_id"],
                row["subject"], row["chapter"], row["attempt_status"], row["error_type"],
                int(row["time_spent_sec"]), row["timestamp"],
            ])
        conn.executemany(
            "INSERT OR IGNORE INTO attempts "
            "(attempt_id, student_alias, question_id, concept_id, subject, chapter, "
            "attempt_status, error_type, time_spent_sec, timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
