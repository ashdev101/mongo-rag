import os
from typing import Literal, Optional, Dict, Any
from langchain_aws import ChatBedrockConverse 
from langchain_openai import ChatOpenAI
from llm.bedrock import bedrock_runtime_client
from dotenv import load_dotenv
app_dir = os.path.join(os.getcwd())
load_dotenv(os.path.join(app_dir, ".env"))


Provider = Literal["bedrock", "openai"]


bedrockModelId = {
    "qwen": "qwen.qwen3-235b-a22b-2507-v1:0",
    "claude_Opus_4.5": "global.anthropic.claude-opus-4-5-20251101-v1:0",
    "claude_Sonnet_4.5" : "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude_3_haiku" : "global.anthropic.claude-3-haiku-20240307-v1:0",
}

class LLMFactory:
    """
    Unified interface for all LLM providers and models.
    """

    # ---- Provider → default model mapping ----
    DEFAULT_MODELS = {
        "bedrock": "qwen.qwen3-vl-235b-a22b",
        "openai": "gpt-4o-mini",
    }

    def __init__(
        self,
        provider: Provider,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any,
    ):
        self.provider = provider
        self.model = model or self.DEFAULT_MODELS[provider]
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_kwargs = kwargs

    def create(self):
        """
        Return a LangChain-compatible chat model.
        """
        if self.provider == "bedrock":
            return self._create_bedrock()

        if self.provider == "openai":
            return self._create_openai()

        raise ValueError(f"Unsupported provider: {self.provider}")

    # -------- Provider implementations --------

    def _create_bedrock(self)  -> ChatBedrockConverse:
        region = os.getenv("AWS_REGION", "ap-south-1")

        return ChatBedrockConverse(
            model_id=self.model,
            region_name=region,
            client=bedrock_runtime_client,
            # Enable when supported
            # model_kwargs={
            #     "temperature": self.temperature,
            #     "max_tokens": self.max_tokens,
            # },
            **self.extra_kwargs,
        )

    def _create_openai(self):
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.extra_kwargs,
        )


if __name__ == "__main__":
    llm = LLMFactory(
    provider="bedrock",
    model="qwen.qwen3-vl-235b-a22b",
    ).create()