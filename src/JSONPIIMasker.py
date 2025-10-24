import re
import copy
from typing import Tuple, Dict, Any
import spacy

class JSONPIIMasker:
    def __init__(self):
        # Load SpaCy large English model
        self.nlp = spacy.load("en_core_web_lg")
        
        # Regex patterns for things spaCy might miss or can't detect easily
        self.patterns = {
            "EMAIL": re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b"),
            "PHONE": re.compile(r"\b(?:\+?1[-.\s]?)*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
            "ZIP": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
        }
        
        # Entity labels from spaCy to mask
        self.spacy_labels = {
            "PERSON": "PERSON",
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "ORG": "ORG",
            "DATE": "DATE",
            "ADDRESS": "LOCATION",  # spaCy doesn’t have ADDRESS entity by default, but let's keep for clarity
        }
        
        self.mapping = {}
        self.counter = {}

    def mask(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        print("Masking data...")
        print("Original Data:", data)
        self.mapping = {}
        self.counter = {}
        masked_data = self._mask_recursive(copy.deepcopy(data))
        print("Masked Data:", masked_data)
        print(masked_data)
        return masked_data, self.mapping

    def unmask(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._unmask_recursive(copy.deepcopy(data))

    def _mask_recursive(self, obj):
        if isinstance(obj, dict):
            return {k: self._mask_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._mask_recursive(item) for item in obj]
        elif isinstance(obj, str):
            # First mask spaCy entities
            masked_text = self._mask_spacy_entities(obj)
            # Then mask regex patterns
            masked_text = self._mask_regex_patterns(masked_text)
            return masked_text
        else:
            return obj

    def _unmask_recursive(self, obj):
        if isinstance(obj, dict):
            return {k: self._unmask_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._unmask_recursive(item) for item in obj]
        elif isinstance(obj, str):
            for token, original in self.mapping.items():
                obj = obj.replace(token, original)
            return obj
        else:
            return obj

    def _mask_spacy_entities(self, text: str) -> str:
        doc = self.nlp(text)
        spans = []

        # Collect spans of entities to mask
        for ent in doc.ents:
            label = self.spacy_labels.get(ent.label_)
            if label:
                spans.append((ent.start_char, ent.end_char, label, ent.text))

        # Sort spans descending by start_char to avoid messing offsets when replacing
        spans = sorted(spans, key=lambda x: x[0], reverse=True)

        for start, end, label, original_text in spans:
            mask_token = self._get_mask_token(label)
            self.mapping[mask_token] = original_text
            text = text[:start] + mask_token + text[end:]

        return text

    def _mask_regex_patterns(self, text: str) -> str:
        for label, pattern in self.patterns.items():
            matches = list(pattern.finditer(text))
            for match in reversed(matches):  # reverse for safe replacement
                value = match.group()
                mask_token = self._get_mask_token(label)
                self.mapping[mask_token] = value
                start, end = match.start(), match.end()
                text = text[:start] + mask_token + text[end:]
        return text

    def _get_mask_token(self, label: str) -> str:
        count = self.counter.get(label, 0)
        token = f"<{label}_{count}>"
        self.counter[label] = count + 1
        return token
    
    def mask_text(self, text: str) -> tuple[str, dict[str, str]]:
        """Mask PII entities in a plain text string."""
        self.mapping = {}
        self.counter = {}

        # Mask spaCy entities
        masked_text = self._mask_spacy_entities(text)
        # Mask regex patterns on the updated text
        masked_text = self._mask_regex_patterns(masked_text)

        return masked_text, self.mapping
    
    

# masker = JSONPIIMasker()

# json_data = [{'_id': {'$oid': '68da2d65e5c7f3045f13c327'}, 'firstName': 'Ronit', 'lastName': 'Roushan', 'profilePic': 'https://lh3.googleusercontent.com/a/ACg8ocKe-nvqu7kqkMk-LaeqkNypBgXcoexK1PBwBWTcHAmIqZc4OFBn=s96-c', 'email': 'ronit21102@gmail.com'}, {'_id': {'$oid': '68d1290ab59d0aeb4a2fac4a'}, 'firstName': 'Sakshi', 'lastName': 'Lade', 'profilePic': 'https://firebasestorage.googleapis.com/v0/b/savishi-d307a.appspot.com/o/Profile%20Pics%2FGrandson%20-%20free%20icon.jpeg?alt=media&token=9fba3068-2f62-460e-9c09-e6b4deb319be', 'email': 'sakshilade09@gmail.com'}, {'_id': {'$oid': '68cb9e44b59d0aeb4a2faaa4'}, 'firstName': 'Vaibhav', 'lastName': 'Mate', 'profilePic': 'https://lh3.googleusercontent.com/a/ACg8ocIVfHRkqRCvJkjTsbLTZjZb11COl1fJNQcyskrjfi2zfvXQcmOf=s96-c', 'email': 'vaibhav.mate88@gmail.com'}, {'_id': {'$oid': '68ca99be65953cc43cb67ef9'}, 'firstName': 'Akash', 'lastName': 'Puranik', 'profilePic': 'https://firebasestorage.googleapis.com/v0/b/savishi-d307a.appspot.com/o/Profile%20Pics%2FProfile%20Special%20Flat%20icon.png?alt=media&token=20c50912-1854-4ee4-9d55-8da98f40b35b', 'email': 'akash.puranik@kreedalabs.com'}, {'_id': {'$oid': '68ca6c2c65953cc43cb67e40'}, 'firstName': 'Kumaresh', 'lastName': 'Bhuyan', 'profilePic': 'https://lh3.googleusercontent.com/a/ACg8ocIuM9h3eVRgJUeVifnrtmy1KE3f0suq9MJNgdm46HlSqu7DfQ296w=s96-c', 'email': 'kumareshbhuyan301@gmail.com'}]


# masked_json, mapping = masker.mask(json_data)
# print("🔒 Masked JSON:\n", masked_json)
# print("\n🗺️ Mapping:\n", mapping)

# unmasked_json = masker.unmask(masked_json)
# print("\n🔓 Unmasked JSON:\n", unmasked_json)