import json
from typing import Any

from app.clients.ai import OpenRouterClient
from app.providers.ai.base import AIProvider


class OpenRouterProvider(AIProvider):
    def __init__(self, client: OpenRouterClient) -> None:
        self.client = client

    async def structured_generate(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        response = await self.client.chat_completion(payload)
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        return json.loads(content)
