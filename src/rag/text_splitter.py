import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

def chunk_text(text, max_tokens=800, overlap=100):
    tokens = enc.encode(text)
    chunks = []

    step = max_tokens - overlap
    for i in range(0, len(tokens), step):
        chunk_tokens = tokens[i:i + max_tokens]
        chunks.append(enc.decode(chunk_tokens))

    return chunks