from __future__ import annotations

import json
import time
from typing import Any, Optional, Type

from pydantic import BaseModel

from aie_mas.config import AieMasConfig


class OpenAICompatibleJsonSchemaClient:
    _TRANSIENT_RETRY_DELAYS_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
    _TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({408, 429})
    _TRANSIENT_ERROR_MARKERS: tuple[str, ...] = (
        "upstream connect error",
        "disconnect/reset before headers",
        "connection termination",
        "connection reset",
        "remote protocol error",
        "gateway timeout",
        "bad gateway",
        "service unavailable",
        "temporarily unavailable",
        "timed out",
        "timeout",
    )
    _RESPONSE_FORMAT_COMPATIBILITY_MARKERS: tuple[str, ...] = (
        "response_format",
        "json_object",
        "unsupported parameter",
        "does not support",
        "not support",
        "invalid parameter",
        "extra inputs are not permitted",
        "unexpected field",
    )

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
        response_schema = response_model.model_json_schema()
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
        raw_text = self.invoke_text(messages=final_messages, response_format={"type": "json_object"})
        payload = self._extract_json_object(raw_text)
        return response_model.model_validate(payload)

    def invoke_text(
        self,
        *,
        messages: list[dict[str, str]],
        response_format: Optional[dict[str, str]] = None,
    ) -> str:
        client = self._get_client()
        request_kwargs = {
            "model": self._model,
            "messages": list(messages),
            "temperature": self._temperature,
        }
        if response_format is not None:
            request_kwargs["response_format"] = response_format

        completion = self._create_completion(client, request_kwargs)

        return self._extract_content(completion)

    def parse_json_object_text(self, raw_text: str) -> dict[str, Any]:
        return self._extract_json_object(raw_text)

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

    def _create_completion(self, client: Any, request_kwargs: dict[str, Any]) -> Any:
        try:
            return self._create_completion_with_transient_retry(client, request_kwargs)
        except Exception as exc:
            if self._should_retry_without_response_format(exc, request_kwargs):
                fallback_kwargs = dict(request_kwargs)
                fallback_kwargs.pop("response_format", None)
                return self._create_completion_with_transient_retry(client, fallback_kwargs)
            raise

    def _create_completion_with_transient_retry(self, client: Any, request_kwargs: dict[str, Any]) -> Any:
        retry_delays = (0.0, *self._TRANSIENT_RETRY_DELAYS_SECONDS)
        last_exc: Exception | None = None
        for attempt_index, delay_seconds in enumerate(retry_delays):
            if attempt_index > 0:
                self._sleep_for_retry(delay_seconds)
            try:
                return client.chat.completions.create(**request_kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt_index >= len(retry_delays) - 1 or not self._is_transient_request_error(exc):
                    raise
        assert last_exc is not None
        raise last_exc

    def _sleep_for_retry(self, delay_seconds: float) -> None:
        time.sleep(delay_seconds)

    def _should_retry_without_response_format(
        self,
        exc: Exception,
        request_kwargs: dict[str, Any],
    ) -> bool:
        if "response_format" not in request_kwargs:
            return False
        status_code = self._extract_status_code(exc)
        if status_code is not None and status_code >= 500:
            return False
        message = str(exc).lower()
        return any(marker in message for marker in self._RESPONSE_FORMAT_COMPATIBILITY_MARKERS)

    def _is_transient_request_error(self, exc: Exception) -> bool:
        status_code = self._extract_status_code(exc)
        if status_code is not None:
            if status_code >= 500 or status_code in self._TRANSIENT_STATUS_CODES:
                return True
            if 400 <= status_code < 500:
                return False

        class_name = exc.__class__.__name__.lower()
        if class_name in {"apiconnectionerror", "apitimeouterror", "internalservererror"}:
            return True

        message = str(exc).lower()
        return any(marker in message for marker in self._TRANSIENT_ERROR_MARKERS)

    def _extract_status_code(self, exc: Exception) -> int | None:
        for candidate in (
            getattr(exc, "status_code", None),
            getattr(exc, "status", None),
            getattr(getattr(exc, "response", None), "status_code", None),
            getattr(getattr(exc, "response", None), "status", None),
        ):
            if isinstance(candidate, int):
                return candidate
        return None

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


class OpenAICompatibleVerifierClient(OpenAICompatibleJsonSchemaClient):
    def __init__(self, config: AieMasConfig, client: Any | None = None) -> None:
        super().__init__(
            base_url=str(config.verifier_base_url),
            api_key=config.verifier_api_key,
            model=str(config.verifier_model),
            temperature=float(config.verifier_temperature),
            timeout_seconds=float(config.verifier_timeout_seconds),
            client=client,
            backend_label="verifier_backend='openai_sdk'",
        )
