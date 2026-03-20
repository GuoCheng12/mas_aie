from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent, PlannerInitialResponse
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.utils.prompts import PromptRepository


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


class _FakeChatCompletions:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeCompletion(self._responses.pop(0))


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = type("FakeChat", (), {"completions": _FakeChatCompletions(responses)})()


def test_openai_planner_backend_invokes_chat_completions_with_configured_model(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "hypothesis_pool": [
                {
                  "name": "restriction of intramolecular motion (RIM)-dominated AIE",
                  "confidence": 0.61,
                  "rationale": "The model selected a baseline AIE hypothesis."
                },
                {
                  "name": "ICT-assisted emission with aggregation-enabled rigidification",
                  "confidence": 0.23,
                  "rationale": "Secondary possibility."
                }
              ],
              "current_hypothesis": "restriction of intramolecular motion (RIM)-dominated AIE",
              "confidence": 0.61,
              "diagnosis": "The first round should gather macro and microscopic evidence.",
              "action": "macro_and_microscopic"
            }
            """
        ]
    )
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        planner_backend="openai_sdk",
        planner_base_url="http://34.13.73.248:3888/v1",
        planner_model="gpt-4.1-mini",
        planner_api_key="test-key",
        prompts_dir=PROMPTS_DIR,
    )
    planner = PlannerAgent(
        prompts=PromptRepository(PROMPTS_DIR),
        config=config,
        llm_client=OpenAICompatiblePlannerClient(config, client=fake_client),
    )

    result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="C1=CC=CC=C1",
        )
    )

    assert result["decision"].action == "macro_and_microscopic"
    assert result["decision"].current_hypothesis == "restriction of intramolecular motion (RIM)-dominated AIE"
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_openai_client_extracts_json_from_code_fence(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """```json
            {
              "hypothesis_pool": [],
              "current_hypothesis": "mock",
              "confidence": 0.5,
              "diagnosis": "mock",
              "action": "macro_and_microscopic"
            }
            ```"""
        ]
    )
    config = AieMasConfig(project_root=tmp_path, prompts_dir=PROMPTS_DIR)
    client = OpenAICompatiblePlannerClient(config, client=fake_client)

    parsed = client.invoke_json_schema(
        messages=[{"role": "user", "content": "Return JSON."}],
        response_model=PlannerInitialResponse,
        schema_name="planner_initial_response",
    )

    assert parsed.current_hypothesis == "mock"
