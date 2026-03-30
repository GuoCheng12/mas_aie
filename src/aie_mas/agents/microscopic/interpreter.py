from __future__ import annotations

import json
from typing import Any, Optional, Protocol

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.llm.openai_compatible import OpenAICompatibleMicroscopicClient

from .compiler import (
    MicroscopicActionDecision,
    MicroscopicReasoningOutcome,
    MicroscopicReasoningParseError,
    MicroscopicReasoningResponse,
    MicroscopicSemanticContractMode,
    _action_decision_from_execution_plan,
    _extract_tagged_reasoning_sections,
    _parse_legacy_tagged_microscopic_reasoning_response,
    _parse_reasoned_action_response_with_plan,
    _parse_tagged_semantic_contract_response_with_plan,
    _parse_structured_action_decision_response_with_plan,
    _tagged_contract_version,
    compile_reasoning_response_to_execution_plan,
)


class MicroscopicReasoningBackend(Protocol):
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningOutcome:
        ...


class OpenAIMicroscopicReasoningBackend:
    def __init__(
        self,
        config: AieMasConfig,
        client: Optional[OpenAICompatibleMicroscopicClient] = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAICompatibleMicroscopicClient(config)

    def _invoke_reasoned_action_text(self, rendered_prompt: Any) -> str:
        messages = prompt_value_to_messages(rendered_prompt)
        return self._client.invoke_text(messages=messages)

    def _invoke_structured_action_decision_text(self, rendered_prompt: Any) -> str:
        messages = prompt_value_to_messages(rendered_prompt)
        response_schema = MicroscopicActionDecision.model_json_schema()
        messages.append(
            {
                "role": "user",
                "content": (
                    "Return only a valid JSON object that matches this schema.\n"
                    "Schema name: microscopic_action_decision\n"
                    f"JSON schema:\n{json.dumps(response_schema, ensure_ascii=False, indent=2)}"
                ),
            }
        )
        return self._client.invoke_text(messages=messages, response_format={"type": "json_object"})

    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningOutcome:
        contract_errors: list[str] = []
        raw_text = ""
        try:
            raw_text = self._invoke_reasoned_action_text(rendered_prompt)
            action_decision, response, compiled_plan = _parse_reasoned_action_response_with_plan(
                raw_text,
                payload=payload,
                config=self._config,
            )
            return MicroscopicReasoningOutcome(
                action_decision=action_decision,
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode="reasoned_action_text",
                reasoning_contract_mode="reasoned_action_text",
                reasoning_contract_errors=[],
            )
        except Exception as exc:
            contract_errors.append(f"reasoned_action_text: {exc}")

        try:
            action_decision, response, compiled_plan = _parse_structured_action_decision_response_with_plan(
                raw_text,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"structured_action_decision: {exc}")
        else:
            return MicroscopicReasoningOutcome(
                action_decision=action_decision,
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode="structured_action_decision",
                reasoning_contract_mode="structured_action_decision",
                reasoning_contract_errors=list(contract_errors),
            )

        try:
            response, compiled_plan = _parse_tagged_semantic_contract_response_with_plan(raw_text, payload=payload)
        except Exception as exc:
            contract_errors.append(f"semantic_contract: {exc}")
        else:
            sections = _extract_tagged_reasoning_sections(raw_text)
            contract_version = _tagged_contract_version(sections.get("microscopic_semantic_contract", ""))
            contract_mode: MicroscopicSemanticContractMode = (
                "semantic_contract" if contract_version == "2" else "legacy_semantic_contract_fallback"
            )
            return MicroscopicReasoningOutcome(
                action_decision=_action_decision_from_execution_plan(
                    compiled_plan,
                    local_execution_rationale=response.reasoning_summary,
                    unsupported_parts=list(response.execution_plan.unsupported_requests),
                ),
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode=contract_mode,
                reasoning_contract_mode=contract_mode,
                reasoning_contract_errors=list(contract_errors),
            )

        try:
            response = _parse_legacy_tagged_microscopic_reasoning_response(raw_text)
            compiled_plan = compile_reasoning_response_to_execution_plan(
                response,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"legacy_tagged_protocol: {exc}")
            try:
                response = _parse_legacy_tagged_microscopic_reasoning_response(raw_text, strict=False)
                compiled_plan = compile_reasoning_response_to_execution_plan(
                    response,
                    payload=payload,
                    config=self._config,
                )
            except Exception as recovery_exc:
                contract_errors.append(f"legacy_tagged_protocol_recovery: {recovery_exc}")
            else:
                return MicroscopicReasoningOutcome(
                    action_decision=_action_decision_from_execution_plan(
                        compiled_plan,
                        local_execution_rationale=response.reasoning_summary,
                        unsupported_parts=list(response.execution_plan.unsupported_requests),
                    ),
                    reasoning_response=response,
                    compiled_execution_plan=compiled_plan,
                    reasoning_parse_mode="legacy_tagged_protocol_fallback",
                    reasoning_contract_mode="legacy_tagged_protocol_fallback",
                    reasoning_contract_errors=list(contract_errors),
                )
        else:
            return MicroscopicReasoningOutcome(
                action_decision=_action_decision_from_execution_plan(
                    compiled_plan,
                    local_execution_rationale=response.reasoning_summary,
                    unsupported_parts=list(response.execution_plan.unsupported_requests),
                ),
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode="legacy_tagged_protocol_fallback",
                reasoning_contract_mode="legacy_tagged_protocol_fallback",
                reasoning_contract_errors=list(contract_errors),
            )

        try:
            raw_text = self._invoke_structured_action_decision_text(rendered_prompt)
            action_decision, response, compiled_plan = _parse_structured_action_decision_response_with_plan(
                raw_text,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"structured_action_decision_retry: {exc}")
        else:
            return MicroscopicReasoningOutcome(
                action_decision=action_decision,
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode="structured_action_decision",
                reasoning_contract_mode="structured_action_decision",
                reasoning_contract_errors=list(contract_errors),
            )

        try:
            payload_obj = self._client.parse_json_object_text(raw_text)
            response = MicroscopicReasoningResponse.model_validate(payload_obj)
            compiled_plan = compile_reasoning_response_to_execution_plan(
                response,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"legacy_json: {exc}")
            raise MicroscopicReasoningParseError(
                "Microscopic reasoning output was neither a valid semantic contract, valid legacy tagged protocol, nor valid legacy JSON.",
                raw_text=raw_text,
                contract_mode="failed",
                contract_errors=contract_errors,
            ) from exc
        return MicroscopicReasoningOutcome(
            action_decision=_action_decision_from_execution_plan(
                compiled_plan,
                local_execution_rationale=response.reasoning_summary,
                unsupported_parts=list(response.execution_plan.unsupported_requests),
            ),
            reasoning_response=MicroscopicReasoningResponse.model_validate(response.model_dump(mode="json")),
            compiled_execution_plan=compiled_plan,
            reasoning_parse_mode="legacy_json_fallback",
            reasoning_contract_mode="legacy_json_fallback",
            reasoning_contract_errors=list(contract_errors),
        )
