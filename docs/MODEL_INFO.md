# Claude Model Configuration

## Current Model (cqa.py)

**Claude Sonnet 4.5** (Latest from team's LLMFactory)

- **Model ID**: `global.anthropic.claude-sonnet-4-5-20250929-v1:0`
- **Region**: `ap-south-1` (Mumbai)
- **Database**: `hr-cleaned`
- **Source**: Matches team standard from `rbac_chat_his_local_schema_opus_4.5` branch

## Available Models in Team's LLMFactory

Based on `src/llm/LLMFactory.py` (commit `cc808b3`):

```python
bedrockModelId = {
    "qwen": "qwen.qwen3-235b-a22b-2507-v1:0",
    "claude_Opus_4.5": "global.anthropic.claude-opus-4-5-20251101-v1:0",
    "claude_Sonnet_4.5": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
}
```

### Model Comparison

| Model | Model ID | Use Case | Cost |
|-------|----------|----------|------|
| **Claude Sonnet 4.5** ✓ | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` | **Production** - Balanced performance/cost | Medium |
| Claude Opus 4.5 | `global.anthropic.claude-opus-4-5-20251101-v1:0` | Complex reasoning, highest quality | High |
| Qwen 3.5 | `qwen.qwen3-235b-a22b-2507-v1:0` | Fast inference, lower cost | Low |

## Model Prefix Differences

### Cross-Region Models (`global.*`)
- Work in **all AWS regions** including `ap-south-1`
- Recommended for production deployments
- Examples:
  - `global.anthropic.claude-sonnet-4-5-20250929-v1:0`
  - `global.anthropic.claude-opus-4-5-20251101-v1:0`

### Regional Models (`anthropic.*`)
- Only available in **us-east-1** and **us-west-2**
- Legacy format
- Examples:
  - `anthropic.claude-3-sonnet-20240229-v1:0`
  - `anthropic.claude-3-5-sonnet-20240620-v1:0`

## Configuration

### In `.env` file:
```env
AWS_REGION=ap-south-1
DB_NAME=hr-cleaned
CLAUDE_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### In code:
```python
from anthropic import AnthropicBedrock

client = AnthropicBedrock(aws_region="ap-south-1")

response = client.messages.create(
    model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    tools=TOOLS,
    messages=messages
)
```

## Recent Changes

### Commit History:
- `cc808b3` (Dec 26, 2024) - "model change to claude" - Switched to Claude Sonnet 4.5
- `e758bd7` (Dec 23, 2024) - "using bedrock instead of openai" - Migrated from OpenAI to AWS Bedrock
- `a8dddfd` - "Bedrock Qwen LLM Agent added" - Added Qwen support

### Migration Path:
```
OpenAI GPT-4 → AWS Bedrock Qwen → AWS Bedrock Claude Sonnet 4.5
```

## Why Claude Sonnet 4.5?

Based on the team's choice in the latest branches:

1. **Better Performance**: Superior to Claude 3.5 and Opus 3.5
2. **Tool Use**: Excellent tool calling capabilities (needed for MongoDB agent)
3. **Context Window**: 200K tokens (plenty for complex queries)
4. **Cost-Effective**: More affordable than Opus while maintaining high quality
5. **Regional Availability**: Works in ap-south-1 (Mumbai region)

## Switching Models

To use a different model, update your `.env`:

```bash
# For highest quality (more expensive):
CLAUDE_MODEL=global.anthropic.claude-opus-4-5-20251101-v1:0

# For current team standard (recommended):
CLAUDE_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0

# For faster/cheaper alternative:
# Note: Requires using ChatBedrockConverse instead of AnthropicBedrock
# CLAUDE_MODEL=qwen.qwen3-235b-a22b-2507-v1:0
```

## Testing

Test your configuration:
```bash
python scripts/test_bedrock_connection.py
```

This will verify:
- AWS credentials
- Model availability in your region
- Basic message API functionality
