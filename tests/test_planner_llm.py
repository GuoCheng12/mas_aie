from __future__ import annotations

from pathlib import Path

from aie_mas.agents.planner import PlannerAgent, PlannerInitialResponse
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, SharedStructureContext, WorkingMemoryEntry
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


def _build_planner(tmp_path: Path, responses: list[str]) -> tuple[PlannerAgent, _FakeClient]:
    fake_client = _FakeClient(responses)
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
    return planner, fake_client


def _base_hypothesis_pool() -> list[dict[str, object]]:
    return [
        {"name": "ICT", "confidence": 0.74},
        {"name": "TICT", "confidence": 0.18},
        {"name": "ESIPT", "confidence": 0.04},
        {"name": "neutral aromatic", "confidence": 0.03},
        {"name": "unknown", "confidence": 0.01},
    ]


def _base_state(**overrides: object) -> AieMasState:
    payload: dict[str, object] = {
        "user_query": "Assess the likely AIE mechanism for this molecule.",
        "smiles": "C1=CC=CC=C1",
        "current_hypothesis": "ICT",
        "confidence": 0.74,
        "runner_up_hypothesis": "TICT",
        "runner_up_confidence": 0.18,
        "decision_pair": ["ICT", "TICT"],
        "hypothesis_pool": _base_hypothesis_pool(),
        "decision_gate_status": "not_ready",
        "pairwise_task_outcome": "not_run",
        "finalization_mode": "none",
    }
    payload.update(overrides)
    return AieMasState.model_validate(payload)


def _verifier_report_for_pair(pair_key: str, specificity: str = "generic_review") -> dict[str, object]:
    return {
        "agent_name": "verifier",
        "task_received": "verifier task",
        "task_understanding": "verifier understanding",
        "reasoning_summary": "verifier reasoning summary",
        "execution_plan": "verifier execution plan",
        "result_summary": "verifier result summary",
        "remaining_local_uncertainty": "verifier uncertainty",
        "tool_calls": [],
        "raw_results": {},
        "structured_results": {
            "pairwise_verifier_completed_for_pair": pair_key,
            "pairwise_verifier_evidence_specificity": specificity,
        },
        "status": "success",
        "planner_readable_report": "verifier planner readable report",
    }


def test_openai_planner_backend_invokes_chat_completions_with_configured_model(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "hypothesis_pool": [
                {
                  "name": "neutral aromatic",
                  "confidence": 0.61,
                  "rationale": "The model selected a baseline AIE hypothesis."
                },
                {
                  "name": "ICT",
                  "confidence": 0.23,
                  "rationale": "Secondary possibility."
                }
              ],
              "current_hypothesis": "neutral aromatic",
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
    assert result["decision"].current_hypothesis == "neutral aromatic"
    assert "macro" in result["decision"].agent_task_instructions
    assert "microscopic" in result["decision"].agent_task_instructions
    assert result["decision"].hypothesis_uncertainty_note
    assert result["decision"].capability_assessment
    assert result["raw_response"]["action"] == "macro_and_microscopic"
    assert result["raw_response"]["diagnosis"] == "The first round should gather macro and microscopic evidence."
    assert result["normalized_response"]["decision"]["action"] == "macro_and_microscopic"
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    prompt_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "runtime_context" in prompt_payload
    assert "shared_structure_status" in prompt_payload
    assert "shared_structure_context" in prompt_payload
    assert "low-cost" in prompt_payload.lower()


def test_openai_initial_hypothesis_pool_is_model_driven(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "hypothesis_pool": [
                {
                  "name": "neutral aromatic",
                  "confidence": 0.58,
                  "rationale": "Bulky aromatic features make this the leading candidate.",
                  "candidate_strength": "strong"
                },
                {
                  "name": "ICT",
                  "confidence": 0.21,
                  "rationale": "Secondary aggregate-state alternative.",
                  "candidate_strength": "weak"
                }
              ],
              "current_hypothesis": "neutral aromatic",
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
                  "name": "ICT",
                  "confidence": 0.63,
                  "rationale": "The donor-acceptor pattern makes ICT the strongest candidate.",
                  "candidate_strength": "strong"
                },
                {
                  "name": "neutral aromatic",
                  "confidence": 0.19,
                  "rationale": "Secondary fallback explanation.",
                  "candidate_strength": "weak"
                }
              ],
              "current_hypothesis": "ICT",
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

    assert bulky_result["decision"].current_hypothesis == "neutral aromatic"
    assert ict_result["decision"].current_hypothesis == "ICT"
    assert (
        bulky_result["decision"].agent_task_instructions["macro"]
        != ict_result["decision"].agent_task_instructions["macro"]
    )


def test_openai_planner_normalizes_hypothesis_labels_to_fixed_pool(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "hypothesis_pool": [
                {
                  "name": "ict",
                  "confidence": 0.62,
                  "rationale": "Charge-transfer character is the leading label."
                },
                {
                  "name": "aggregate emission",
                  "confidence": 0.18,
                  "rationale": "This invalid label should be dropped."
                },
                {
                  "name": "unknown",
                  "confidence": 0.05,
                  "rationale": "Unknown should not remain when a non-unknown candidate exists."
                }
              ],
              "current_hypothesis": "ict",
              "confidence": 0.62,
              "diagnosis": "Use macro and microscopic first-round evidence collection.",
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

    assert result["decision"].current_hypothesis == "ICT"
    assert [entry.name for entry in result["hypothesis_pool"]] == [
        "ICT",
        "unknown",
        "TICT",
        "ESIPT",
        "neutral aromatic",
    ]
    assert round(sum(float(entry.confidence or 0.0) for entry in result["hypothesis_pool"]), 6) == 1.0


def test_openai_client_extracts_json_from_code_fence(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """```json
            {
              "hypothesis_pool": [],
              "current_hypothesis": "ICT",
              "confidence": 0.5,
              "diagnosis": "placeholder diagnosis",
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

    assert parsed.current_hypothesis == "ICT"


def test_openai_planner_diagnosis_prompt_includes_recent_rounds_context(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "diagnosis": "Recent rounds add only modest new evidence, so continue refinement.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
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
        current_hypothesis="ICT",
        confidence=0.52,
        shared_structure_status="ready",
        shared_structure_context=SharedStructureContext(
            input_smiles="C1=CC=CC=C1",
            canonical_smiles="c1ccccc1",
            charge=0,
            multiplicity=1,
            atom_count=12,
            conformer_count=3,
            selected_conformer_id=1,
            prepared_xyz_path=str(tmp_path / "prepared.xyz"),
            prepared_sdf_path=str(tmp_path / "prepared.sdf"),
            summary_path=str(tmp_path / "summary.json"),
            rotatable_bond_count=2,
            aromatic_ring_count=2,
            ring_system_count=1,
            hetero_atom_count=0,
            branch_point_count=2,
            donor_acceptor_partition_proxy=0.0,
            planarity_proxy=0.8,
            compactness_proxy=0.4,
            torsion_candidate_count=2,
            principal_span_proxy=7.2,
            conformer_dispersion_proxy=0.5,
        ),
        macro_reports=[
            {
                "agent_name": "macro",
                "task_received": "macro task",
                "task_understanding": "macro understanding",
                "reasoning_summary": "macro reasoning summary",
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
                current_hypothesis="ICT",
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
                current_hypothesis="ICT",
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
    assert result["raw_response"]["action"] == "microscopic"
    assert result["normalized_response"]["decision"]["action"] == "microscopic"
    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "shared_structure_status" in message_payload
    assert "shared_structure_context" in message_payload
    assert "recent_rounds_context" in message_payload
    assert "recent_capability_context" in message_payload
    assert '"action_taken": "macro, microscopic"' in message_payload
    assert '"diagnosis_summary": "The same verifier gap remains."' in message_payload
    assert '"task_understanding": "macro understanding"' in message_payload
    assert '"reasoning_summary": "macro reasoning summary"' in message_payload
    assert '"execution_plan": "macro execution plan"' in message_payload
    assert '"repeated_main_gaps"' in message_payload


def test_workflow_stores_planner_raw_and_normalized_responses(tmp_path: Path) -> None:
    from aie_mas.graph.builder import AieMasWorkflow
    from aie_mas.graph.state import PlannerDecision

    config = AieMasConfig(project_root=tmp_path, execution_profile="local-dev", prompts_dir=PROMPTS_DIR)
    workflow = AieMasWorkflow(config)
    decision = PlannerDecision(
        diagnosis="placeholder diagnosis",
        action="macro_and_microscopic",
        current_hypothesis="placeholder hypothesis",
        confidence=0.55,
        planned_agents=["macro", "microscopic"],
        task_instruction="dispatch",
        agent_task_instructions={"macro": "macro task", "microscopic": "micro task"},
    )
    workflow.planner.plan_initial = lambda state: {  # type: ignore[method-assign]
        "hypothesis_pool": [],
        "decision": decision,
        "raw_response": {"action": "macro_and_microscopic", "diagnosis": "raw diagnosis"},
        "normalized_response": {"decision": decision.model_dump(mode="json")},
    }

    state = AieMasState(
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
    )

    updated = workflow.planner_initial(state)

    assert updated.last_planner_raw_response == {
        "action": "macro_and_microscopic",
        "diagnosis": "raw diagnosis",
    }
    assert updated.last_planner_normalized_response == {
        "decision": decision.model_dump(mode="json"),
    }
    assert updated.planner_response_history[-1]["node"] == "planner_initial"


def test_planner_diagnosis_requires_internal_pairwise_task_before_verifier(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.74},
                {"name": "TICT", "confidence": 0.18},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "neutral aromatic", "confidence": 0.03},
                {"name": "unknown", "confidence": 0.01}
              ],
              "diagnosis": "ICT remains top1 over TICT and the case is nearing closure.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.74,
              "evidence_summary": "Latest internal evidence favors ICT.",
              "main_gap": "Need one internal discriminator between ICT and TICT.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_diagnosis(_base_state())

    assert result["decision"].action == "microscopic"
    assert result["decision"].decision_gate_status == "needs_pairwise_discriminative_task"
    assert result["decision"].pairwise_task_agent == "microscopic"
    assert result["decision"].finalize is False
    assert "distinguish 'ICT' from 'TICT'" in (result["decision"].task_instruction or "")


def test_planner_diagnosis_requests_verifier_after_pairwise_task_completion(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.76},
                {"name": "TICT", "confidence": 0.14},
                {"name": "ESIPT", "confidence": 0.05},
                {"name": "neutral aromatic", "confidence": 0.03},
                {"name": "unknown", "confidence": 0.02}
              ],
              "diagnosis": "The internal pairwise task was completed and ICT still leads over TICT.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.76,
              "evidence_summary": "A bounded internal discriminator has already been collected.",
              "main_gap": "Need high-confidence external context before closure.",
              "conflict_status": "none",
              "pairwise_task_completed_for_pair": "ICT__vs__TICT",
              "pairwise_task_outcome": "decisive",
              "pairwise_task_rationale": "Microscopic evidence directly probed the key discriminator."
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="ICT__vs__TICT",
            pairwise_task_outcome="decisive",
            pairwise_task_rationale="Microscopic evidence directly probed the key discriminator.",
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].decision_gate_status == "needs_high_confidence_verifier"
    assert result["decision"].needs_verifier is True
    assert "high-confidence external verification" in (result["decision"].task_instruction or "")


def test_planner_reweight_allows_best_available_finalize_after_inconclusive_pairwise_task(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.61},
                {"name": "TICT", "confidence": 0.29},
                {"name": "ESIPT", "confidence": 0.05},
                {"name": "neutral aromatic", "confidence": 0.03},
                {"name": "unknown", "confidence": 0.02}
              ],
              "diagnosis": "The internal discriminator stayed inconclusive, but ICT remains first after verifier supplementation.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.61,
              "finalize": true,
              "evidence_summary": "Internal pairwise evidence was inconclusive and verifier added external context.",
              "main_gap": "No decisive internal discriminator separated ICT from TICT.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="ICT__vs__TICT",
            pairwise_task_outcome="inconclusive",
            pairwise_task_rationale="The bounded microscopic discriminator stayed ambiguous.",
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT")],
        )
    )

    assert result["decision"].finalize is True
    assert result["decision"].finalization_mode == "best_available"
    assert result["decision"].decision_gate_status == "ready_to_finalize_best_available"
    assert "Best-available closure" in (result["decision"].final_hypothesis_rationale or "")


def test_planner_reweight_blocks_finalize_when_pairwise_task_failed(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.68},
                {"name": "TICT", "confidence": 0.20},
                {"name": "ESIPT", "confidence": 0.05},
                {"name": "neutral aromatic", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.03}
              ],
              "diagnosis": "The internal pairwise task failed, so the case cannot close safely.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.68,
              "finalize": true,
              "evidence_summary": "The requested internal discriminator failed before completion.",
              "main_gap": "The key ICT-vs-TICT discriminator was never completed.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="ICT__vs__TICT",
            pairwise_task_outcome="failed",
            pairwise_task_rationale="The bounded microscopic discriminator failed locally.",
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT")],
        )
    )

    assert result["decision"].finalize is False
    assert result["decision"].finalization_mode == "none"
    assert result["decision"].decision_gate_status == "blocked_by_missing_decisive_evidence"
