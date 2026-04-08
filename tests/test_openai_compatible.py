from __future__ import annotations

from pathlib import Path

import pytest

from aie_mas.agents.planner import PlannerInitialResponse
from aie_mas.config import AieMasConfig
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts"


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeTransientError(Exception):
    status_code = 503


class _FakeResponseFormatError(Exception):
    status_code = 400


class _FakeBadRequestError(Exception):
    status_code = 400


class _FakeChatCompletions:
    def __init__(self, scripted_outcomes: list[object]) -> None:
        self._scripted_outcomes = list(scripted_outcomes)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._scripted_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _FakeCompletion(str(outcome))


class _FakeClient:
    def __init__(self, scripted_outcomes: list[object]) -> None:
        self.chat = type(
            "FakeChat",
            (),
            {"completions": _FakeChatCompletions(scripted_outcomes)},
        )()


def _planner_client(tmp_path: Path, scripted_outcomes: list[object]) -> tuple[OpenAICompatiblePlannerClient, _FakeClient]:
    fake_client = _FakeClient(scripted_outcomes)
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        planner_backend="openai_sdk",
        planner_base_url="http://34.13.73.248:3888/v1",
        planner_model="gpt-4.1-mini",
        planner_api_key="test-key",
        prompts_dir=PROMPTS_DIR,
    )
    return OpenAICompatiblePlannerClient(config, client=fake_client), fake_client


def _minimal_planner_initial_json() -> str:
    return """
    {
      "hypothesis_pool": [],
      "current_hypothesis": "ICT",
      "confidence": 0.5,
      "diagnosis": "placeholder diagnosis",
      "action": "macro_and_microscopic"
    }
    """


def test_openai_client_retries_transient_upstream_error_without_dropping_response_format(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("aie_mas.llm.openai_compatible.time.sleep", lambda _: None)
    client, fake_client = _planner_client(
        tmp_path,
        [
            _FakeTransientError(
                "upstream connect error or disconnect/reset before headers. reset reason: connection termination"
            ),
            _minimal_planner_initial_json(),
        ],
    )

    parsed = client.invoke_json_schema(
        messages=[{"role": "user", "content": "Return JSON."}],
        response_model=PlannerInitialResponse,
        schema_name="planner_initial_response",
    )

    assert parsed.current_hypothesis == "ICT"
    assert len(fake_client.chat.completions.calls) == 2
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    assert fake_client.chat.completions.calls[1]["response_format"] == {"type": "json_object"}


def test_openai_client_falls_back_without_response_format_only_for_compatibility_error(
    tmp_path: Path,
) -> None:
    client, fake_client = _planner_client(
        tmp_path,
        [
            _FakeResponseFormatError("Unsupported parameter: response_format"),
            _minimal_planner_initial_json(),
        ],
    )

    parsed = client.invoke_json_schema(
        messages=[{"role": "user", "content": "Return JSON."}],
        response_model=PlannerInitialResponse,
        schema_name="planner_initial_response",
    )

    assert parsed.current_hypothesis == "ICT"
    assert len(fake_client.chat.completions.calls) == 2
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in fake_client.chat.completions.calls[1]


def test_openai_client_does_not_retry_non_transient_bad_request(tmp_path: Path) -> None:
    client, fake_client = _planner_client(
        tmp_path,
        [
            _FakeBadRequestError("BadRequestError: invalid schema payload"),
        ],
    )

    with pytest.raises(_FakeBadRequestError):
        client.invoke_text(
            messages=[{"role": "user", "content": "Return JSON."}],
            response_format={"type": "json_object"},
        )

    assert len(fake_client.chat.completions.calls) == 1
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
