import re
import spacy

nlp = spacy.load("en_core_web_sm")

SELF_PRONOUNS = {"i", "me", "my", "mine", "myself"}
OTHER_PRONOUNS = {"he", "she", "they", "them", "his", "her", "their"}

SELF_PATTERNS = re.compile(r"\b(i|me|my|mine|myself)\b", re.I)
OTHER_PATTERNS = re.compile(r"\b(he|she|they|them|his|her|their|someone|somebody)\b", re.I)

SELF_SEMANTIC = [
    "my goal status",
    "my date of birth",
    "my performance rating",
    "my performance status",
    "my performance reviewer",
    "my appraisal score",
    "my manager's email address",
    "my manager's phone number",
    "my manager's name",
    "my manager's code",
    "my manager's ID",
    "my manager's address",
]

OTHER_SEMANTIC = [
    "your goal status",
    "your date of birth",
    "your performance rating",
    "your performance status",
    "your performance reviewer",
    "your appraisal score",
    "your manager's email address",
    "your manager's phone number",
    "your manager's name",
    "your manager's code",
    "your manager's ID",
    "your manager's address",
]


class SelfOtherClassifier:
    def __init__(self):
        self.self_docs = [nlp(s) for s in SELF_SEMANTIC]
        self.other_docs = [nlp(s) for s in OTHER_SEMANTIC]

    # ---------- 1. RULE BASED ----------
    def rule_based(self, text):
        if SELF_PATTERNS.search(text):
            return "self"
        if OTHER_PATTERNS.search(text):
            return "other"
        return None

    # ---------- 2. DEPENDENCY PARSING ----------
    def dependency_based(self, doc):
        for token in doc:
            if token.dep_ in {"nsubj", "nsubjpass"}:
                if token.text.lower() in SELF_PRONOUNS:
                    return "self"
                if token.text.lower() in OTHER_PRONOUNS or token.ent_type_ == "PERSON":
                    return "other"
        return None

    # ---------- 3. SEMANTIC FALLBACK ----------
    def semantic_based(self, doc):
        self_score = max(doc.similarity(d) for d in self.self_docs)
        other_score = max(doc.similarity(d) for d in self.other_docs)

        if max(self_score, other_score) < 0.55:
            return "generic"

        return "self" if self_score > other_score else "other"

    # ---------- MAIN ----------
    def classify(self, text):
        text = text.strip()
        doc = nlp(text)

        # Step 1: rules
        result = self.rule_based(text)
        if result:
            return result

        # Step 2: syntax
        result = self.dependency_based(doc)
        if result:
            return result

        # Step 3: semantics
        return self.semantic_based(doc)
    


if __name__ == "__main__":
    classifier = SelfOtherClassifier()
    text = "my managers email address"
    result = classifier.classify(text)
    print(f"Classification result: {result}")
