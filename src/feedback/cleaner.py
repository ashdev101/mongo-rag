import re

def clean_text(text):
    """
    Replace all special characters in the given text with a space.
    Keeps only letters, digits, and spaces.
    """
    if not isinstance(text, str):
        raise TypeError("query must be a string.")

    # Replace any character that is NOT a letter, digit, or space with a space
    text_lower = text.lower()
    cleaned_text = re.sub(r'[^A-Za-z0-9 ]', ' ', text_lower)

    # Replace multiple spaces with a single space and strip leading/trailing spaces
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text