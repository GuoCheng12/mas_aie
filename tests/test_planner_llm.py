from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent, PlannerInitialResponse
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, WorkingMemoryEntry
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
    assert "macro" in result["decision"].agent_task_instructions
    assert "microscopic" in result["decision"].agent_task_instructions
    assert result["decision"].hypothesis_uncertainty_note
    assert result["decision"].capability_assessment
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_openai_initial_hypothesis_pool_is_model_driven(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "hypothesis_pool": [
                {
                  "name": "restriction of intramolecular motion (RIM)-dominated AIE",
                  "confidence": 0.58,
                  "rationale": "Bulky aromatic features make this the leading candidate.",
                  "candidate_strength": "strong"
                },
                {
                  "name": "packing-assisted excimer or aggregate-state emission",
                  "confidence": 0.21,
                  "rationale": "Secondary aggregate-state alternative.",
                  "candidate_strength": "weak"
                }
              ],
              "current_hypothesis": "restriction of intramolecular motion (RIM)-dominated AIE",
              "confidence": 0.58,
              "diagnosis": "Use macro and microscopic first-round evidence collection.",
              "action": "macro_and_microscopic",
              "task_instruction": "Dispatch first-round tasks.",
              "agent_task_instructions": {
                "macro": "Inspect bulky aromatic structure features.",
                "microscopic": "Run first-round S0/S1 proxy collection."
              },
              "hypothesis_uncertainty_note": "RIM leads, but packing remains a live alternative.",
              "capability_assessment": "Current agents can collect bounded internal evidence."
            }
            """,
            """
            {
              "hypothesis_pool": [
                {
                  "name": "ICT-assisted emission with aggregation-enabled rigidification",
                  "confidence": 0.63,
                  "rationale": "The donor-acceptor pattern makes ICT the strongest candidate.",
                  "candidate_strength": "strong"
                },
                {
                  "name": "restriction of intramolecular motion (RIM)-dominated AIE",
                  "confidence": 0.19,
                  "rationale": "Secondary fallback explanation.",
                  "candidate_strength": "weak"
                }
              ],
              "current_hypothesis": "ICT-assisted emission with aggregation-enabled rigidification",
              "confidence": 0.63,
              "diagnosis": "Use macro and microscopic first-round evidence collection.",
              "action": "macro_and_microscopic",
              "task_instruction": "Dispatch first-round tasks.",
              "agent_task_instructions": {
                "macro": "Inspect donor-acceptor and conjugation features.",
                "microscopic": "Run first-round S0/S1 proxy collection with ICT-related uncertainty in mind."
              },
              "hypothesis_uncertainty_note": "ICT leads, but rigidification may still be mixed in.",
              "capability_assessment": "Current agents can collect bounded internal evidence."
            }
            """,
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

    bulky_result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        )
    )
    ict_result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="O=N(=O)c1ccc(N(CC)CC)cc1",
        )
    )

    assert bulky_result["decision"].current_hypothesis == "restriction of intramolecular motion (RIM)-dominated AIE"
    assert ict_result["decision"].current_hypothesis == "ICT-assisted emission with aggregation-enabled rigidification"
    assert (
        bulky_result["decision"].agent_task_instructions["macro"]
        != ict_result["decision"].agent_task_instructions["macro"]
    )


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


def test_openai_planner_diagnosis_prompt_includes_recent_rounds_context(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "diagnosis": "Recent rounds add only modest new evidence, so continue refinement.",
              "action": "microscopic",
              "current_hypothesis": "restriction of intramolecular motion (RIM)-dominated AIE",
              "confidence": 0.55,
              "needs_verifier": false,
              "finalize": false,
              "evidence_summary": "Macro and micro evidence were reviewed.",
              "main_gap": "Microscopic consistency is still incomplete.",
              "conflict_status": "none",
              "information_gain_assessment": "The current round adds some new information.",
              "gap_trend": "The main gap is shrinking.",
              "stagnation_detected": false,
              "hypothesis_uncertainty_note": "The current hypothesis still has residual uncertainty.",
              "capability_assessment": "Current specialized agents can still provide one bounded refinement.",
              "stagnation_assessment": "No stagnation is currently visible.",
              "contraction_reason": ""
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
    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        confidence=0.52,
        macro_reports=[
            {
                "agent_name": "macro",
                "task_received": "macro task",
                "task_understanding": "macro understanding",
                "execution_plan": "macro execution plan",
                "result_summary": "macro result summary",
                "remaining_local_uncertainty": "macro uncertainty",
                "tool_calls": [],
                "raw_results": {},
                "structured_results": {},
                "status": "success",
                "planner_readable_report": "macro planner readable report",
            }
        ],
        working_memory=[
            WorkingMemoryEntry(
                round_id=1,
                current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
                confidence=0.45,
                action_taken="macro, microscopic",
                evidence_summary="Initial internal evidence was collected.",
                diagnosis_summary="The main gap is verifier evidence.",
                main_gap="Verifier evidence is required before a temporary conclusion can be trusted.",
                conflict_status="none",
                next_action="microscopic",
            ),
            WorkingMemoryEntry(
                round_id=2,
                current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
                confidence=0.5,
                action_taken="microscopic",
                evidence_summary="One follow-up micro refinement was run.",
                diagnosis_summary="The same verifier gap remains.",
                main_gap="Verifier evidence is required before a temporary conclusion can be trusted.",
                conflict_status="none",
                next_action="microscopic",
            ),
        ],
    )

    result = planner.plan_diagnosis(state)

    assert result["decision"].action == "microscopic"
    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "recent_rounds_context" in message_payload
    assert "recent_capability_context" in message_payload
    assert '"action_taken": "macro, microscopic"' in message_payload
    assert '"diagnosis_summary": "The same verifier gap remains."' in message_payload
    assert '"task_understanding": "macro understanding"' in message_payload
    assert '"execution_plan": "macro execution plan"' in message_payload
    assert '"repeated_main_gaps"' in message_payload
