import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in the environment.")

client = MongoClient(MONGODB_URI)
db = client["test-saptarshi"]                   
collection = db["chat-history"]       

def push_convo_pair(email: str, user_msg: str, bot_msg: str):
    """
    Push the latest conversation pair and keep only the last 10 items.
    """
    try:
        print("Updating History for",email)
        collection.update_one(
            {"email": email},
            {
                "$push": {
                    "history": {
                        "$each": [
                            {
                                "user": user_msg,
                                "assistant": bot_msg,
                                "ts": datetime.now()
                            }
                        ],
                        "$slice": -10
                    }
                },
                "$set": {"updated_at": datetime.now()}
            },
            upsert=True
        )
        return
    except:
        print("Failed to Update History for",email)

def get_chat_history(email: str):
    """
    Retrieve the last conversation turns (up to 10), remove `ts`,
    format them with newline separation, and return as a single string.
    """
    try:
        doc = collection.find_one(
            {"email": email},
            {"_id": 0, "history": 1}
        )

        if not doc or "history" not in doc:
            return ""

        history = doc["history"]

        formatted_lines = []

        for turn in history:
            # Remove timestamp if present
            turn.pop("ts", None)

            user_msg = turn.get("user", "").strip()
            bot_msg = turn.get("assistant", "").strip()

            formatted_lines.append(f"User: {user_msg}\nAssistant: {bot_msg}")

        # Join all turns into a clean prompt block
        return "\n\n".join(formatted_lines)
    except:
        return "Error retreiving Chat History"
    
if __name__ == "__main__":
    test_email = "Shayanta.Chaudhuri@tataplay.com"
    print(get_chat_history(test_email))