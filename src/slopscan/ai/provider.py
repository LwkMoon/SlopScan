"""AI provider abstraction (spec section 40/41).

SlopScan's optional AI-enhanced mode never sends raw source code or full
page content to a provider. It sends the *structured, aggregated evidence*
already produced by the deterministic scan (see ScanResult.as_summary_dict)
and asks for interpretation, not a verdict. See ai/pipeline.py for how the
result is folded back into the report, always clearly separated from
deterministic findings.

Adding a new provider means implementing `AIProvider.complete()` -- nothing
else in the codebase needs to change (see ai/anthropic_provider.py for the
reference implementation).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class AIProviderError(Exception):
    """Raised for provider-facing errors (missing key, network, bad response).
    Never includes the API key itself in the message (spec section 41)."""


@dataclass
class AICompletionRequest:
    system_prompt: str
    user_prompt: str
    max_tokens: int = 800


@dataclass
class AICompletionResponse:
    text: str
    model: str
    provider: str


class AIProvider(ABC):
    provider_id: str = "base"
    default_model: str = ""

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise AIProviderError(
                f"No API key provided for {self.provider_id}. "
                f"Set SLOPSCAN_AI_API_KEY, or pass --ai-provider with a configured key."
            )
        self.api_key = api_key
        self.model = model or self.default_model

    @abstractmethod
    def complete(self, request: AICompletionRequest) -> AICompletionResponse: ...


def get_provider(provider_id: str, api_key: str, model: str | None = None) -> AIProvider:
    """Provider registry lookup. Import providers lazily so `pip install
    slopscan` (no AI extras) never fails just because httpx-based provider
    modules exist -- they all use the same httpx dependency already
    required by the core package, so this is mostly about keeping the
    import graph clean and provider-agnostic."""
    from slopscan.ai.anthropic_provider import AnthropicProvider
    from slopscan.ai.google_provider import GoogleProvider
    from slopscan.ai.openai_provider import OpenAIProvider

    providers: dict[str, type[AIProvider]] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "google": GoogleProvider,
    }
    cls = providers.get(provider_id)
    if cls is None:
        raise AIProviderError(
            f"Unknown AI provider: {provider_id!r}. Available: {', '.join(sorted(providers))}"
        )
    return cls(api_key=api_key, model=model)
