import os
from langchain_aws import BedrockEmbeddings
from dotenv import load_dotenv

load_dotenv()


bedrock_embeddings = BedrockEmbeddings(
                            model_id = "amazon.titan-embed-text-v2:0",
                            region_name = os.getenv("AWS_REGION"),
                        )
