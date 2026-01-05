#!/usr/bin/env python3
"""
Claude QnA (cqa.py)
Sequential Tool-Calling QnA System using Claude from Bedrock with MongoDB

Hypothesis: LLM should perform sequential tool calls to reach a conclusion
rather than trying to answer in a single shot.

This implementation uses Claude's native tool use API with an agentic loop
that allows multiple rounds of tool calls until the LLM reaches a final answer.
"""

import os
import json
from typing import List, Dict, Any
from pymongo import MongoClient
from bson.json_util import dumps
from dotenv import load_dotenv
from anthropic import AnthropicBedrock

# Load environment variables
load_dotenv()

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "hr-cleaned")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Claude Bedrock Model IDs - based on your team's LLMFactory.py:
# Cross-region models (global.* prefix work in ap-south-1):
# - global.anthropic.claude-sonnet-4-5-20250929-v1:0 (Claude Sonnet 4.5 - currently used)
# - global.anthropic.claude-opus-4-5-20251101-v1:0 (Claude Opus 4.5)
# Regional models (anthropic.* prefix for us-east-1/us-west-2):
# - anthropic.claude-3-sonnet-20240229-v1:0 (Claude 3 Sonnet)
# - anthropic.claude-3-5-sonnet-20240620-v1:0 (Claude 3.5 Sonnet v1)
CLAUDE_MODEL = os.getenv(
    "CLAUDE_MODEL", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
)

# MongoDB Tools Definition
TOOLS = [
    {
        "name": "list_collections",
        "description": "List all available collections in the MongoDB database. Use this first to understand what data is available.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_collection_schema",
        "description": "Get the schema and sample documents from a specific collection to understand its structure and fields. Always inspect the schema before writing queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_name": {
                    "type": "string",
                    "description": "The name of the collection to inspect",
                },
                "sample_size": {
                    "type": "integer",
                    "description": "Number of sample documents to retrieve (default: 3)",
                    "default": 3,
                },
            },
            "required": ["collection_name"],
        },
    },
    {
        "name": "run_aggregation",
        "description": "Execute a MongoDB aggregation pipeline on a specified collection. The pipeline should be a valid MongoDB aggregation array. Only use this after inspecting the schema.",
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_name": {
                    "type": "string",
                    "description": "The name of the collection to query",
                },
                "pipeline": {
                    "type": "array",
                    "description": 'MongoDB aggregation pipeline as an array of stage objects. Example: [{"$match": {"status": "active"}}, {"$limit": 10}]',
                    "items": {"type": "object"},
                },
            },
            "required": ["collection_name", "pipeline"],
        },
    },
]

# System prompt for Claude
SYSTEM_PROMPT = """You are a specialized assistant that answers questions about TataPlay's HR data only.

STRICT GUARDRAILS:
1. **ONLY answer questions related to TataPlay's HR data** - employees, leaves, performance, assignments, offboarding, training, etc.
2. **REFUSE to answer** questions about:
   - General knowledge, current events, or topics unrelated to this HR database
   - Your own architecture, capabilities, or how you work internally
   - Programming help, code explanations, or technical tutorials
   - Other companies, organizations, or datasets
3. **If asked an irrelevant question**, politely decline with: "I can only answer questions about TataPlay's HR data. Please ask about employees, leave balances, departments, performance, or other HR-related information."
4. **If asked about yourself or how you work**, respond with: "I answer questions about TataPlay's HR data. How can I help you with employee information?"
5. **Stay focused** - Do not engage in conversations outside the HR data domain.

DATABASE CONTEXT:
The database contains the following types of data:
- **base_report**: Master employee data (employee codes, names, emails, departments, designations, regions, DOJ, DOB, etc.)
- **leave_transaction**: Employee leave records with three types of leaves:
  - Sick Leave
  - Casual Leave
  - Paid Leave
  Note: When asked about total leaves, sum all three types. If no records found, employee has taken no leaves.
- **offboarding**: Offboarding checklists and status by department (IT, HR, Finance, etc.)
- **pip_status**: Performance Improvement Plan status reports
- **pip_transaction**: PIP transaction details and history
- **performance_goals**: Employee performance goal reports
- **goal_status**: Status of performance goals
- **probation_confirmation**: Probation employee confirmation reports
- **classroom_requests**: Training/classroom course requests
- **assignment_details**: Employee assignment information

IMPORTANT INSTRUCTIONS:
1. **Always start by listing collections** to see what data is available
2. **Inspect the schema** of relevant collections before writing any queries
3. **Write precise aggregation pipelines** based on the actual field names you see in the schema
4. **Use sequential tool calls** - don't try to guess; verify each step
5. **Limit results** to a reasonable number (default 50) unless user specifies otherwise
6. **Only query relevant fields** - use $project to limit fields in the output
7. **Never make assumptions** about field names or data structure - always check first
8. **Field names may vary** - they could be lowercase, uppercase, or title case (e.g., "primary email" vs "Primary Email")

WORKFLOW:
Step 1: list_collections → understand available data
Step 2: get_collection_schema → understand structure of relevant collections
Step 3: run_aggregation → execute the query based on verified schema
Step 4: Provide a clear, concise answer based on the results

QUERY RULES:
- Only use aggregation queries (read-only)
- Always include $limit stage (default 50)
- Use $project to return only relevant fields
- Field names are case-sensitive - use exact names from schema
- For counting, use $group with $sum
- For filtering, use $match
- For sorting, use $sort
- For date comparisons, be aware of different date formats (strings vs Date objects)

COMMON QUERY PATTERNS:
- Employee lookup: Match by "employee code" or "primary email"
- Leave balance: Sum "Sick Leave", "Casual Leave", "Paid Leave" from leave_transaction
- Department queries: Match on "department" or "DEPARTMENT" field in base_report
- Offboarding status: Check offboarding collection by department and employee
- Active employees: Filter by "Assignment Status Type" = "ACTIVE" in base_report

OUTPUT FORMAT:
- Provide clear, human-readable answers
- Format data in tables or lists when appropriate
- Include relevant context from the query results
- If no results found, explain why and suggest alternatives
- Be concise but informative
"""


class MongoDBToolExecutor:
    """Executes MongoDB tool calls"""

    def __init__(self, mongodb_uri: str, db_name: str):
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[db_name]

    def list_collections(self) -> str:
        """List all collections in the database"""
        try:
            collections = self.db.list_collection_names()
            return json.dumps(
                {"collections": collections, "count": len(collections)}, indent=2
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def get_collection_schema(self, collection_name: str, sample_size: int = 3) -> str:
        """Get schema information and sample documents from a collection"""
        try:
            if collection_name not in self.db.list_collection_names():
                return json.dumps(
                    {"error": f"Collection '{collection_name}' does not exist"}
                )

            collection = self.db[collection_name]

            # Get sample documents
            samples = list(collection.find({}).limit(sample_size))

            # Get field names from samples
            all_fields = set()
            for doc in samples:
                all_fields.update(doc.keys())

            # Get document count
            doc_count = collection.count_documents({})

            result = {
                "collection": collection_name,
                "total_documents": doc_count,
                "fields": sorted(list(all_fields)),
                "sample_documents": samples,
            }

            return dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def run_aggregation(self, collection_name: str, pipeline: List[Dict]) -> str:
        """Run an aggregation pipeline on a collection"""
        try:
            if collection_name not in self.db.list_collection_names():
                return json.dumps(
                    {"error": f"Collection '{collection_name}' does not exist"}
                )

            collection = self.db[collection_name]

            # Execute aggregation
            results = list(collection.aggregate(pipeline))

            return dumps(
                {
                    "collection": collection_name,
                    "pipeline": pipeline,
                    "result_count": len(results),
                    "results": results,
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps(
                {"error": str(e), "collection": collection_name, "pipeline": pipeline}
            )

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Execute a tool by name with given input"""
        if tool_name == "list_collections":
            return self.list_collections()
        elif tool_name == "get_collection_schema":
            return self.get_collection_schema(
                collection_name=tool_input["collection_name"],
                sample_size=tool_input.get("sample_size", 3),
            )
        elif tool_name == "run_aggregation":
            return self.run_aggregation(
                collection_name=tool_input["collection_name"],
                pipeline=tool_input["pipeline"],
            )
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})


class ClaudeQnA:
    """Sequential tool-calling QnA system using Claude from Bedrock"""

    def __init__(self, mongodb_uri: str, db_name: str, aws_region: str = "us-east-1"):
        # Initialize Claude Bedrock client
        self.client = AnthropicBedrock(
            aws_region=aws_region,
            aws_access_key=os.getenv("AWS_S3_USER_ACCESS_KEY"),
            aws_secret_key=os.getenv("AWS_S3_USER_SECRET_ACCESS_KEY"),
        )

        # Initialize MongoDB tool executor
        self.mongo_executor = MongoDBToolExecutor(mongodb_uri, db_name)

        self.max_iterations = 10  # Prevent infinite loops

        # Conversation history for follow-up questions
        self.conversation_history = []

    def answer_question(
        self, question: str, verbose: bool = True, use_history: bool = True
    ) -> str:
        """
        Answer a question using sequential tool calling.

        This implements an agentic loop where Claude can:
        1. Call tools to gather information
        2. Analyze results
        3. Call more tools if needed
        4. Provide a final answer

        Args:
            question: User's natural language question
            verbose: If True, print detailed execution steps
            use_history: If True, include conversation history for follow-up questions

        Returns:
            Final answer from Claude
        """
        # Build messages with conversation history
        if use_history and self.conversation_history:
            # Start with conversation history
            messages = self.conversation_history.copy()
            # Add new user question
            messages.append({"role": "user", "content": question})
        else:
            # Fresh conversation
            messages = [{"role": "user", "content": question}]

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            if verbose:
                print(f"\n{'=' * 80}")
                print(f"ITERATION {iteration}")
                print(f"{'=' * 80}")

            # Call Claude with tools
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if verbose:
                print("\nClaude's response:")
                print(f"Stop reason: {response.stop_reason}")
                print(f"Content blocks: {len(response.content)}")

            # Check if Claude is done (no more tool calls)
            if response.stop_reason == "end_turn":
                # Extract final text answer
                final_answer = ""
                for block in response.content:
                    if block.type == "text":
                        final_answer += block.text

                if verbose:
                    print(f"\n{'=' * 80}")
                    print("FINAL ANSWER")
                    print(f"{'=' * 80}")

                # Save conversation history for follow-up questions
                if use_history:
                    # Add user's question to history (if not already there)
                    if not self.conversation_history:
                        self.conversation_history.append(
                            {"role": "user", "content": question}
                        )
                    elif self.conversation_history[-1].get("content") != question:
                        self.conversation_history.append(
                            {"role": "user", "content": question}
                        )

                    # Add assistant's response to history (save as plain text for simplicity)
                    self.conversation_history.append(
                        {"role": "assistant", "content": final_answer}
                    )

                return final_answer

            # Process tool calls
            if response.stop_reason == "tool_use":
                # Add Claude's response to conversation
                messages.append({"role": "assistant", "content": response.content})

                # Execute all tool calls and collect results
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        if verbose:
                            print(f"\n🔧 Tool Call: {tool_name}")
                            print(f"   Input: {json.dumps(tool_input, indent=2)}")

                        # Execute the tool
                        result = self.mongo_executor.execute_tool(tool_name, tool_input)

                        if verbose:
                            print(
                                f"   Result preview: {result[:200]}..."
                                if len(result) > 200
                                else f"   Result: {result}"
                            )

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": result,
                            }
                        )

                # Add tool results to conversation
                messages.append({"role": "user", "content": tool_results})
            else:
                # Unexpected stop reason
                if verbose:
                    print(f"\nUnexpected stop reason: {response.stop_reason}")
                break

        # Max iterations reached
        if iteration >= self.max_iterations:
            return f"Maximum iterations ({self.max_iterations}) reached. Could not complete the query."

        return "No answer generated."

    def clear_history(self):
        """Clear conversation history to start fresh"""
        self.conversation_history = []

    def get_history_summary(self) -> str:
        """Get a summary of the conversation history"""
        if not self.conversation_history:
            return "No conversation history"

        summary = []
        for i, msg in enumerate(self.conversation_history):
            role = msg["role"]
            if role == "user":
                summary.append(f"Q{i // 2 + 1}: {msg['content']}")
            elif role == "assistant":
                # Extract text from content
                if isinstance(msg["content"], list):
                    text = " ".join(
                        [
                            block.get("text", "")
                            for block in msg["content"]
                            if block.get("type") == "text"
                        ]
                    )
                else:
                    text = msg["content"]
                summary.append(
                    f"A{i // 2 + 1}: {text[:100]}..."
                    if len(text) > 100
                    else f"A{i // 2 + 1}: {text}"
                )

        return "\n".join(summary)


def main():
    """Main entry point for testing"""

    # Check required environment variables
    if not MONGODB_URI:
        print("Error: MONGODB_URI environment variable not set")
        return

    print("=" * 80)
    print("Claude QnA - Sequential Tool-Calling System")
    print("=" * 80)
    print(f"MongoDB Database: {DB_NAME}")
    print("Claude Model: Claude Sonnet 4.5 (matches team LLMFactory)")
    print(f"Model ID: {CLAUDE_MODEL}")
    print(f"AWS Region: {AWS_REGION}")
    print("=" * 80)

    # Initialize QnA system
    qna = ClaudeQnA(mongodb_uri=MONGODB_URI, db_name=DB_NAME, aws_region=AWS_REGION)

    # Test queries
    test_queries = [
        "How many employees are in the database?",
        "What is my leave balance? My email is ashwinit@tatasky.com",
        "List the top 5 employees who joined most recently",
        "How many employees are from the IT department?",
    ]

    print("\nRunning test queries...\n")

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'#' * 80}")
        print(f"QUERY {i}: {query}")
        print(f"{'#' * 80}")

        answer = qna.answer_question(query, verbose=True)

        print("\n📊 FINAL ANSWER:")
        print(answer)
        print(f"\n{'#' * 80}\n")

        # Uncomment to run only first query during testing
        # break

    print("\n✅ Testing complete!")


if __name__ == "__main__":
    main()
