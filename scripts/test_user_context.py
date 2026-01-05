#!/usr/bin/env python3
"""
Test script to demonstrate user context injection in system prompt

Shows how different users get different system prompts with their metadata.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rbac_manager import RBACManager
from cqa import ClaudeQnA
from dotenv import load_dotenv

load_dotenv()


def show_user_context(emp_code: int, description: str):
    """Show system prompt for a given user"""
    print("=" * 80)
    print(f"USER: {description}")
    print("=" * 80)
    print()

    # Initialize QnA system for this user
    try:
        qna = ClaudeQnA(
            mongodb_uri=os.getenv("MONGODB_URI"),
            db_name=os.getenv("DB_NAME", "hr-cleaned"),
            aws_region=os.getenv("AWS_REGION", "ap-south-1"),
            user_emp_code=emp_code
        )

        # Get and display system prompt
        prompt = qna.get_system_prompt()

        # Extract just the USER CONTEXT section for display
        lines = prompt.split('\n')
        in_context = False
        context_lines = []

        for line in lines:
            if 'USER CONTEXT:' in line:
                in_context = True
            elif 'STRICT GUARDRAILS:' in line:
                break

            if in_context:
                context_lines.append(line)

        print('\n'.join(context_lines))
        print()

    except Exception as e:
        print(f"Error: {e}")
        print()


def main():
    print("=" * 80)
    print("USER CONTEXT INJECTION TEST")
    print("=" * 80)
    print()
    print("This demonstrates how user metadata is injected into the system prompt")
    print("so Claude knows who is asking questions and what data they can access.")
    print()

    # Test different users
    test_users = [
        (3996, "Sangram Chavan - CHRO (Full Access)"),
        (7190, "Ashwin Shukla - SVP HR (Full Access)"),
        (6671, "Pallavi Kaushik - Manager HR (North Region Only)"),
        (871, "Pramatesh V. Kumar - VP HR (Corporate, West, Central)"),
        (None, "Anonymous User (No RBAC)"),
    ]

    for emp_code, description in test_users:
        show_user_context(emp_code, description)

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Benefits of user context injection:")
    print("  1. Claude knows who is asking the question")
    print("  2. Claude understands the user's access level")
    print("  3. Claude can provide personalized responses")
    print("  4. Claude knows not to mention access restrictions")
    print("  5. Transparent to the end user")
    print()


if __name__ == "__main__":
    main()
