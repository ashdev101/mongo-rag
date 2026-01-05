import re
import spacy

# ------------------ Load spaCy model ------------------
# For stable semantic similarity, use 'en_core_web_md' instead of 'sm'
nlp = spacy.load("en_core_web_sm")

# ------------------ PRONOUNS ------------------
SELF_PRONOUNS = {"i", "me", "my", "mine", "myself"}

# ------------------ REGEX ------------------
SELF_PATTERNS = re.compile(r"\b(i|me|my|mine|myself)\b", re.I)
OTHER_PATTERNS = re.compile(
    r"\b(he|she|they|them|his|her|their|someone|somebody|another\s+employee)\b",
    re.I
)

# ------------------ COLLECTIVE NOUNS ------------------
COLLECTIVE_NOUNS = {
    "department", "team", "organization", "company", "group",
    "people", "employees", "members", "reports", "subordinates",
    "staff", "headcount"
}

# ------------------ REPORTING / MANAGERIAL ------------------
REPORTING_PATTERNS = re.compile(
    r"\b(reports?\s+to\s+me|reporting\s+to\s+me|direct\s+reports?)\b",
    re.I
)

# ------------------ GENERIC QUERIES ------------------
GENERIC_PATTERNS = re.compile(
    r"\b(performance status|employee details|appraisal information|goal status)\b",
    re.I
)

# ------------------ SEMANTIC EXAMPLES ------------------
SELF_SEMANTIC = [
    "my date of birth",
    "my personal information",
    "my performance rating",
    "my appraisal score",
    "my performance status",
    "my goal status",
    "who is my performance reviewer",
    "what is my appraisal rating",
    "show my own performance details",
    "my manager's name",
    "my manager's email address",
    "my manager's phone number",
    "information about myself",
    "details about me",
]


OTHER_SEMANTIC = [
    "people in my department",
    "members of my team",
    "employees reporting to me",
    "who are my direct reports",
    "list of my team members",
    "team size",
    "department headcount",
    "how many people are in my team",
    "show employees in my organization",
    "headcount in my department",
    "who reports to me",
    "staff under my supervision",
    "members of my organization",
]


# ------------------ CLASSIFIER ------------------
class SelfOtherClassifier:
    def __init__(self):
        self.self_docs = [nlp(s) for s in SELF_SEMANTIC]
        self.other_docs = [nlp(s) for s in OTHER_SEMANTIC]

    # ---------- 1. RULE BASED ----------
    def rule_based(self, text):
        text_lower = text.lower()

        # Explicit generic queries
        if GENERIC_PATTERNS.search(text_lower):
            return "generic"

        # Reporting / managerial queries → OTHER
        if REPORTING_PATTERNS.search(text_lower):
            return "other"

        # my + collective noun → OTHER
        for noun in COLLECTIVE_NOUNS:
            if re.search(rf"\bmy\s+{noun}\b", text_lower):
                return "other"

        # Explicit other pronouns
        if OTHER_PATTERNS.search(text):
            return "other"

        # Explicit self pronouns
        if SELF_PATTERNS.search(text):
            return "self"

        return None

    # ---------- 2. DEPENDENCY PARSING ----------
    def dependency_based(self, doc):
        for token in doc:
            # Subject pronouns
            if token.dep_ in {"nsubj", "nsubjpass"}:
                if token.text.lower() in SELF_PRONOUNS:
                    return "self"
                if token.text.lower() in OTHER_PATTERNS.pattern or token.ent_type_ == "PERSON":
                    return "other"

            # Object-based collective nouns
            if token.text.lower() in COLLECTIVE_NOUNS:
                return "other"

        return None

    # ---------- 3. SEMANTIC FALLBACK ----------
    def semantic_based(self, doc):
        self_score = max(doc.similarity(d) for d in self.self_docs)
        other_score = max(doc.similarity(d) for d in self.other_docs)

        if max(self_score, other_score) < 0.55:
            return "other"  # default safest guess

        return "self" if self_score > other_score else "other"

    # ---------- MAIN ----------
    def classify(self, text):
        text = text.strip()
        doc = nlp(text)

        # Step 1: Rules
        result = self.rule_based(text)
        if result:
            return result

        # Step 2: Syntax
        result = self.dependency_based(doc)
        if result:
            return result

        # Step 3: Semantic fallback
        return self.semantic_based(doc)

# ------------------ TESTING ------------------
if __name__ == "__main__":
    classifier = SelfOtherClassifier()

    tests = [
        # SELF
        "what is my performance rating",
        "show my appraisal score",
        "what is my date of birth",
        "who is my performance reviewer",
        "give me my personal information",
        "details about myself",
        "my goal status",
        "my manager's email address",

        # OTHER
        "how many people are there in my department",
        "list employees in my team",
        "show members of my organization",
        "what is the headcount of my department",
        "who are my direct reports",
        "list staff reporting to me",
        "number of people in my group",
        "who reports to me",
        "people reporting to me",
        "give me someone's date of birth",
        "details about another employee",

        # GENERIC
        "performance status",
        "employee details",
        "appraisal information",
        "goal status",
    ]

    for text in tests:
        print(f"{text:<50} → {classifier.classify(text)}")