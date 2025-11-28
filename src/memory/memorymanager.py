import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import threading

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in the environment.")

client = MongoClient(MONGODB_URI)
db = client["test-saptarshi"]                   
collection = db["chat-history"]       

def push_convo_pair(email: str, user_msg: str = None, bot_msg: str = None, turns: list = None):
    """
    Fire-and-forget version. Saves conversation turn(s) to MongoDB asynchronously.
    Runs DB update in a background daemon thread.
    Caller will NOT wait; thread auto-kills itself after completion.
    
    Args:
        email: User email
        user_msg: Single user message (if saving one turn)
        bot_msg: Single bot message (if saving one turn)
        turns: List of dicts with 'user' and 'assistant' keys (if saving multiple turns)
               If provided, user_msg and bot_msg are ignored
    
    Usage:
        # Single turn:
        push_convo_pair(email, "user query", "bot response")
        
        # Multiple turns:
        push_convo_pair(email, turns=[
            {"user": "query1", "assistant": "response1"},
            {"user": "query2", "assistant": "response2"}
        ])
    """
    def _task():
        try:
            # Prepare turns to save
            turns_to_save = []
            
            if turns:
                # Multiple turns provided
                for turn in turns:
                    user = turn.get("user", "").strip() if isinstance(turn, dict) else ""
                    bot = turn.get("assistant", "").strip() if isinstance(turn, dict) else ""
                    if user or bot:  # Only save non-empty turns
                        turns_to_save.append({
                            "user": user,
                            "assistant": bot,
                            "ts": datetime.now()
                        })
            elif user_msg is not None or bot_msg is not None:
                # Single turn provided
                user = user_msg.strip() if user_msg else ""
                bot = bot_msg.strip() if bot_msg else ""
                if user or bot:  # Only save non-empty turn
                    turns_to_save.append({
                        "user": user,
                        "assistant": bot,
                        "ts": datetime.now()
                    })
            
            if not turns_to_save:
                return  # Nothing to save
            
            print(f"Updating History for {email} ({len(turns_to_save)} turn(s))")
            collection.update_one(
                {"email": email},
                {
                    "$push": {
                        "history": {
                            "$each": turns_to_save,
                            "$slice": -10
                        }
                    },
                    "$set": {"updated_at": datetime.now()}
                },
                upsert=True
            )
        except Exception as e:
            print(f"Failed to Update History for {email}, Error: {e}")

    # daemon=True ensures the thread dies automatically after finishing
    t = threading.Thread(target=_task, daemon=True)
    t.start()

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

def get_chat_history_as_messages(email: str):
    """
    Retrieve the last conversation turns (up to 10) as a list of message dictionaries.
    Returns list of dicts with 'user' and 'assistant' keys.
    """
    try:
        doc = collection.find_one(
            {"email": email},
            {"_id": 0, "history": 1}
        )

        if not doc or "history" not in doc:
            return []

        history = doc["history"]
        # Return last 10 messages as list of dicts
        return [{"user": turn.get("user", "").strip(), "assistant": turn.get("assistant", "").strip()} 
                for turn in history[-10:]]
    except Exception as e:
        print(f"Error retrieving chat history as messages: {e}")
        return []

def push_clarification_turns_async(email: str, clarification_turns: list):
    """
    DEPRECATED: Use push_convo_pair(email, turns=clarification_turns) instead.
    This function is kept for backward compatibility but now just calls push_convo_pair.
    
    Asynchronously push clarification conversation turns to MongoDB.
    clarification_turns: list of dicts with 'user' and 'assistant' keys
    """
    # Use the optimized push_convo_pair function
    push_convo_pair(email, turns=clarification_turns)