import json
import re
from typing import Any


import json
import re
from typing import Any


class BedrockResolverOutputParser:
    """
    Parser for conversation resolver outputs.

    Valid outputs:
    1. JSON: { "query": "<text>" }
    2. Plain string: "<text>"

    Everything else is rejected.
    """

    @staticmethod
    def parse(response: Any) -> dict | str:
        text = BedrockResolverOutputParser._extract_text(response)

        # 1. Try JSON first
        try:
            return BedrockResolverOutputParser._extract_first_json(text)
        except ValueError:
            pass

        # 2. Fallback: treat as resolved string
        text = text.strip()

        if not text:
            raise ValueError("Empty response from LLM")

        return text

    @staticmethod
    def _extract_text(response: Any) -> str:
        content = getattr(response, "content", response)

        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict)
                else getattr(block, "text", "")
                for block in content
            )

        if not isinstance(content, str):
            raise TypeError(f"Unsupported response content type: {type(content)}")

        return content.lstrip("\ufeff").strip()

    @staticmethod
    def _extract_first_json(text: str) -> dict:
        # Fast path
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Remove markdown fences
        text = re.sub(r"```(?:json)?", "", text)

        # Brace matching
        stack = []
        start = None

        for i, ch in enumerate(text):
            if ch == "{":
                if not stack:
                    start = i
                stack.append(ch)
            elif ch == "}":
                if stack:
                    stack.pop()
                    if not stack and start is not None:
                        candidate = text[start : i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            pass

        raise ValueError("No valid JSON object found")



if __name__ == "__main__":
    # Test cases
    test_responses = [
        # Simple JSON
        '{"key": "value", "number": 123}',

        # JSON in markdown
        "Here is the data:\n```json\n{\"key\": \"value\", \"number\": 123}\n```",

        # JSON with explanation
        "The result is as follows:\n```json\n{\"key\": \"value\", \"number\": 123}\n```\nLet me know if you need more info.",

        # Nested markdown
        "Data:\n```json\n{\n  \"outer\": {\n    \"inner\": {\n      \"key\": \"value\"\n    }\n  }\n}\n```",

        # No JSON
        "This response has no JSON."
    ]

    for resp in test_responses:
        print("Input Response:")
        print(resp)
        print("Extracted JSON:")
        try:
            result = BedrockResolverOutputParser.parse(resp)
            print(result)
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 40)
