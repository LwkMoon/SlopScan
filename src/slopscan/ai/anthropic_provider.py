from __future__ import annotations

import httpx

from slopscan.ai.provider import AICompletionRequest, AICompletionResponse, AIProvider, AIProviderError

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"


class AnthropicProvider(AIProvider):
    provider_id = "anthropic"
    default_model = "claude-3-5-haiku-latest"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        try:
            resp = httpx.post(
                _API_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": request.max_tokens,
                    "system": request.system_prompt,
                    "messages": [{"role": "user", "content": request.user_prompt}],
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Network error contacting Anthropic: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(f"Anthropic API returned HTTP {resp.status_code}: {_safe_snippet(resp.text)}")

        data = resp.json()
        text_parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
        return AICompletionResponse(text="\n".join(text_parts).strip(), model=self.model, provider=self.provider_id)


def _safe_snippet(text: str, limit: int = 300) -> str:
    return text[:limit] + ("..." if len(text) > limit else "")
