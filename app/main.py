import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .database import init_db, get_conn
from .schemas import AttemptIn, ChatIn, ActionIn
from . import mastery, guardrails, genai

app = FastAPI(title="IIT Student Coach Chatbot API")

TEACHER_KEY = os.environ.get("TEACHER_KEY", "teacher123")

def require_teacher_key(x_teacher_key: str):
    if x_teacher_key != TEACHER_KEY:
        raise HTTPException(403, "Invalid or missing teacher key - this endpoint is restricted.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    conn = get_conn()
    pairs = conn.execute(
        "SELECT DISTINCT student_alias, concept_id FROM attempts"
    ).fetchall()
    for row in pairs:
        mastery.recalc_mastery(conn, row["student_alias"], row["concept_id"])
    conn.close()

def log_audit(conn, actor_alias, action, target, details="", actor_role="student"):
    conn.execute(
        "INSERT INTO audit_log (actor_alias, actor_role, action, target, details, timestamp) VALUES (?,?,?,?,?,?)",
        (actor_alias, actor_role, action, target, details, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()

@app.get("/health")
def health():
    return {"status": "ok", "data_version": 2, "time": datetime.now().isoformat(timespec="seconds")}

@app.get("/concepts")
def list_concepts(subject: str = None, chapter: str = None):
    conn = get_conn()
    sql = "SELECT * FROM concept_notes WHERE 1=1"
    params = []
    if subject:
        sql += " AND subject=?"
        params.append(subject)
    if chapter:
        sql += " AND chapter=?"
        params.append(chapter)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/questions")
def list_questions(concept_id: str = None, chapter: str = None, subject: str = None):
    conn = get_conn()
    sql = "SELECT question_id, concept_id, subject, chapter, difficulty, question_text FROM questions WHERE 1=1"
    params = []
    if concept_id:
        sql += " AND concept_id=?"
        params.append(concept_id)
    if chapter:
        sql += " AND chapter=?"
        params.append(chapter)
    if subject:
        sql += " AND subject=?"
        params.append(subject)
    sql += " ORDER BY question_id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/sources/{resource_id}")
def get_source(resource_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT resource_id, subject, chapter, resource_text, difficulty, common_misconception "
        "FROM concept_notes WHERE resource_id=?", (resource_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "source not found")
    return dict(row)

@app.get("/summary/{alias}")
def student_summary(alias: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN attempt_status='correct' THEN 1 ELSE 0 END) AS correct, "
        "MAX(timestamp) AS last_active FROM attempts WHERE student_alias=?", (alias,)
    ).fetchone()
    conn.close()
    total = row["total"] or 0
    correct = row["correct"] or 0
    return {
        "student_alias": alias,
        "total_attempts": total,
        "correct": correct,
        "accuracy": round(correct / total, 3) if total else None,
        "last_active": row["last_active"],
    }

@app.post("/attempts")
def submit_attempt(attempt: AttemptIn):
    if attempt.attempt_status not in ("correct", "incorrect"):
        raise HTTPException(400, "attempt_status must be 'correct' or 'incorrect'")

    conn = get_conn()
    q = conn.execute("SELECT * FROM questions WHERE question_id=?", (attempt.question_id,)).fetchone()
    if not q:
        conn.close()
        raise HTTPException(404, "question_id not found")

    attempt_id = str(uuid.uuid4())[:8]
    error_type = q["error_type_if_wrong"] if attempt.attempt_status == "incorrect" else ""
    conn.execute(
        "INSERT INTO attempts (attempt_id, student_alias, question_id, concept_id, subject, chapter, "
        "attempt_status, error_type, time_spent_sec, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (attempt_id, attempt.student_alias, attempt.question_id, q["concept_id"], q["subject"],
         q["chapter"], attempt.attempt_status, error_type, attempt.time_spent_sec,
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    new_score = mastery.recalc_mastery(conn, attempt.student_alias, q["concept_id"])
    log_audit(conn, attempt.student_alias, "submit_attempt", attempt.question_id,
              f"status={attempt.attempt_status}")
    conn.close()

    return {
        "attempt_id": attempt_id,
        "concept_id": q["concept_id"],
        "attempt_status": attempt.attempt_status,
        "error_type": error_type or None,
        "updated_mastery_score": new_score,
        "next_step": "Ask the coach for a hint" if attempt.attempt_status == "incorrect" else "Try a harder question next",
    }

@app.post("/coach/chat")
def coach_chat(chat: ChatIn):
    conn = get_conn()
    flags = guardrails.check_input(conn, chat.message)

    result = genai.generate_coaching_response(
        conn, chat.student_alias, chat.message, chat.subject, chat.chapter,
        chat.concept_id, chat.last_question_id, chat.reveal_full_solution, flags
    )

    session_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO chat_sessions (session_id, student_alias, role, message, guardrail_flag, "
        "citations, confidence, token_estimate, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (session_id, chat.student_alias, "assistant", result["response"], result["guardrail_flag"],
         ",".join(result["citations"]), result["confidence"], result["token_estimate"],
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    log_audit(conn, chat.student_alias, "coach_chat", session_id,
              f"guardrail={result['guardrail_flag'] or 'none'}")
    conn.close()

    return {
        "session_id": session_id,
        "response": result["response"],
        "citations": result["citations"],
        "confidence": result["confidence"],
        "hint_level": result["hint_level"],
        "token_estimate": result["token_estimate"],
        "guardrail_flag": result["guardrail_flag"] or None,
        "disclaimer": "AI-generated coaching guidance - verify with your teacher for exam-critical decisions.",
    }

@app.get("/study-plan/{alias}")
def study_plan(alias: str):
    conn = get_conn()
    plan = mastery.build_study_plan(conn, alias)
    log_audit(conn, alias, "generate_study_plan", plan["plan_id"])
    conn.close()
    return plan

@app.get("/mastery/{alias}")
def mastery_dashboard(alias: str):
    conn = get_conn()
    data = mastery.chapter_mastery(conn, alias)
    conn.close()
    return {"student_alias": alias, "chapters": data}

@app.post("/actions/log")
def log_action(action: ActionIn, x_teacher_key: str = Header(default="")):
    require_teacher_key(x_teacher_key)
    conn = get_conn()
    log_audit(conn, action.actor_alias, action.action, action.target, action.details, action.actor_role)
    conn.close()
    return {"status": "logged", "timestamp": datetime.now().isoformat(timespec="seconds")}

@app.get("/audit")
def get_audit(limit: int = Query(50, le=500), x_teacher_key: str = Header(default="")):
    require_teacher_key(x_teacher_key)
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/error-analysis/{alias}")
def error_analysis(alias: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT chapter, error_type, COUNT(*) as frequency FROM attempts "
        "WHERE student_alias=? AND attempt_status='incorrect' AND error_type != '' "
        "GROUP BY chapter, error_type ORDER BY frequency DESC LIMIT 10", (alias,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/ocr/extract")
async def ocr_extract(file: UploadFile = File(...)):
    image_bytes = await file.read()
    ocr_text = await genai.extract_text_from_image(image_bytes)
    conn = get_conn()
    matched = genai.match_known_question(conn, ocr_text) if ocr_text else None
    conn.close()
    return {
        "ocr_text": ocr_text,
        "matched_question_id": matched["question_id"] if matched else None,
    }

@app.post("/coach/solve-image")
async def solve_image(student_alias: str = Form(...), file: UploadFile = File(...)):
    image_bytes = await file.read()
    ocr_text = await genai.extract_text_from_image(image_bytes)

    if not ocr_text:
        return {
            "ocr_text": "",
            "response": "I couldn't read any text from that image - try a clearer, well-lit photo, "
                        "or type the question directly instead.",
            "matched_question_id": None,
            "citations": [], "confidence": None, "guardrail_flag": None,
        }

    conn = get_conn()
    flags = guardrails.check_input(conn, ocr_text)
    flags = [f for f in flags if f != "off_topic"]
    matched = genai.match_known_question(conn, ocr_text)

    result = genai.generate_coaching_response(
        conn, student_alias, ocr_text,
        subject=matched["subject"] if matched else None,
        chapter=matched["chapter"] if matched else None,
        concept_id=matched["concept_id"] if matched else None,
        last_question_id=matched["question_id"] if matched else None,
        reveal_full_solution=False,
        guardrail_flags=flags,
    )

    session_id = str(uuid.uuid4())[:8]
    conn.execute(
        "INSERT INTO chat_sessions (session_id, student_alias, role, message, guardrail_flag, "
        "citations, confidence, token_estimate, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (session_id, student_alias, "assistant", result["response"], result["guardrail_flag"],
         ",".join(result["citations"]), result["confidence"], result["token_estimate"],
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    log_audit(conn, student_alias, "solve_image", session_id,
              f"matched_question={matched['question_id'] if matched else 'none'}")
    conn.close()

    return {
        "ocr_text": ocr_text,
        "matched_question_id": matched["question_id"] if matched else None,
        "response": result["response"],
        "citations": result["citations"],
        "confidence": result["confidence"],
        "hint_level": result["hint_level"],
        "guardrail_flag": result["guardrail_flag"] or None,
    }

@app.get("/metrics")
def metrics():
    conn = get_conn()
    total_attempts = conn.execute("SELECT COUNT(*) c FROM attempts").fetchone()["c"]
    total_chats = conn.execute("SELECT COUNT(*) c FROM chat_sessions").fetchone()["c"]
    avg_tokens = conn.execute("SELECT AVG(token_estimate) a FROM chat_sessions").fetchone()["a"]
    guardrail_hits = conn.execute(
        "SELECT COUNT(*) c FROM chat_sessions WHERE guardrail_flag != ''"
    ).fetchone()["c"]
    conn.close()
    return {
        "total_attempts": total_attempts,
        "total_chat_sessions": total_chats,
        "avg_token_estimate": round(avg_tokens, 1) if avg_tokens else 0,
        "guardrail_triggers": guardrail_hits,
    }
