from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from aie_mas.config import AieMasConfig


class OpenAICompatiblePlannerClient:
    def __init__(self, config: AieMasConfig, client: Any | None = None) -> None:
        self._config = config
        self._client = client

    def invoke_json_schema(
        self,
        *,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        schema_name: str,
    ) -> BaseModel:
        client = self._get_client()
        response_schema = response_model.model_json_schema()
        response_format = {"type": "json_object"}

        final_messages = list(messages)
        final_messages.append(
            {
                "role": "user",
                "content": (
                    "Return only a valid JSON object that matches this schema.\n"
                    f"Schema name: {schema_name}\n"
                    f"JSON schema:\n{json.dumps(response_schema, ensure_ascii=False, indent=2)}"
                ),
            }
        )

        request_kwargs = {
            "model": self._config.planner_model,
            "messages": final_messages,
            "temperature": self._config.planner_temperature,
            "response_format": response_format,
        }

        try:
            completion = client.chat.completions.create(**request_kwargs)
        except Exception:
            request_kwargs.pop("response_format", None)
            completion = client.chat.completions.create(**request_kwargs)

        raw_text = self._extract_content(completion)
        payload = self._extract_json_object(raw_text)
        return response_model.model_validate(payload)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The openai package is required for planner_backend='openai_sdk'. "
                "Install the linux-runtime extra or add openai to your environment."
            ) from exc

        self._client = OpenAI(
            base_url=self._config.planner_base_url,
            api_key=self._config.planner_api_key or "EMPTY",
            timeout=self._config.planner_timeout_seconds,
        )
        return self._client

    def _extract_content(self, completion: Any) -> str:
        message = completion.choices[0].message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif hasattr(item, "text"):
                    parts.append(str(getattr(item, "text")))
                else:
                    parts.append(str(item))
            return "".join(parts)
        return str(content)

    def _extract_json_object(self, raw_text: str) -> dict[str, Any]:
        candidate = raw_text.strip()
        if candidate.startswith("```"):
            candidate = self._strip_code_fence(candidate)

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"Planner response did not contain JSON: {raw_text!r}")
            payload = json.loads(candidate[start : end + 1])

        if not isinstance(payload, dict):
            raise ValueError(f"Planner response must be a JSON object: {payload!r}")
        return payload

    def _strip_code_fence(self, raw_text: str) -> str:
        lines = raw_text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return raw_text
