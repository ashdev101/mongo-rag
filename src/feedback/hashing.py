import hashlib

def md5_hash_string(input_string: str) -> str:
    """
    Generate the MD5 hash of a given string.

    Args:
        input_string (str): The string to hash.

    Returns:
        str: The hexadecimal MD5 hash.
    """
    if not isinstance(input_string, str):
        raise TypeError("Input must be a string.")

    # Encode the string to bytes, as hashlib works with bytes
    encoded_str = input_string.encode('utf-8')

    # Create MD5 hash object
    md5_obj = hashlib.md5(encoded_str)

    # Return the hexadecimal digest
    return md5_obj.hexdigest()


