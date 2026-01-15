import os
from dotenv import load_dotenv
from anthropic import AsyncAnthropicBedrock

anthropic_client = AsyncAnthropicBedrock(
            aws_region="ap-south-1",
            aws_access_key=os.getenv("AWS_S3_USER_ACCESS_KEY"),
            aws_secret_key=os.getenv("AWS_S3_USER_SECRET_ACCESS_KEY"),
            max_retries=10,
        )

