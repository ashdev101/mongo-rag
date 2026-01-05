# Claude QnA (cqa.py) - Sequential Tool-Calling System

## Overview

`cqa.py` is a standalone sequential tool-calling QnA system that uses **Claude from AWS Bedrock** to answer questions about MongoDB data through intelligent, multi-step tool usage.

### Hypothesis Being Tested

**LLMs should perform sequential tool calls to reach a conclusion** rather than attempting to answer questions in a single shot. This approach allows the model to:
- Gather information incrementally
- Verify assumptions before querying
- Adapt based on intermediate results
- Build complex queries step-by-step

## Architecture

```
User Question
     ↓
┌────────────────────────────────┐
│   Claude from Bedrock          │
│   (Agentic Loop)               │
└────────────────────────────────┘
     ↓
┌────────────────────────────────┐
│   Tool Selection & Planning    │
└────────────────────────────────┘
     ↓
┌────────────────────────────────┐
│   Sequential Tool Calls:       │
│   1. list_collections          │
│   2. get_collection_schema     │
│   3. run_aggregation           │
└────────────────────────────────┘
     ↓
┌────────────────────────────────┐
│   MongoDB Execution            │
└────────────────────────────────┘
     ↓
┌────────────────────────────────┐
│   Results Analysis             │
└────────────────────────────────┘
     ↓
Final Answer
```

## Features

### 1. **Sequential Tool Calling (Agentic Loop)**
- Claude autonomously decides which tools to call and in what order
- Continues until reaching a final answer
- Maximum 10 iterations to prevent infinite loops

### 2. **Three MongoDB Tools**

#### `list_collections`
- Lists all available collections in the database
- No parameters required
- Used as first step to understand available data

#### `get_collection_schema`
- Inspects a collection's structure
- Parameters:
  - `collection_name` (required)
  - `sample_size` (optional, default: 3)
- Returns field names and sample documents

#### `run_aggregation`
- Executes MongoDB aggregation pipelines
- Parameters:
  - `collection_name` (required)
  - `pipeline` (required) - Array of aggregation stages
- Returns query results with metadata

### 3. **Intelligent Query Planning**
The system enforces a workflow:
1. **Discovery**: List collections to see what's available
2. **Schema Inspection**: Get field names and data structure
3. **Query Execution**: Run aggregation with verified field names
4. **Answer Synthesis**: Provide human-readable response

## Setup

### Prerequisites

1. **AWS Account with Bedrock Access**
   ```bash
   # Configure AWS credentials
   aws configure
   # Or set environment variables:
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_REGION=us-east-1
   ```

2. **Enable Claude in Bedrock**
   - Go to AWS Bedrock console
   - Request access to Anthropic Claude models
   - Enable cross-region access for:
     - `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (Claude Sonnet 4.5 - **recommended, matches team standard**)
     - `global.anthropic.claude-opus-4-5-20251101-v1:0` (Claude Opus 4.5 - higher capability)

3. **MongoDB Access**
   - Local MongoDB or MongoDB Atlas connection
   - Database named `hr-cleaned` (or modify `DB_NAME` in code)

### Installation

```bash
# Install dependencies
pip install anthropic pymongo python-dotenv

# Or using the existing pyproject.toml
uv pip install anthropic
```

### Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your credentials:
   ```env
   MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
   AWS_REGION=ap-south-1
   DB_NAME=hr-cleaned
   CLAUDE_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0
   ```

3. Test your Bedrock connection:
   ```bash
   python scripts/test_bedrock_connection.py
   ```

## Usage

### Basic Usage

```python
from cqa import ClaudeQnA

# Initialize the QnA system
qna = ClaudeQnA(
    mongodb_uri="mongodb://localhost:27017/",
    db_name="hr",
    aws_region="us-east-1"
)

# Ask a question
answer = qna.answer_question(
    "How many employees joined in 2024?",
    verbose=True  # Shows detailed execution steps
)

print(answer)
```

### Running the Test Suite

```bash
python cqa.py
```

This runs predefined test queries and shows the sequential tool-calling process.

### Custom Queries

Edit the `test_queries` list in `main()`:

```python
test_queries = [
    "How many employees are in the IT department?",
    "What is the average salary by department?",
    "Show me employees who joined in the last 3 months",
]
```

## Example Execution Flow

### Query: "How many employees are in the database?"

```
ITERATION 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Tool Call: list_collections
   Input: {}
   Result: {"collections": ["base_report", "leave_transaction", ...], "count": 5}

ITERATION 2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Tool Call: get_collection_schema
   Input: {"collection_name": "base_report", "sample_size": 3}
   Result: {"collection": "base_report", "total_documents": 1247, "fields": [...]}

ITERATION 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 Tool Call: run_aggregation
   Input: {
     "collection_name": "base_report",
     "pipeline": [{"$count": "total_employees"}]
   }
   Result: {"results": [{"total_employees": 1247}]}

FINAL ANSWER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
There are 1,247 employees in the database.
```

## Key Differences from Existing System

| Feature | Existing (Mongo.py) | New (cqa.py) |
|---------|---------------------|--------------|
| **Framework** | LangChain + LangGraph | Native Claude API |
| **Tool Calling** | ReAct agent (predefined) | Sequential agentic loop |
| **LLM** | OpenAI GPT-4 | Claude 3.5 Sonnet (Bedrock) |
| **Iterations** | Fixed agent steps | Dynamic (1-10 iterations) |
| **PII Masking** | RegexPIIMasker | None (testing hypothesis) |
| **Dependencies** | 29+ packages | 3 packages only |
| **Visibility** | Limited logging | Verbose execution trace |

## Benefits of Sequential Tool Calling

1. **Transparency**: See each step the LLM takes
2. **Accuracy**: LLM verifies schema before querying
3. **Debugging**: Easy to identify where queries fail
4. **Flexibility**: LLM adapts strategy based on intermediate results
5. **Cost-efficient**: Only calls tools when necessary

## Testing the Hypothesis

### Metrics to Track

1. **Number of iterations** per query
2. **Tool call sequence** patterns
3. **Success rate** (correct answers)
4. **Token usage** per query
5. **Latency** (time to final answer)

### Expected Behavior

- Simple queries: 2-3 iterations (list → schema → query)
- Complex queries: 4-6 iterations (multiple schema checks, query refinement)
- Failed queries: Should self-correct by re-inspecting schema

### Comparison Test

Run the same query through both systems:

```python
# Original system (Mongo.py)
from Mongo import NaturalLanguageToMQL
converter = NaturalLanguageToMQL()
converter.convert_to_mql_and_execute_query("How many IT employees?")

# New system (cqa.py)
from cqa import ClaudeQnA
qna = ClaudeQnA(...)
answer = qna.answer_question("How many IT employees?")
```

## Troubleshooting

### "Access denied" errors
- Check AWS credentials: `aws sts get-caller-identity`
- Verify Bedrock model access in AWS console
- Ensure IAM role has `bedrock:InvokeModel` permission

### "Model not found" errors
- Update `CLAUDE_MODEL` to an available model ID
- Check available models: AWS Bedrock console → Model access

### MongoDB connection errors
- Verify `MONGODB_URI` format
- Test connection: `mongosh "mongodb://..."`
- Check network access (IP whitelist for Atlas)

### "Maximum iterations reached"
- Query might be too ambiguous
- Increase `max_iterations` in `ClaudeQnA.__init__`
- Simplify the question

## Next Steps

1. **Add PII Masking**: Integrate with existing `RegexPIIMasker`
2. **Add Access Control**: Integrate with `langgraph_sample.py`
3. **Add Query Router**: Use `Router_gpt.py` for POLICY vs DOCUMENT routing
4. **Metrics Collection**: Log iteration count, tool sequences, latency
5. **Comparison Study**: Run both systems on identical queries and compare

## Code Structure

```
cqa.py
├── MongoDBToolExecutor     # Executes MongoDB operations
│   ├── list_collections()
│   ├── get_collection_schema()
│   ├── run_aggregation()
│   └── execute_tool()
│
├── ClaudeQnA               # Main QnA system
│   ├── __init__()          # Initialize Claude & MongoDB
│   └── answer_question()   # Agentic loop implementation
│
└── main()                  # Test harness
```

## License

Same as parent project.
