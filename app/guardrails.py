import re

MAX_INPUT_CHARS = 800

INJECTION_PATTERNS = [
    "ignore previous instructions", "ignore all previous", "disregard the system prompt",
    "reveal your system prompt", "reveal your instructions", "act as", "you are now",
    "bypass your rules", "pretend you have no restrictions", "jailbreak",
]

LIVE_EXAM_PATTERNS = [
    "live exam", "proctored", "this is my exam", "currently taking my exam",
    "submitting in", "graded test right now", "exam is happening now", "invigilator",
    "timed test right now", "give me just the final answer for my exam",
    "exam right now", "during my exam", "during the exam", "answers for my exam", "answers for the exam",
]

RANK_INTELLIGENCE_PATTERNS = [
    "am i smart", "am i intelligent", "what's my rank", "what is my rank",
    "compare me to", "how intelligent am i", "iq",
    "my rank", "predict my rank", "will i crack", "guarantee a rank",
]

GENERIC_ACADEMIC_TERMS = [
    "bond", "bonds", "bonding", "covalent", "ionic", "molecular", "molecule", "atom", "atomic",
    "formula", "solve", "problem", "exam",
    "iit", "jee", "revise", "revision", "mistake", "wrong", "hint", "solution",
    "question", "practice", "syllabus", "physics", "chemistry", "mathematics", "maths", "math",
    "equation", "derivation", "theorem", "reaction", "force", "energy", "velocity", "acceleration",
    "mirror", "lens", "concave", "convex", "curvature", "image", "focal", "focus",
    "refraction", "reflection", "ray", "screen", "magnification", "distance", "radius",
    "mass", "block", "incline", "inclined", "surface", "friction", "frictionless",
    "rest", "coefficient", "kinetic", "static", "tension", "pulley", "spring",
    "collision", "momentum", "rigid", "particle", "projectile", "height", "angle",
    "rough", "smooth", "horizontal", "vertical", "gravity", "weight", "normal",
    "resistor", "resistance", "electric current", "voltage", "capacitor", "circuit", "charge",
    "field", "flux", "inductor", "battery", "ohm", "ampere", "conductor",
    "mole", "concentration", "molarity", "solution", "acid", "base", "salt", "catalyst",
    "temperature", "pressure", "volume", "gas", "compound", "element", "molecule",
    "atom", "electron", "proton", "neutron", "orbital", "isotope", "ph", "titration",
    "function", "graph", "root", "coordinate", "vector", "matrix", "series", "sequence",
    "derivative", "integral", "probability", "permutation", "combination",
]

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at", "to", "for",
    "and", "or", "with", "this", "that", "it", "as", "be", "by", "from", "what", "how",
    "why", "when", "where", "who", "which", "do", "does", "did", "can", "could", "will",
    "would", "should", "i", "you", "he", "she", "they", "we", "my", "your", "me",
}

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

BASIC_PCM_TERMS = [
    "define", "definition", "meaning", "basics", "basic", "simple", "calculate",
    "compute", "convert", "conversion", "unit", "si unit", "average", "percentage",
    "fraction", "decimal", "ratio", "simplify", "number", "prime number", "factor",
    "square", "cube", "table", "sum", "difference", "product", "quotient",
    "multiply", "divide", "add", "subtract", "expand", "factorize",
]

MATH_EXPRESSION_PATTERN = re.compile(r"\d+\s*[\+\-\*/\^%]\s*\d+|\d+\s*(percent|%)\s*of\s*\d+")

SMALLTALK_PATTERN = re.compile(r"^\s*(hi|hii|hello|hey|thanks|thank you|thx|ok|okay|bye|good morning|good evening|good night)\b[\s\w!.,?]{0,20}$", re.I)

def _word_pattern(terms):
    escaped = sorted((re.escape(t) for t in terms), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(escaped) + r")(?:s|es)?\b")

_ACADEMIC_RE = _word_pattern(KNOWN_CHAPTERS + GENERIC_ACADEMIC_TERMS + BASIC_PCM_TERMS)

def is_smalltalk(message: str) -> bool:
    return bool(SMALLTALK_PATTERN.match(message))

def is_on_topic(conn, message: str) -> bool:
    lower = message.lower()
    if _ACADEMIC_RE.search(lower):
        return True
    if MATH_EXPRESSION_PATTERN.search(lower):
        return True
    from .genai import detect_chapter_from_message
    if detect_chapter_from_message(message):
        return True

    query_terms = set(re.findall(r"\w+", lower)) - STOPWORDS
    if len(query_terms) < 2:
        return False
    rows = conn.execute("SELECT resource_text FROM concept_notes").fetchall()
    for r in rows:
        text_terms = set(re.findall(r"\w+", r["resource_text"].lower())) - STOPWORDS
        if len(query_terms & text_terms) >= 3:
            return True
    return False

def check_input(conn, message: str):
    flags = []
    if len(message) > MAX_INPUT_CHARS:
        flags.append("input_too_long")
    lower = message.lower()
    if any(p in lower for p in INJECTION_PATTERNS):
        flags.append("prompt_injection_suspected")
    if any(p in lower for p in LIVE_EXAM_PATTERNS):
        flags.append("live_exam_request")
    if any(p in lower for p in RANK_INTELLIGENCE_PATTERNS):
        flags.append("rank_or_intelligence_claim_request")
    if not flags and not is_smalltalk(message) and not is_on_topic(conn, message):
        flags.append("off_topic")
    return flags

def refusal_message(flags):
    if "live_exam_request" in flags:
        return (
            "I can't help with live or proctored exam questions - that would cross into "
            "exam integrity. I'm happy to walk you through the underlying concept instead, "
            "so you understand it for next time."
        )
    if "prompt_injection_suspected" in flags:
        return (
            "I can't change my role or ignore my guidelines, even if asked directly. "
            "I'm still here to help you study - what concept or question would you like to work on?"
        )
    if "rank_or_intelligence_claim_request" in flags:
        return (
            "I don't rank students or make claims about intelligence - everyone learns at their "
            "own pace. I can tell you which topics need more practice based on your attempts, though!"
        )
    if "off_topic" in flags:
        return (
            "I'm built specifically to help with JEE Physics, Chemistry, and Maths preparation - "
            "that question is outside what I can help with here. Ask me about a concept, a question "
            "you're stuck on, or your revision plan instead!"
        )
    if "input_too_long" in flags:
        return "Could you shorten your question a bit? A focused question gets you a better answer."
    return "I'm not able to help with that request, but I'm glad to help you study the concept instead."

def check_output(text: str, has_citation: bool):
    flags = []
    if not has_citation:
        flags.append("missing_citation")
    if len(text) > 1200:
        flags.append("answer_too_long")
    return flags
