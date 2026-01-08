import os
from dotenv import load_dotenv
from anthropic import AnthropicBedrock
from src.nitya_poc.MongoDBToolExecutor import MongoDBToolExecutor
from src.nitya_poc.SYSTEM_PROMPT_TEMPLATE import SYSTEM_PROMPT_TEMPLATE
import json

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
        "description": "Execute a MongoDB aggregation pipeline on a specified collection. The pipeline should be a valid MongoDB aggregation array. Only use this after inspecting the schema.The result of the aggregation will be as per the users allowed access level.",
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

class ClaudeQnA:
    """
    Sequential tool-calling QnA system using Claude (Bedrock).
    RBAC REMOVED.
    PII supported.
    """

    def __init__(
        self,
        mongo_executor : MongoDBToolExecutor,
        pii_masker,
        user_context: dict,
        aws_region: str = "ap-south-1",
    ):
        self.client = AnthropicBedrock(
            aws_region=aws_region,
            aws_access_key=os.getenv("AWS_S3_USER_ACCESS_KEY"),
            aws_secret_key=os.getenv("AWS_S3_USER_SECRET_ACCESS_KEY"),
        )


        self.mongo_executor = mongo_executor
        self.pii_masker = pii_masker

        self.max_iterations = 10
        self.conversation_history = []

        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "{user_context}",
        json.dumps(user_context, indent=2)

)

    def answer_question(
        self,
        question: str,
        verbose: bool = False,
        use_history: bool = False,
    ) -> str:

        # ---------------- PII PRE-MASK ----------------
        masked, mapping = self.pii_masker.mask({"query": question})
        masked_question = masked["query"]

        messages = []
        if use_history and self.conversation_history:
            messages.extend(self.conversation_history)

        messages.append({"role": "user", "content": question}) # dont mask as of now

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens= 4096,
                system=self.system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                final_text = ""
                for block in response.content:
                    if block.type == "text":
                        final_text += block.text

                # ---------------- PII UNMASK ----------------
                # final_text = self.pii_masker.unmask(
                #     {"content": final_text}, mapping
                # )["content"]
                final_text = final_text

                if use_history:
                    self.conversation_history.append(
                        {"role": "user", "content": masked_question}
                    )
                    self.conversation_history.append(
                        {"role": "assistant", "content": final_text}
                    )

                return final_text

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self.mongo_executor.execute_tool(
                            block.name, block.input
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

                messages.append({"role": "user", "content": tool_results})

        return "UnablLe to answer the question. Please try rephrasing it , or try after some time."

    def clear_history(self):
        self.conversation_history = []

    def get_system_prompt(self) -> str:
        return self.system_prompt
    

# if __name__ == "__main__":


