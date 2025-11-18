from queryengine import query_main_store
from embedder import embed_all_in_folder
import re
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

folder_path = os.path.join(BASE_DIR, "..", "..", "Reports", "Policies")
folder_path = os.path.abspath(folder_path)

print(folder_path)

embed_all_in_folder(folder_path)

# answer = query_main_store("What are the responsibilities of the managers in performance review.")