import os
import re
import io
import requests

TOP_K = 3
_CACHE = {}

KNOWN_CHAPTERS = [
    "kinematics", "laws of motion", "work energy power", "rotational motion", "gravitation",
    "thermodynamics", "electrostatics", "current electricity", "magnetism", "optics",
    "mole concept", "chemical equilibrium", "chemical kinetics", "electrochemistry",
    "chemical bonding", "periodic properties", "coordination compounds", "hydrocarbons",
    "general organic chemistry", "aldehydes and ketones",
    "quadratic equations", "sequences and series", "permutations and combinations",
    "probability", "straight lines", "circles", "trigonometric equations",
    "limits and derivatives", "integration", "vectors",
]

EXTRA_SYNONYMS = {
    "Kinematics": ["uniform acceleration", "relative velocity", "distance travelled", "v-t graph", "velocity-time"],
    "Laws of Motion": ["impulse", "momentum", "centripetal", "pseudo force", "angle of repose", "apparent weight"],
    "Work Energy Power": ["restitution", "collision", "spring energy", "elastic collision", "efficiency"],
    "Rotational Motion": ["rolling", "centre of mass", "center of mass", "angular acceleration", "rotational", "parallel axis"],
    "Gravitation": ["escape velocity", "satellite", "geostationary", "acceleration due to gravity", "gravitational"],
    "Thermodynamics": ["ideal gas", "latent heat", "carnot", "specific heat", "calorimetry", "cyclic process", "pv diagram"],
    "Electrostatics": ["dipole", "dielectric", "capacitance"],
    "Current Electricity": ["wheatstone", "drift velocity", "kirchhoff", "internal resistance", "resistance", "resistivity"],
    "Magnetism": ["biot savart", "ampere", "lenz", "faraday", "induction", "inductance", "lorentz", "magnetic"],
    "Optics": ["total internal reflection", "critical angle", "prism", "young", "double slit", "interference", "refractive index", "diffraction", "apparent depth"],
    "Mole Concept": ["limiting reagent", "molarity", "dilution", "percentage composition", "percentage yield", "stp"],
    "Chemical Equilibrium": ["buffer", "henderson", "ksp", "solubility product", "degree of dissociation", "reaction quotient"],
    "Chemical Kinetics": ["zero order", "first order", "second order", "activation energy", "arrhenius", "rate determining", "molecularity", "catalyst"],
    "Electrochemistry": ["kohlrausch", "molar conductivity", "conductivity", "faraday", "cell potential", "electrochemical"],
    "Chemical Bonding": ["hydrogen bonding", "hydrogen bond", "formal charge", "bond angle", "paramagnetic", "diamagnetic", "dipole moment"],
    "Periodic Properties": ["electron gain", "diagonal relationship", "metallic character", "periodic trend", "oxidation state"],
    "Coordination Compounds": ["chelate", "magnetic moment", "crystal field", "edta", "spin only", "ligand field"],
    "Hydrocarbons": ["ozonolysis", "hydrogenation", "huckel", "nitration", "friedel crafts", "combustion", "peroxide", "anti markovnikov"],
    "General Organic Chemistry": ["sn1", "sn2", "nucleophile", "electrophile", "enantiomer", "meso", "optical isomerism", "mesomeric", "carbocation stability"],
    "Aldehydes and Ketones": ["iodoform", "clemmensen", "wolff kishner", "nucleophilic addition", "silver mirror"],
    "Quadratic Equations": ["biquadratic", "cube roots of unity", "nature of roots", "complex roots"],
    "Sequences and Series": ["infinite gp", "telescoping", "arithmetic mean", "geometric mean", "am gm", "common difference"],
    "Permutations and Combinations": ["circular arrangement", "circular arrangements", "round table", "necklace", "ncr", "npr", "arrangements", "selections"],
    "Probability": ["binomial", "expected value", "conditional probability", "independent events", "mutually exclusive", "bayes theorem"],
    "Straight Lines": ["collinear", "parallel lines", "perpendicular lines", "angle between two lines", "area of a triangle", "section formula"],
    "Circles": ["tangent length", "length of the tangent", "external point"],
    "Trigonometric Equations": ["compound angle", "double angle", "sum to product", "general solution", "trigonometry"],
    "Limits and Derivatives": ["l'hopital", "lhopital", "continuity", "continuous", "maxima", "minima", "chain rule", "related rates", "tangent to the curve"],
    "Integration": ["partial fractions", "definite integral", "area under", "ilate"],
    "Vectors": ["triple product", "scalar triple product", "unit vector", "parallelepiped", "position vector", "coplanar"],
}

def detect_chapter_from_message(message: str):
    lower = message.lower()
    for chapter in KNOWN_CHAPTERS:
        if chapter in lower:
            return chapter.title() if chapter != "work energy power" else "Work Energy Power"

    SYNONYMS = {
        "Optics": ["mirror", "lens", "concave", "convex", "curvature", "refraction", "reflection", "image"],
        "Current Electricity": ["resistor", "circuit", "ohm", "ampere", "voltage"],
        "Magnetism": ["magnetic field", "solenoid", "compass"],
        "Chemical Bonding": ["covalent", "ionic bond", "lewis structure", "vsepr", "atom", "molecule", "element", "compound", "bond", "bonds", "bonding", "hybridisation", "hybridization", "bond order", "dipole", "polarity", "molecular orbital"],
        "Laws of Motion": ["newton", "newtons", "newton's", "inertia", "block", "incline", "inclined", "friction", "kinetic friction",
                           "tension", "pulley", "rough surface", "normal force", "coefficient of friction"],
        "Quadratic Equations": ["quadratic", "discriminant", "roots", "root", "x^2", "ax^2", "x squared", "sum of roots", "product of roots"],
        "Kinematics": ["velocity", "acceleration", "projectile", "displacement", "free fall"],
        "Thermodynamics": ["entropy", "enthalpy", "heat engine", "isothermal", "adiabatic", "first law"],
        "Electrostatics": ["coulomb", "electric field", "capacitor", "gauss", "electric potential"],
        "Gravitation": ["gravity", "orbital", "escape velocity", "kepler"],
        "Mole Concept": ["mole", "molar mass", "avogadro", "stoichiometry"],
        "Chemical Equilibrium": ["equilibrium", "le chatelier", "kc", "kp"],
        "Chemical Kinetics": ["rate constant", "rate law", "half life", "order of reaction"],
        "Electrochemistry": ["galvanic", "electrolysis", "nernst", "emf", "electrode"],
        "Hydrocarbons": ["alkane", "alkene", "alkyne", "benzene", "markovnikov", "aromatic"],
        "General Organic Chemistry": ["isomer", "isomers", "isomerism", "chiral", "stereoisomer", "carbocation", "inductive", "resonance", "hyperconjugation"],
        "Aldehydes and Ketones": ["aldehyde", "ketone", "aldol", "cannizzaro", "tollens", "carbonyl", "fehling"],
        "Periodic Properties": ["ionisation", "ionization", "electronegativity", "atomic radius", "periodic table", "isoelectronic"],
        "Coordination Compounds": ["ligand", "ligands", "complex", "coordination number", "crystal field"],
        "Probability": ["probability", "bayes", "dice", "coin toss"],
        "Permutations and Combinations": ["permutation", "combination", "factorial", "arrange"],
        "Limits and Derivatives": ["derivative", "differentiation", "limits", "limit of", "limit as", "differentiate"],
        "Integration": ["integral", "integrals", "integrate", "integrating", "antiderivative", "by parts"],
        "Sequences and Series": ["arithmetic progression", "geometric progression", "sequence", "series"],
        "Circles": ["circle", "tangent to", "radius"],
        "Straight Lines": ["slope", "straight line", "intercept"],
        "Vectors": ["vector", "dot product", "cross product"],
        "Trigonometric Equations": ["sin", "cos", "tan", "trigonometric"],
        "Rotational Motion": ["torque", "moment of inertia", "angular momentum", "angular velocity"],
        "Work Energy Power": ["work done", "kinetic energy", "potential energy", "work-energy theorem"],
    }
    for chapter, extra in EXTRA_SYNONYMS.items():
        SYNONYMS[chapter] = SYNONYMS.get(chapter, []) + extra
    best, best_len = None, 0
    for chapter, words in SYNONYMS.items():
        for w in words:
            if len(w) > best_len and re.search(r"\b" + re.escape(w) + r"\b", lower):
                best, best_len = chapter, len(w)
    return best

def retrieve_top_chunks(conn, subject=None, chapter=None, concept_id=None, query="", k=TOP_K):
    sql = "SELECT concept_id, resource_id, chapter, resource_text, common_misconception FROM concept_notes WHERE 1=1"
    params = []
    if concept_id:
        sql += " AND concept_id=?"
        params.append(concept_id)
    if subject:
        sql += " AND subject=?"
        params.append(subject)
    if chapter:
        sql += " AND chapter=?"
        params.append(chapter)
    rows = conn.execute(sql, params).fetchall()

    from .guardrails import STOPWORDS
    query_terms = set(re.findall(r"\w+", query.lower())) - STOPWORDS
    scored = []
    for r in rows:
        text_terms = set(re.findall(r"\w+", r["resource_text"].lower())) - STOPWORDS
        overlap = len(query_terms & text_terms)
        scored.append((overlap, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]] if scored else rows[:k]

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

async def extract_text_from_image(image_bytes: bytes) -> str:
    from PIL import Image, ImageOps, ImageEnhance

    def preprocess(img: "Image.Image") -> "Image.Image":
        img = img.convert("L")
        img = ImageOps.autocontrast(img)
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        if img.width < 1200:
            scale = 1200 / img.width
            img = img.resize((1200, int(img.height * scale)))
        return img

    try:
        import winocr
        img = preprocess(Image.open(io.BytesIO(image_bytes)))
        result = await winocr.recognize_pil(img, "en-US")
        text = (result.text or "").strip()
        if text:
            return text
    except Exception as e:
        print(f"[OCR] winocr unavailable/failed: {type(e).__name__}: {e}")

    try:
        import pytesseract

        if os.name == "nt":
            for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                      r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break

        img = preprocess(Image.open(io.BytesIO(image_bytes)))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"[OCR ERROR] Tesseract also failed: {type(e).__name__}: {e}")
        return ""

def match_known_question(conn, ocr_text: str):
    query_terms = set(re.findall(r"\w+", ocr_text.lower()))
    if len(query_terms) < 3:
        return None
    rows = conn.execute("SELECT * FROM questions").fetchall()
    best, best_score = None, 0
    for r in rows:
        text_terms = set(re.findall(r"\w+", r["question_text"].lower()))
        score = len(query_terms & text_terms)
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= 3 else None


def call_llm(system_prompt: str, user_prompt: str) -> str:
    gateway_url = os.environ.get("GATEWAY_URL", "")
    team_token = os.environ.get("TEAM_TOKEN", "")

    if gateway_url and team_token:
        try:
            resp = requests.post(
                f"{gateway_url}/v1/chat/completions",
                headers={"Authorization": f"Bearer {team_token}", "Content-Type": "application/json"},
                json={
                    "model": "anything",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_completion_tokens": 300,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass

    provider = os.environ.get("LLM_PROVIDER", "").lower()
    api_key = os.environ.get("LLM_API_KEY", "")

    if provider == "anthropic" and api_key:
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": 300,
                      "system": system_prompt,
                      "messages": [{"role": "user", "content": user_prompt}]},
                timeout=15,
            )
            data = resp.json()
            return "".join(b.get("text", "") for b in data.get("content", []))
        except Exception:
            pass

    if provider == "openai" and api_key:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "max_tokens": 300,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": user_prompt}]},
                timeout=15,
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            pass

    return None

import re as _re_arith

def try_basic_arithmetic(message: str):
    if len(message.strip()) > 40:
        return None

    lower = message.lower().strip().rstrip("?")

    percent_match = _re_arith.search(r"(?<![a-zA-Z])(\d+(?:\.\d+)?)\s*(?:percent|%)\s*of\s*(\d+(?:\.\d+)?)(?![a-zA-Z])", lower)
    if percent_match:
        pct, base = float(percent_match.group(1)), float(percent_match.group(2))
        result = pct / 100 * base
        return {
            "response": f"{pct:g}% of {base:g} = {result:g}",
            "citations": [], "confidence": 1.0, "hint_level": "basic_calculation",
            "token_estimate": 10, "guardrail_flag": "",
        }

    expr_match = _re_arith.search(
        r"(?<![a-zA-Z])(-?\d+(?:\.\d+)?)\s*([\+\-\*/])\s*(-?\d+(?:\.\d+)?)(?![a-zA-Z])", lower)
    if expr_match:
        a, op, b = float(expr_match.group(1)), expr_match.group(2), float(expr_match.group(3))
        try:
            if op == "+": result = a + b
            elif op == "-": result = a - b
            elif op == "*": result = a * b
            elif op == "/":
                if b == 0:
                    return {
                        "response": "Division by zero is undefined - there's no valid answer to that expression.",
                        "citations": [], "confidence": 1.0, "hint_level": "basic_calculation",
                        "token_estimate": 10, "guardrail_flag": "",
                    }
                result = a / b
            fmt = lambda x: f"{x:g}"
            return {
                "response": f"{fmt(a)} {op} {fmt(b)} = {fmt(result)}",
                "citations": [], "confidence": 1.0, "hint_level": "basic_calculation",
                "token_estimate": 10, "guardrail_flag": "",
            }
        except Exception:
            return None
    return None

def generate_coaching_response(conn, student_alias, message, subject, chapter, concept_id,
                                last_question_id, reveal_full_solution, guardrail_flags):
    if guardrail_flags:
        from .guardrails import refusal_message
        return {
            "response": refusal_message(guardrail_flags),
            "citations": [],
            "confidence": None,
            "hint_level": None,
            "token_estimate": estimate_tokens(message),
            "guardrail_flag": ",".join(guardrail_flags),
        }

    from .guardrails import is_smalltalk
    if not last_question_id and is_smalltalk(message):
        return {
            "response": "Hi! I'm Pravesh. Pick a problem on the left for a hint, or ask me about any JEE Physics, Chemistry or Maths concept.",
            "citations": [], "confidence": None, "hint_level": "smalltalk",
            "token_estimate": 20, "guardrail_flag": "",
        }

    if not last_question_id:
        id_match = re.search(r"\bq-\d{5}\b", message.lower())
        if id_match:
            found = conn.execute("SELECT question_id FROM questions WHERE question_id=?", (id_match.group(0).upper(),)).fetchone()
            if found:
                last_question_id = found["question_id"]

    if not last_question_id:
        arithmetic_result = try_basic_arithmetic(message)
        if arithmetic_result:
            return arithmetic_result

    question_row = None
    if last_question_id:
        question_row = conn.execute(
            "SELECT * FROM questions WHERE question_id=?", (last_question_id,)
        ).fetchone()
        if question_row:
            concept_id = concept_id or question_row["concept_id"]
            subject = subject or question_row["subject"]
            chapter = chapter or question_row["chapter"]

    if not chapter and not concept_id:
        chapter = detect_chapter_from_message(message) or chapter

    chunks = retrieve_top_chunks(conn, subject=subject, chapter=chapter,
                                  concept_id=concept_id, query=message)
    citations = [c["resource_id"] for c in chunks]
    misconception = chunks[0]["common_misconception"] if chunks else None

    if question_row and not reveal_full_solution:
        hint_level = "hint"
        cache_key = (question_row["question_id"], tuple(sorted(citations)), "hint")
        if cache_key in _CACHE:
            text = _CACHE[cache_key]
        else:
            grounded_context = " | ".join(c["resource_text"] for c in chunks)
            system_prompt = (
                "You are a supportive IIT-entrance coaching assistant. Give a short hint (2-3 sentences) "
                "tied to the student's likely misconception. Do NOT give the final numeric/full solution. "
                "Be encouraging, age-appropriate, and cite the concept note. Never claim to know the "
                "student's rank or intelligence."
            )
            user_prompt = (
                f"Problem: {question_row['question_text']}\nTeacher hint: {question_row['hint']}\n"
                f"Likely misconception: {misconception}\nGrounded context: {grounded_context}\n"
                f"Give a hint only, not the answer."
            )
            llm_text = call_llm(system_prompt, user_prompt)
            text = llm_text or (
                f"Hint: {question_row['hint']}\n\n"
                f"Watch out for: {question_row['error_type_if_wrong']}. "
                f"Re-check that step before redoing the problem."
            )
            _CACHE[cache_key] = text
    elif question_row and reveal_full_solution:
        hint_level = "full_solution"
        steps = question_row["solution_steps"].replace(" Step ", "\nStep ")
        text = f"{steps}\n\nFinal answer: {question_row['final_answer']}"
    else:
        hint_level = "explanation"
        norm_message = " ".join(sorted(re.findall(r"\w+", message.lower())))
        cache_key = (concept_id, chapter, subject, tuple(sorted(citations)), norm_message, "explanation")
        if cache_key in _CACHE:
            text = _CACHE[cache_key]
        else:
            grounded_context = " | ".join(c["resource_text"] for c in chunks)
            system_prompt = (
                "You are a supportive IIT-entrance coaching assistant. Explain the concept clearly "
                "in under 120 words, cite the concept note, and note your confidence honestly."
            )
            user_prompt = f"Student question: {message}\nGrounded context: {grounded_context}"
            llm_text = call_llm(system_prompt, user_prompt)
            if llm_text:
                text = llm_text
            elif chunks:
                heading = chunks[0]["chapter"]
                bullets = "\n".join(
                    "- " + c["resource_text"].split(": ", 1)[-1] for c in chunks
                )
                text = f"Here is what the notes say on {heading}:\n{bullets}"
            else:
                text = "I could not find a matching concept note for that."
            _CACHE[cache_key] = text

    confidence = (0.9 if question_row else 0.8) if chunks else 0.4
    if not chunks:
        text += " I don't have a matching concept note for this - treat this as a general pointer, not a cited fact."

    return {
        "response": text,
        "citations": citations,
        "confidence": confidence,
        "hint_level": hint_level,
        "token_estimate": estimate_tokens(message + text),
        "guardrail_flag": "",
    }
