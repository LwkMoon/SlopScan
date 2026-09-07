from __future__ import annotations

import httpx

from slopscan.ai.provider import AICompletionRequest, AICompletionResponse, AIProvider, AIProviderError


class GoogleProvider(AIProvider):
    provider_id = "google"
    default_model = "gemini-1.5-flash"

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        try:
            resp = httpx.post(
                url,
                json={
                    "system_instruction": {"parts": [{"text": request.system_prompt}]},
                    "contents": [{"parts": [{"text": request.user_prompt}]}],
                    "generationConfig": {"maxOutputTokens": request.max_tokens},
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Network error contacting Google: {exc}") from exc

        if resp.status_code != 200:
            raise AIProviderError(f"Google API returned HTTP {resp.status_code}: {_safe_snippet(resp.text)}")

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as exc:
            raise AIProviderError("Unexpected Google response shape") from exc
        return AICompletionResponse(text=text, model=self.model, provider=self.provider_id)


def _safe_snippet(text: str, limit: int = 300) -> str:
    return text[:limit] + ("..." if len(text) > limit else "")
