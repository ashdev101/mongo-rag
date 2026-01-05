#!/usr/bin/env python3
"""
Quick test script for Claude QnA system
Run with: python test_cqa.py
"""

import os
from dotenv import load_dotenv
from cqa import ClaudeQnA

# Load environment
load_dotenv()


def main():
    # Configuration
    MONGODB_URI = os.getenv("MONGODB_URI")
    DB_NAME = os.getenv("DB_NAME", "hr_bot_db")  # Use DB_NAME from .env
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

    if not MONGODB_URI:
        print("❌ Error: MONGODB_URI not set in .env file")
        print("   Copy .env.example to .env and configure your MongoDB URI")
        return

    print("🚀 Initializing Claude QnA System...")
    print(f"   Database: {DB_NAME}")
    print(f"   AWS Region: {AWS_REGION}")
    print()

    # Initialize QnA system
    try:
        qna = ClaudeQnA(mongodb_uri=MONGODB_URI, db_name=DB_NAME, aws_region=AWS_REGION)
        print("✅ System initialized successfully!")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return

    # Interactive mode
    print("\n" + "=" * 80)
    print("INTERACTIVE MODE - Ask questions about your HR data")
    print("=" * 80)
    print("Commands:")
    print("  'quit' or 'exit' - Exit the program")
    print("  'clear' or 'reset' - Clear conversation history")
    print("  'history' - Show conversation history")
    print("=" * 80 + "\n")

    question_count = 0

    while True:
        try:
            question = input("\n❓ Your question: ").strip()

            if question.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            if question.lower() in ["clear", "reset"]:
                qna.clear_history()
                question_count = 0
                print("✅ Conversation history cleared. Starting fresh!")
                continue

            if question.lower() == "history":
                print("\n" + "=" * 80)
                print("CONVERSATION HISTORY:")
                print("=" * 80)
                print(qna.get_history_summary())
                print("=" * 80)
                continue

            if not question:
                continue

            question_count += 1

            print(f"\n{'=' * 80}")
            print(f"🤔 Processing question #{question_count}...")
            if question_count > 1:
                print("   (Using conversation history for context)")
            print(f"{'=' * 80}")

            # Get answer with verbose output and history support
            answer = qna.answer_question(question, verbose=True, use_history=True)

            print(f"\n{'=' * 80}")
            print("📊 FINAL ANSWER:")
            print(f"{'=' * 80}")
            print(answer)
            print()

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Try asking your question differently.\n")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
