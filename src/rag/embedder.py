import os
from loaders import load_document
from VectorStoreManager import VectorStoreManager
from text_splitter import chunk_text

vector_manager = VectorStoreManager()

SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx"]


def embed_file(file_path):
    raw_texts = load_document(file_path)

    # Ensure list
    if isinstance(raw_texts, str):
        raw_texts = [raw_texts]

    chunks = []
    for text in raw_texts:
        chunks.extend(chunk_text(text))

    vector_manager.add_texts(chunks)
    return len(chunks)


def embed_all_in_folder(folder_path):
    results = []

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if not os.path.isfile(file_path):
            continue

        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"Skipping unsupported file: {filename}")
            continue

        try:
            chunks = embed_file(file_path)
            results.append({
                "file": filename,
                "chunks": chunks
            })
            print(f"✔ Embedded {filename} ({chunks} chunks)")

        except Exception as e:
            print(f"❌ Failed to embed {filename}: {e}")

    print("\nEmbedding complete — all documents stored in ONE vectorstore.")
    return results

