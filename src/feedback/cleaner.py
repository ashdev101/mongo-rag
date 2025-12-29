import re
from RegexPIIMasker import FieldBasedPIIMasker

def remove_emojis(text):
    """
    Remove all emoji characters from the given text.
    Uses regex to match emoji unicode ranges.
    """
    if not isinstance(text, str):
        return text
    
    # Emoji regex pattern covering most common emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # extended symbols
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002700-\U000027BF"  # dingbats
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)

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


def mask_data(text: str) -> str:
    print("Un-masked agg",text)
    masker = FieldBasedPIIMasker()

    data_l=eval(text)
    masked_data1= str(masker.mask(dict(data_l[0]))[0]) 
    masked_data2= str(masker.mask(dict(data_l[1]))[0])
    print("Un-masked agg",masked_data1+masked_data2)
    return "["+masked_data1+","+masked_data2+"]"
