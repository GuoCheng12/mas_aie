from __future__ import annotations

import json
from typing import Any, Optional, Type

from pydantic import BaseModel

from aie_mas.config import AieMasConfig


class OpenAICompatibleJsonSchemaClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: Optional[str],
        model: str,
        temperature: float,
        timeout_seconds: float,
        client: Any | None = None,
        backend_label: str,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self._client = client
        self._backend_label = backend_label

    def invoke_json_schema(
        self,
        *,
        messages: list[dict[str, str]],
        response_model: Type[BaseModel],
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
            "model": self._model,
            "messages": final_messages,
            "temperature": self._temperature,
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
                f"The openai package is required for {self._backend_label}. "
                "Install the linux-runtime extra or add openai to your environment."
            ) from exc

        self._client = OpenAI(
            base_url=self._base_url,
            api_key=self._api_key or "EMPTY",
            timeout=self._timeout_seconds,
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
                raise ValueError(f"LLM response did not contain JSON: {raw_text!r}")
            payload = json.loads(candidate[start : end + 1])

        if not isinstance(payload, dict):
            raise ValueError(f"LLM response must be a JSON object: {payload!r}")
        return payload

    def _strip_code_fence(self, raw_text: str) -> str:
        lines = raw_text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return raw_text


class OpenAICompatiblePlannerClient(OpenAICompatibleJsonSchemaClient):
    def __init__(self, config: AieMasConfig, client: Any | None = None) -> None:
        super().__init__(
            base_url=config.planner_base_url,
            api_key=config.planner_api_key,
            model=config.planner_model,
            temperature=config.planner_temperature,
            timeout_seconds=config.planner_timeout_seconds,
            client=client,
            backend_label="planner_backend='openai_sdk'",
        )


class OpenAICompatibleMicroscopicClient(OpenAICompatibleJsonSchemaClient):
    def __init__(self, config: AieMasConfig, client: Any | None = None) -> None:
        super().__init__(
            base_url=str(config.microscopic_base_url),
            api_key=config.microscopic_api_key,
            model=str(config.microscopic_model),
            temperature=float(config.microscopic_temperature),
            timeout_seconds=float(config.microscopic_timeout_seconds),
            client=client,
            backend_label="microscopic_backend='openai_sdk'",
        )


class OpenAICompatibleMacroClient(OpenAICompatibleJsonSchemaClient):
    def __init__(self, config: AieMasConfig, client: Any | None = None) -> None:
        super().__init__(
            base_url=str(config.macro_base_url),
            api_key=config.macro_api_key,
            model=str(config.macro_model),
            temperature=float(config.macro_temperature),
            timeout_seconds=float(config.macro_timeout_seconds),
            client=client,
            backend_label="macro_backend='openai_sdk'",
        )
