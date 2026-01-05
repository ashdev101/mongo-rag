#!/usr/bin/env python3
"""
Quick test to verify AWS Bedrock connection and Claude access
Run this first before running cqa.py
"""

import os
from dotenv import load_dotenv
from anthropic import AnthropicBedrock

load_dotenv()


def test_bedrock_connection():
    """Test basic Bedrock connection"""

    aws_region = os.getenv("AWS_REGION", "ap-south-1")
    claude_model = os.getenv(
        "CLAUDE_MODEL", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )

    print("=" * 80)
    print("AWS Bedrock Connection Test")
    print("=" * 80)
    print(f"AWS Region: {aws_region}")
    print("Claude Model: Claude Sonnet 4.5 (team standard)")
    print(f"Model ID: {claude_model}")
    print()

    try:
        print("🔄 Initializing AnthropicBedrock client...")
        client = AnthropicBedrock(
            aws_region=aws_region,
            aws_access_key=os.getenv("AWS_S3_USER_ACCESS_KEY"),
            aws_secret_key=os.getenv("AWS_S3_USER_SECRET_ACCESS_KEY"),
        )
        print("✅ Client initialized successfully!")

        print("\n🔄 Testing basic message call...")
        resp = client.messages.create(
            model=claude_model,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": "Hello from Bedrock! Please respond with 'Connection successful' if you receive this.",
                }
            ],
        )

        print("✅ Message call successful!")
        print("\n" + "=" * 80)
        print("CLAUDE'S RESPONSE:")
        print("=" * 80)
        print(resp.content[0].text)
        print("=" * 80)

        # Test tool calling capability (required for cqa.py)
        print("\n🔄 Testing tool calling capability...")
        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "A test message"}
                    },
                    "required": ["message"],
                },
            }
        ]

        tool_resp = client.messages.create(
            model=claude_model,
            max_tokens=200,
            tools=tools,
            messages=[
                {"role": "user", "content": "Use the test_tool with message 'hello'"}
            ],
        )

        if tool_resp.stop_reason == "tool_use":
            print("✅ Tool calling works correctly!")
        else:
            print(
                f"⚠️  Tool calling test completed (stop_reason: {tool_resp.stop_reason})"
            )

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED - Bedrock connection is working correctly!")
        print("=" * 80)
        print("\nYou can now run:")
        print("  python test_cqa.py     (interactive mode)")
        print("  python cqa.py          (test suite)")

        return True

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting steps:")
        print("1. Check AWS credentials:")
        print("   aws sts get-caller-identity")
        print("\n2. Verify Bedrock model access:")
        print("   Go to AWS Console → Bedrock → Model access")
        print(f"   Ensure '{claude_model}' is enabled")
        print("\n3. Check IAM permissions:")
        print("   Ensure your IAM user/role has 'bedrock:InvokeModel' permission")
        print(
            "   Required policy: AmazonBedrockFullAccess or custom with bedrock:InvokeModel"
        )
        print("\n4. Verify region and model:")
        print(f"   Current region: {aws_region}")
        print(
            "   Cross-region models (global.*) work in all regions including ap-south-1"
        )
        print("   Regional models (anthropic.*) only work in us-east-1/us-west-2")
        print("\n5. Check .env file:")
        print("   Ensure AWS_REGION and CLAUDE_MODEL are set correctly")

        return False


if __name__ == "__main__":
    success = test_bedrock_connection()
    exit(0 if success else 1)
