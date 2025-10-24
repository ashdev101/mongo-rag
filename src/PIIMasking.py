from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import uuid
import re

from presidio_analyzer import AnalyzerEngine
import re

class PIIMasker:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.mapping = {}

    def mask(self, text):
        results = self.analyzer.analyze(text=text, entities=None, language='en')

        # Sort in reverse order so replacements don't shift the indexes
        results = sorted(results, key=lambda x: x.start, reverse=True)

        masked_text = text
        self.mapping = {}
        counter = {}

        for res in results:
            entity = res.entity_type
            original = text[res.start:res.end]

            # Avoid overlapping replacements
            if any(tag in original for tag in ['<', '>']):
                continue

            # Create a unique placeholder
            idx = counter.get(entity, 0)
            placeholder = f"<{entity}_{idx}>"
            counter[entity] = idx + 1

            # Save mapping
            self.mapping[placeholder] = original

            # Replace in string
            masked_text = masked_text[:res.start] + placeholder + masked_text[res.end:]

        return masked_text

    def unmask(self, text):
        # Replace placeholders with original values
        for placeholder, original in self.mapping.items():
            text = text.replace(placeholder, original)
        return text



masker = PIIMasker()
text = "My name is John Doe and my email is 1w2M1@example.com"
masked = masker.mask(text)
print("Masked:", masked)
unmasked = masker.unmask(masked)
print("Unmasked:", unmasked)