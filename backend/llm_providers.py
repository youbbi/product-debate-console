"""
LLM Provider Abstraction Layer

Supports multiple LLM providers for the Council decision method:
- Azure OpenAI (GPT-4)
- Anthropic (Claude)
- Google (Gemini)
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ProviderInfo:
    """Information about an LLM provider"""
    id: str
    name: str
    model: str
    is_available: bool
    estimated_cost_per_1k_tokens: float


class LLMProvider(ABC):
    """Base class for LLM providers"""

    def __init__(self, provider_id: str, name: str, model: str):
        self.provider_id = provider_id
        self.name = name
        self.model = model

    @abstractmethod
    async def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Send prompt and get complete response"""
        pass

    @abstractmethod
    async def astream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        """Stream response token by token"""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider has valid credentials"""
        pass

    def get_info(self) -> ProviderInfo:
        """Get provider information"""
        return ProviderInfo(
            id=self.provider_id,
            name=self.name,
            model=self.model,
            is_available=self.is_configured(),
            estimated_cost_per_1k_tokens=self._get_cost_estimate()
        )

    @abstractmethod
    def _get_cost_estimate(self) -> float:
        """Get estimated cost per 1k tokens"""
        pass


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI GPT provider"""

    def __init__(self):
        model = os.getenv("AZURE_DEPLOYMENT_GPT4", "gpt-4-turbo")
        # Extract display name from deployment (e.g., "gpt-5.2-chat" -> "GPT-5.2")
        display_name = model.replace("-chat", "").replace("gpt-", "GPT-").replace("-", " ")
        super().__init__(
            provider_id="azure",
            name=display_name,
            model=model
        )
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self._llm = None
        if self.is_configured():
            logging.info(f"[Azure] Configured: endpoint={self.endpoint}, deployment={self.model}")
        else:
            logging.warning(f"[Azure] Not configured: missing endpoint or API key")

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def _get_cost_estimate(self) -> float:
        return 0.03  # ~$0.03 per 1k tokens for GPT-4-turbo

    def _get_llm(self):
        if self._llm is None:
            from langchain_openai import AzureChatOpenAI
            self._llm = AzureChatOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                deployment_name=self.model,
                api_version="2024-12-01-preview",
                temperature=1,
                max_tokens=2500
            )
        return self._llm

    async def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        llm = self._get_llm()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = await llm.ainvoke(messages)
        return response.content

    async def astream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        llm = self._get_llm()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider"""

    def __init__(self):
        super().__init__(
            provider_id="anthropic",
            name="Claude Sonnet 4.5",
            model="claude-sonnet-4-5-20250929"
        )
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client = None
        if self.is_configured():
            logging.info(f"[Anthropic] Configured: model={self.model}")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_cost_estimate(self) -> float:
        return 0.015  # ~$0.015 per 1k tokens for Claude 3.5 Sonnet

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        client = self._get_client()
        messages = [{"role": "user", "content": prompt}]
        response = await client.messages.create(
            model=self.model,
            max_tokens=2500,
            system=system_prompt or "",
            messages=messages
        )
        return response.content[0].text

    async def astream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        client = self._get_client()
        messages = [{"role": "user", "content": prompt}]
        async with client.messages.stream(
            model=self.model,
            max_tokens=2500,
            system=system_prompt or "",
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield text


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini provider"""

    def __init__(self):
        super().__init__(
            provider_id="google",
            name="Gemini 3 Pro",
            model="gemini-3-pro-preview"
        )
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self._model = None
        if self.is_configured():
            logging.info(f"[Google] Configured: model={self.model}")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_cost_estimate(self) -> float:
        return 0.00125  # ~$0.00125 per 1k tokens for Gemini 1.5 Pro

    def _get_model(self):
        if self._model is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model)
        return self._model

    async def invoke(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        model = self._get_model()
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        response = await model.generate_content_async(full_prompt)
        return response.text

    async def astream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        model = self._get_model()
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        response = await model.generate_content_async(
            full_prompt,
            stream=True
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text


# Provider Registry
PROVIDERS: Dict[str, type] = {
    "azure": AzureOpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleGeminiProvider,
}


def get_provider(provider_id: str) -> Optional[LLMProvider]:
    """Get a specific provider instance"""
    if provider_id in PROVIDERS:
        provider = PROVIDERS[provider_id]()
        if provider.is_configured():
            return provider
    return None


def get_configured_providers() -> List[LLMProvider]:
    """Get all providers with valid credentials"""
    configured = []
    for provider_class in PROVIDERS.values():
        provider = provider_class()
        if provider.is_configured():
            configured.append(provider)
    return configured


def get_available_provider_info() -> List[Dict[str, Any]]:
    """Get info about all available providers for API response"""
    providers = get_configured_providers()
    return [
        {
            "id": p.provider_id,
            "name": p.name,
            "model": p.model,
            "estimated_cost_per_1k_tokens": p._get_cost_estimate()
        }
        for p in providers
    ]


def calculate_cost_estimate(method: str, avg_tokens_per_call: int = 1500) -> Dict[str, Any]:
    """Calculate estimated cost for a decision method"""
    providers = get_configured_providers()
    num_providers = len(providers)

    if method == "consensus":
        # 6 calls: 1 context + 4 executives + 1 synthesis
        total_calls = 6
        # All use Azure OpenAI
        azure = get_provider("azure")
        if azure:
            cost_per_call = azure._get_cost_estimate() * (avg_tokens_per_call / 1000)
            total_cost = total_calls * cost_per_call
        else:
            total_cost = 0
        return {
            "method": "consensus",
            "total_calls": total_calls,
            "estimated_cost": round(total_cost, 3),
            "breakdown": f"{total_calls} calls to Azure OpenAI"
        }

    elif method == "council":
        # 3 divergence + 6 peer reviews (each LLM reviews 2 others) + 1 chairman
        divergence_calls = num_providers
        review_calls = num_providers * (num_providers - 1)  # Each reviews the others
        synthesis_calls = 1
        total_calls = divergence_calls + review_calls + synthesis_calls

        # Average cost across providers
        avg_cost = sum(p._get_cost_estimate() for p in providers) / num_providers if providers else 0
        cost_per_call = avg_cost * (avg_tokens_per_call / 1000)
        total_cost = total_calls * cost_per_call

        return {
            "method": "council",
            "total_calls": total_calls,
            "estimated_cost": round(total_cost, 3),
            "breakdown": f"{divergence_calls} divergence + {review_calls} peer reviews + {synthesis_calls} synthesis",
            "providers": num_providers
        }

    elif method == "both":
        consensus_estimate = calculate_cost_estimate("consensus", avg_tokens_per_call)
        council_estimate = calculate_cost_estimate("council", avg_tokens_per_call)
        total_cost = consensus_estimate["estimated_cost"] + council_estimate["estimated_cost"]
        total_calls = consensus_estimate["total_calls"] + council_estimate["total_calls"]

        return {
            "method": "both",
            "total_calls": total_calls,
            "estimated_cost": round(total_cost, 3),
            "breakdown": f"Consensus ({consensus_estimate['total_calls']} calls) + Council ({council_estimate['total_calls']} calls)"
        }

    return {"method": method, "total_calls": 0, "estimated_cost": 0, "breakdown": "Unknown method"}
