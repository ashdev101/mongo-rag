import os
import boto3
from botocore.config import Config

bedrock_runtime_client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION", "ap-south-1"),
    config=Config(
        retries={
            "mode": "adaptive",
            "max_attempts": 10,
        },
        max_pool_connections=50,  # important for Sonnet
    ),
)
