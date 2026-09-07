from __future__ import annotations

import httpx

from slopscan.ai.provider import AICompletionRequest, AICompletionResponse, AIProvider, AIProviderError

_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    provider_id = "openai"
    default_model = "gpt-4o-mini"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        try:
            resp = httpx.post(
                _API_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"},
                json={
                    "model": self.model,
                    "max_tokens": request.max_tokens,
                    "messages": [
                        {"role": "system", "content": request.system_prompt},
                        {"role": "user", "content": request.user_prompt},
                    ],
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Network error contacting OpenAI: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(f"OpenAI API returned HTTP {resp.status_code}: {_safe_snippet(resp.text)}")

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            raise AIProviderError("Unexpected OpenAI response shape") from exc
        return AICompletionResponse(text=text, model=self.model, provider=self.provider_id)


def _safe_snippet(text: str, limit: int = 300) -> str:
    return text[:limit] + ("..." if len(text) > limit else "")
