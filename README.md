# IIT Student Coach Chatbot

IEEE PCE Cognithon 2026, Case 21. A grounded JEE (PCM) study coach with a rules-based mastery engine, prerequisite-first study plans, guardrails and an audit trail.

## Stack

- Backend: FastAPI, Uvicorn, SQLite
- Frontend: plain HTML, CSS and JavaScript in `index.html`
- Retrieval: keyword-overlap retrieval over 240 curated concept notes, with clickable citations
- LLM: optional. It falls back to an offline grounded response if no key is set
- OCR: winocr (Windows built-in), with pytesseract as a fallback

## Run locally (Windows)

Open two terminals in this folder.

Terminal 1, backend:

    py -m pip install -r requirements.txt
    py -m uvicorn app.main:app --port 8001

Terminal 2, frontend:

    py -m http.server 5500

On Windows you can just double-click start.bat (it stops old servers, resets the database and starts both).

Open http://localhost:5500 for the landing page. The coach app is at http://localhost:5500/app.html?alias=STU-001

API docs: http://localhost:8001/docs

## Run locally (macOS / Linux)

    python3 -m pip install fastapi uvicorn requests pydantic python-dotenv python-multipart Pillow pytesseract
    python3 -m uvicorn app.main:app --port 8001
    python3 -m http.server 5500

## Configuration

Copy `.env.example` to `.env`. All values are optional.

| Variable | Purpose |
|---|---|
| GATEWAY_URL, TEAM_TOKEN | OpenAI-compatible gateway (`/v1/chat/completions`) |
| LLM_PROVIDER, LLM_API_KEY | `anthropic` or `openai` with your key |
| TEACHER_KEY | header `x-teacher-key` for `/audit` and `/actions/log` (default `teacher123`) |

## Endpoints

| Endpoint | Purpose |
|---|---|
| GET /health | liveness check |
| GET /concepts | browse concept notes |
| GET /questions | browse questions |
| POST /attempts | log an attempt and recalculate mastery |
| POST /coach/chat | hint, explanation or full solution, with guardrails |
| GET /study-plan/{alias} | prerequisite-first plan |
| GET /mastery/{alias} | per-chapter mastery |
| GET /error-analysis/{alias} | misconception frequency |
| POST /ocr/extract | image to editable text |
| POST /coach/solve-image | one-shot image solve |
| POST /actions/log | reviewer action (teacher key) |
| GET /audit | audit log (teacher key) |
| GET /metrics | usage metrics |
| GET /summary/{alias} | attempts and accuracy for a student |
| GET /sources/{resource_id} | the concept note behind a citation |

## Data

All data is synthetic and written for this project. Nothing is scraped or copied from real students.

- `data/concept_notes.csv`: 240 concept notes, 8 per chapter across 30 JEE chapters
- `data/questions.csv`: 300 worked questions, 10 per chapter, each with a hint, step-by-step solution and final answer
- `data/seed_attempts.csv`: about 470 attempts from 12 synthetic students with different strengths and weaknesses

To regenerate the CSVs:

    cd data
    py generate_data.py

Delete `coach.db` after regenerating so it reseeds on the next start.

## How it works

1. A student picks a problem or asks a question in the chat.
2. Guardrails check the message for prompt injection, live-exam requests, rank claims and off-topic input.
3. Retrieval finds the top concept notes by keyword overlap, scoped to the detected chapter.
4. The reply is a hint, a full solution or a grounded explanation, with citations and a confidence value.
5. Attempts update a recency-weighted mastery score per chapter, which drives the study plan and weak-spot analysis.
6. Every action is written to an audit log that only a teacher key can read.

## Limitations

- Retrieval is keyword overlap, not embeddings.
- Mastery is a transparent rules-based score, not a trained model.
- The question bank is modest (300 problems) and meant to show the pipeline, not replace a full test series.
