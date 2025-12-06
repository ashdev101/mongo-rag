import os
import time
import json
import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # Load .env file


def call_bedrock_model(model_id, system, user, temperature):
    """
    Calls a Bedrock model and returns response_text, latency_ms, and error_message.
    Errors are captured and returned instead of raising.
    """

    AWS_BEARER_TOKEN_BEDROCK = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    AWS_REGION = os.getenv("AWS_REGION")

    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION
    )


    payload = {
        "messages": [
            {"role": "system", "content": [{"type": "text", "text": system}]},
            {"role": "user", "content": [{"type": "text", "text": user}]}
        ],
        "temperature": temperature,
        "max_tokens": 1024
    }

    start = time.time()

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(payload)
        )

        latency_ms = round((time.time() - start) * 1000, 2)

        body = json.loads(response["body"].read())

        # Extract model response text safely
        output_text = ""
        if "output" in body and "message" in body["output"]:
            parts = body["output"]["message"].get("content", [])
            for p in parts:
                if p.get("type") == "text":
                    output_text += p.get("text", "")
        else:
            output_text = str(body)

        return output_text, latency_ms, None

    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        return None, latency_ms, str(e)



def model_wrapper(system,prompt,temp=0):
    model_id="qwen.qwen3-vl-235b-a22b"
    response_text, latency_ms, error_message = call_bedrock_model(
    model_id=model_id,
    system=system,
    user=prompt,
    temperature=temp)

    response_ob=eval(str(response_text))

    return error_message if response_ob == None else response_ob["choices"][0]["message"]["content"]



# Example Usage:

# from bedrock import model_wrapper
# print(model_wrapper(system="be friendly",prompt="hi"))