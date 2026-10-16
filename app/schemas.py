from pydantic import BaseModel
from typing import Optional, List

class AttemptIn(BaseModel):
    student_alias: str
    question_id: str
    attempt_status: str
    time_spent_sec: int = 60

class ChatIn(BaseModel):
    student_alias: str
    message: str
    concept_id: Optional[str] = None
    chapter: Optional[str] = None
    subject: Optional[str] = None
    last_question_id: Optional[str] = None
    reveal_full_solution: bool = False

class ActionIn(BaseModel):
    actor_alias: str
    actor_role: str = "student"
    action: str
    target: str
    details: Optional[str] = ""
