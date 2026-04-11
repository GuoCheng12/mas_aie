from __future__ import annotations

import json
from pathlib import Path

from aie_mas.agents import planner as planner_module
from aie_mas.agents.planner import (
    PlannerAgent,
    PlannerInitialResponse,
    _mentioned_microscopic_capabilities,
    _single_action_microscopic_task_instruction,
)
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AieMasState,
    AgentReport,
    HypothesisScreeningRecord,
    PlannerDecision,
    SharedStructureContext,
    WorkingMemoryAgentEntry,
    WorkingMemoryEntry,
)
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.memory.working import WorkingMemoryManager
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


def _round_response_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "hypothesis_pool": _base_hypothesis_pool(),
        "reasoning_phase": "portfolio_screening",
        "agent_framing_mode": "portfolio_neutral",
        "portfolio_screening_complete": False,
        "coverage_debt_hypotheses": ["ESIPT"],
        "credible_alternative_hypotheses": ["TICT", "ESIPT"],
        "hypothesis_screening_ledger": [
            {
                "hypothesis": "ESIPT",
                "screening_status": "untested",
                "screening_priority": "high",
                "evidence_families_covered": [],
                "screening_note": "Still needs a direct screen.",
            }
        ],
        "portfolio_screening_summary": "ESIPT remains a still-credible untested alternative.",
        "screening_focus_hypotheses": ["ESIPT"],
        "screening_focus_summary": "Use one bounded direct screen to reduce ESIPT coverage debt.",
        "diagnosis": "Top1 remains ICT while ESIPT still has unresolved screening debt.",
        "action": "microscopic",
        "current_hypothesis": "ICT",
        "confidence": 0.74,
        "needs_verifier": False,
        "finalize": False,
        "task_instruction": "Use one bounded direct microscopic screen.",
        "agent_task_instructions": {"microscopic": "Use one bounded direct microscopic screen."},
        "evidence_summary": "Internal evidence remains incomplete.",
        "main_gap": "Need one more direct screen.",
        "conflict_status": "none",
        "hypothesis_uncertainty_note": "Top1 is provisional.",
        "final_hypothesis_rationale": "",
        "capability_assessment": "Current capability remains bounded.",
        "stagnation_assessment": "No stagnation is present.",
        "contraction_reason": "Do not collapse to pairwise before screening debt clears.",
        "information_gain_assessment": "One more direct screen is still required.",
        "gap_trend": "open",
        "stagnation_detected": False,
        "capability_lesson_candidates": [],
        "hypothesis_reweight_explanation": {
            "ICT": "Current lead from existing evidence.",
            "TICT": "Still plausible runner-up.",
            "ESIPT": "Still credible and not directly screened.",
            "neutral aromatic": "Weak fallback.",
            "unknown": "Residual uncertainty.",
        },
        "decision_gate_status": "needs_portfolio_screening",
        "verifier_supplement_target_pair": "",
        "verifier_supplement_status": "missing",
        "verifier_information_gain": "none",
        "verifier_evidence_relation": "no_new_info",
        "verifier_supplement_summary": "",
        "closure_justification_target_pair": "",
        "closure_justification_status": "missing",
        "closure_justification_evidence_source": "",
        "closure_justification_basis": "",
        "closure_justification_summary": "",
        "pairwise_task_agent": "",
        "pairwise_task_completed_for_pair": "",
        "pairwise_task_outcome": "not_run",
        "pairwise_task_rationale": "",
        "pairwise_resolution_mode": "",
        "pairwise_resolution_evidence_sources": [],
        "pairwise_resolution_summary": "",
        "finalization_mode": "none",
    }
    payload.update(overrides)
    return json.dumps(payload)


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
            "verifier_target_pair": pair_key,
            "verifier_supplement_status": "sufficient",
            "verifier_information_gain": "high" if specificity in {"close_family", "exact_compound"} else "medium",
            "verifier_evidence_relation": "mixed",
            "verifier_supplement_summary": "Verifier returned source-backed external supplement.",
            "pairwise_verifier_completed_for_pair": pair_key,
            "pairwise_verifier_evidence_specificity": specificity,
            "status": "success",
        },
        "status": "success",
        "planner_readable_report": "verifier planner readable report",
    }


def test_mentioned_microscopic_capabilities_includes_new_targeted_interfaces() -> None:
    instruction = (
        "First try run_targeted_charge_analysis on the current torsion bundle, then if needed "
        "run_targeted_density_population_analysis on the same bundle, followed by "
        "run_targeted_transition_dipole_analysis and run_ris_state_characterization."
    )

    assert _mentioned_microscopic_capabilities(instruction) == [
        "run_targeted_charge_analysis",
        "run_targeted_density_population_analysis",
        "run_targeted_transition_dipole_analysis",
        "run_ris_state_characterization",
    ]


def test_mentioned_microscopic_capabilities_includes_orbital_interfaces() -> None:
    instruction = (
        "Try run_targeted_localized_orbital_analysis first, then run_targeted_natural_orbital_analysis "
        "if the first route fails."
    )

    assert _mentioned_microscopic_capabilities(instruction) == [
        "run_targeted_localized_orbital_analysis",
        "run_targeted_natural_orbital_analysis",
    ]


def test_mentioned_microscopic_capabilities_includes_approx_delta_dipole_interface() -> None:
    instruction = (
        "Use run_targeted_approx_delta_dipole_analysis on the torsion bundle and return approximate dipole-change "
        "proxy observables."
    )

    assert _mentioned_microscopic_capabilities(instruction) == [
        "run_targeted_approx_delta_dipole_analysis",
    ]


def test_mentioned_microscopic_capabilities_includes_member_listing_and_geometry_extraction() -> None:
    instruction = (
        "First use list_artifact_bundle_members on round_08_run_targeted_localized_orbital_analysis_bundle, "
        "then if needed run extract_geometry_descriptors_from_bundle on the same reusable bundle."
    )

    assert _mentioned_microscopic_capabilities(instruction) == [
        "list_artifact_bundle_members",
        "extract_geometry_descriptors_from_bundle",
    ]


def test_single_action_microscopic_task_instruction_for_supported_targeted_interface_is_neutral() -> None:
    instruction = _single_action_microscopic_task_instruction(
        capability_name="run_targeted_density_population_analysis",
        current_hypothesis="ICT",
        main_gap="Need one more LE-vs-CT discriminator.",
        original_task_instruction=(
            "Use run_targeted_density_population_analysis for bundle_id=`round_05_torsion_snapshots` "
            "and return density/population observables."
        ),
    )

    assert instruction.startswith(
        "Execute ONLY `run_targeted_density_population_analysis` for bundle_id=`round_05_torsion_snapshots`"
    )
    assert "density/population observables only" in instruction
    assert "ESIPT" not in instruction
    assert "TICT" not in instruction


def test_single_action_microscopic_task_instruction_for_approx_delta_dipole_interface_is_neutral() -> None:
    instruction = _single_action_microscopic_task_instruction(
        capability_name="run_targeted_approx_delta_dipole_analysis",
        current_hypothesis="ICT",
        main_gap="Need one more approximate dipole-change proxy.",
        original_task_instruction=(
            "Use run_targeted_approx_delta_dipole_analysis for bundle_id=`round_05_torsion_snapshots` "
            "and return approximate per-atom-charge-derived dipole proxy observables."
        ),
    )

    assert instruction.startswith(
        "Execute ONLY `run_targeted_approx_delta_dipole_analysis` for bundle_id=`round_05_torsion_snapshots`"
    )
    assert "approximate per-atom-charge-derived dipole proxy observables only" in instruction


def test_single_action_microscopic_task_instruction_for_phase2_targeted_interfaces_is_neutral() -> None:
    transition_instruction = _single_action_microscopic_task_instruction(
        capability_name="run_targeted_transition_dipole_analysis",
        current_hypothesis="ICT",
        main_gap="Need one more dark-state discriminator.",
        original_task_instruction=(
            "Use run_targeted_transition_dipole_analysis for bundle_id=`round_07_torsion_snapshots` "
            "and return transition-dipole observables."
        ),
    )
    ris_instruction = _single_action_microscopic_task_instruction(
        capability_name="run_ris_state_characterization",
        current_hypothesis="ICT",
        main_gap="Need one more state-character discriminator.",
        original_task_instruction=(
            "Use run_ris_state_characterization for bundle_id=`round_07_torsion_snapshots` "
            "and return RIS state-character observables."
        ),
    )

    assert transition_instruction.startswith(
        "Execute ONLY `run_targeted_transition_dipole_analysis` for bundle_id=`round_07_torsion_snapshots`"
    )
    assert "transition-dipole observables only" in transition_instruction
    assert "ESIPT" not in transition_instruction
    assert "TICT" not in transition_instruction

    assert ris_instruction.startswith(
        "Execute ONLY `run_ris_state_characterization` for bundle_id=`round_07_torsion_snapshots`"
    )
    assert "raw state-character observables only" in ris_instruction
    assert "ESIPT" not in ris_instruction
    assert "TICT" not in ris_instruction


def test_single_action_microscopic_task_instruction_for_member_listing_is_neutral() -> None:
    instruction = _single_action_microscopic_task_instruction(
        capability_name="list_artifact_bundle_members",
        current_hypothesis="ICT",
        main_gap="Need to inspect exact follow-up members before raw inspection.",
        original_task_instruction=(
            "Use list_artifact_bundle_members for bundle_id=`round_08_run_targeted_localized_orbital_analysis_bundle` "
            "and return stable member ids."
        ),
    )

    assert instruction.startswith(
        "Execute ONLY `list_artifact_bundle_members` for bundle_id=`round_08_run_targeted_localized_orbital_analysis_bundle`"
    )
    assert "stable member ids" in instruction
    assert "ESIPT" not in instruction
    assert "TICT" not in instruction


def test_working_memory_backfills_task_instruction_and_action_labels() -> None:
    manager = WorkingMemoryManager()
    state = _base_state()
    state.round_idx = 2
    state.latest_evidence_summary = "Microscopic follow-up completed."
    state.latest_main_gap = "Need raw inspection of one follow-up bundle member."
    state.latest_conflict_status = "none"
    state.last_planner_decision = PlannerDecision(
        diagnosis="Inspect the follow-up bundle members directly.",
        action="microscopic",
        current_hypothesis="ICT",
        confidence=0.72,
        planned_agents=["microscopic"],
        task_instruction=None,
        agent_task_instructions={},
    )
    state.active_round_reports = [
        AgentReport(
            agent_name="microscopic",
            task_received="Inspect a targeted follow-up bundle.",
            task_understanding="Inspect raw artifacts for one exact member.",
            execution_plan="Discovery-only member listing then bounded raw inspection.",
            result_summary="Listed stable member ids and inspected the requested member.",
            remaining_local_uncertainty="Need one more CT-localization discriminator.",
            tool_calls=[],
            raw_results={},
            structured_results={"executed_capability": "list_artifact_bundle_members"},
            planner_readable_report="Stable member ids were returned for the reusable follow-up bundle.",
            status="success",
        )
    ]

    manager.append_round_summary(state)

    entry = state.working_memory[-1]
    assert entry.planner_task_instruction == "microscopic"
    assert entry.planned_action_label == "microscopic"
    assert entry.executed_action_labels == ["list_artifact_bundle_members"]
    assert entry.executed_evidence_families == []
    assert state.planned_action_label == "microscopic"
    assert state.executed_action_labels == ["list_artifact_bundle_members"]


def _microscopic_registry_blocked_report() -> dict[str, object]:
    return {
        "agent_name": "microscopic",
        "task_received": "microscopic task",
        "task_understanding": "microscopic understanding",
        "reasoning_summary": "microscopic reasoning summary",
        "execution_plan": "microscopic execution plan",
        "result_summary": "microscopic result summary",
        "remaining_local_uncertainty": "microscopic uncertainty",
        "tool_calls": [],
        "raw_results": {},
        "structured_results": {
            "registry_infeasible_for_verifier_handshake": True,
            "registry_infeasible_reason": "required_registry_observables_unavailable",
            "completion_reason_code": "partial_observable_only",
            "missing_deliverables": ["CT/localization proxy"],
            "route_summary": {"ct_proxy_availability": "not_available"},
        },
        "status": "success",
        "planner_readable_report": "microscopic planner readable report",
    }


def _microscopic_structure_blocked_report(code: str = "embedding_failed") -> dict[str, object]:
    return {
        "agent_name": "microscopic",
        "task_received": "microscopic task",
        "task_understanding": "microscopic understanding",
        "reasoning_summary": "microscopic reasoning summary",
        "execution_plan": "microscopic execution plan",
        "result_summary": "structure preparation failed",
        "remaining_local_uncertainty": "microscopic uncertainty",
        "tool_calls": [],
        "raw_results": {
            "structure_prep_error": {
                "code": code,
                "message": "RDKit failed to embed any 3D conformer for the current molecule.",
            }
        },
        "structured_results": {
            "completion_reason_code": "precondition_missing",
            "structure_prep_error": {
                "code": code,
                "message": "RDKit failed to embed any 3D conformer for the current molecule.",
            },
        },
        "status": "failed",
        "planner_readable_report": "microscopic planner readable report",
    }


def _working_memory_entry_with_agent_uncertainty(
    *,
    round_id: int,
    action_taken: str,
    uncertainty: str,
    current_hypothesis: str = "ICT",
    confidence: float = 0.6,
    main_gap: str = "Need one more ICT-vs-TICT discriminator.",
) -> WorkingMemoryEntry:
    agent_name = "verifier" if action_taken == "verifier" else "microscopic"
    return WorkingMemoryEntry(
        round_id=round_id,
        current_hypothesis=current_hypothesis,
        confidence=confidence,
        action_taken=action_taken,
        evidence_summary="Existing evidence summary.",
        diagnosis_summary="Existing diagnosis summary.",
        main_gap=main_gap,
        conflict_status="none",
        next_action=action_taken,
        agent_reports=[
            WorkingMemoryAgentEntry(
                agent_name=agent_name,  # type: ignore[arg-type]
                task_received=f"{agent_name} task",
                task_understanding=f"{agent_name} understanding",
                execution_plan=f"{agent_name} execution plan",
                result_summary=f"{agent_name} result summary",
                remaining_local_uncertainty=uncertainty,
            )
        ],
    )


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
    assert "macro_capability_registry" in prompt_payload
    assert "screen_intramolecular_hbond_preorganization" in prompt_payload
    assert "current_round_index" in prompt_payload
    assert "max_rounds" in prompt_payload
    assert "shared_structure_status" in prompt_payload
    assert "shared_structure_context" not in prompt_payload
    assert "molecule_identity_context" not in prompt_payload
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
    assert "current_round_index" in message_payload
    assert "max_rounds" in message_payload
    assert "rounds_remaining_including_current" in message_payload
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


def test_planner_diagnosis_redirects_finalize_to_verifier_when_supplement_is_missing(tmp_path: Path) -> None:
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

    assert result["decision"].action == "verifier"
    assert result["decision"].decision_gate_status == "needs_high_confidence_verifier"
    assert result["decision"].verifier_supplement_status == "missing"
    assert result["decision"].finalize is False
    assert "high-confidence external verification" in (result["decision"].task_instruction or "")


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
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="sufficient",
            pairwise_task_rationale="Microscopic evidence directly probed the key discriminator.",
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].decision_gate_status == "needs_high_confidence_verifier"
    assert result["decision"].needs_verifier is True
    assert result["decision"].closure_justification_status == "sufficient"
    assert result["decision"].pairwise_task_outcome == "dedicated_pairwise_task_completed"
    assert "high-confidence external verification" in (result["decision"].task_instruction or "")


def test_planner_diagnosis_preserves_verifier_when_microscopic_is_registry_blocked(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.76},
                {"name": "neutral aromatic", "confidence": 0.16},
                {"name": "TICT", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.02},
                {"name": "unknown", "confidence": 0.02}
              ],
              "diagnosis": "Internal evidence is saturated and the remaining gap now needs verifier supplementation.",
              "action": "verifier",
              "current_hypothesis": "ICT",
              "confidence": 0.76,
              "needs_verifier": true,
              "evidence_summary": "The latest microscopic task completed but the required CT/localization observable was unavailable internally.",
              "main_gap": "Need high-confidence external context before closure.",
              "conflict_status": "none",
              "pairwise_task_completed_for_pair": "ICT_vs_neutral aromatic:not_completed",
              "pairwise_task_outcome": "not_run"
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            runner_up_hypothesis="neutral aromatic",
            runner_up_confidence=0.16,
            decision_pair=["ICT", "neutral aromatic"],
            hypothesis_pool=[
                {"name": "ICT", "confidence": 0.76},
                {"name": "neutral aromatic", "confidence": 0.16},
                {"name": "TICT", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.02},
                {"name": "unknown", "confidence": 0.02},
            ],
            microscopic_reports=[_microscopic_registry_blocked_report()],
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].decision_gate_status == "needs_high_confidence_verifier"
    assert result["decision"].needs_verifier is True


def test_planner_diagnosis_normalizes_request_verifier_supplement_alias(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "unknown", "confidence": 0.50},
                {"name": "neutral aromatic", "confidence": 0.45},
                {"name": "TICT", "confidence": 0.03},
                {"name": "ICT", "confidence": 0.015},
                {"name": "ESIPT", "confidence": 0.005}
              ],
              "diagnosis": "Internal discriminators are blocked and the next step must be verifier supplementation.",
              "action": "request_verifier_supplement",
              "current_hypothesis": "unknown",
              "confidence": 0.50,
              "needs_verifier": true,
              "task_instruction": "Verifier: Resolve exact identity and photophysics for the current pairwise gap.",
              "agent_task_instructions": {
                "verifier": "Resolve exact identity and photophysics for the current pairwise gap."
              },
              "evidence_summary": "Verifier evidence remains the highest-leverage discriminator.",
              "main_gap": "Need compound-specific photophysics to separate unknown from neutral aromatic.",
              "conflict_status": "tool_and_data_integrity_bottleneck"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            current_hypothesis="unknown",
            confidence=0.50,
            runner_up_hypothesis="neutral aromatic",
            runner_up_confidence=0.45,
            decision_pair=["unknown", "neutral aromatic"],
            hypothesis_pool=[
                {"name": "unknown", "confidence": 0.50},
                {"name": "neutral aromatic", "confidence": 0.45},
                {"name": "TICT", "confidence": 0.03},
                {"name": "ICT", "confidence": 0.015},
                {"name": "ESIPT", "confidence": 0.005},
            ],
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].planned_agents == ["verifier"]
    assert result["decision"].task_instruction == "Verifier: Resolve exact identity and photophysics for the current pairwise gap."


def test_planner_diagnosis_contracts_multi_action_microscopic_task_to_single_action(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "neutral aromatic", "confidence": 0.46},
                {"name": "TICT", "confidence": 0.31},
                {"name": "ICT", "confidence": 0.18},
                {"name": "unknown", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.01}
              ],
              "diagnosis": "A torsion follow-up is still the most informative next internal discriminator.",
              "action": "microscopic",
              "current_hypothesis": "neutral aromatic",
              "confidence": 0.46,
              "needs_verifier": false,
              "task_instruction": "Microscopic agent: run run_torsion_snapshots on the key dihedral, then run parse_snapshot_outputs on the resulting bundle, then run extract_ct_descriptors_from_bundle on round_01_baseline_bundle and the new torsion bundle.",
              "agent_task_instructions": {
                "microscopic": "Execute run_torsion_snapshots for dih_1_2_3_4, then parse_snapshot_outputs, then extract_ct_descriptors_from_bundle on round_01_baseline_bundle."
              },
              "evidence_summary": "Baseline is bright but torsion sensitivity is still unmeasured.",
              "main_gap": "Need torsion-dependent internal evidence to separate neutral aromatic from TICT.",
              "conflict_status": "mixed_signals_but_resolvable",
              "hypothesis_uncertainty_note": "The key uncertainty is whether twisting causes a dark CT-like state.",
              "capability_assessment": "Microscopic can run bounded torsion follow-up or artifact-backed parse actions, but only one action per decision.",
              "stagnation_assessment": "No stagnation yet.",
              "contraction_reason": ""
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            current_hypothesis="neutral aromatic",
            confidence=0.44,
            runner_up_hypothesis="TICT",
            runner_up_confidence=0.33,
            decision_pair=["neutral aromatic", "TICT"],
            hypothesis_pool=[
                {"name": "neutral aromatic", "confidence": 0.44},
                {"name": "TICT", "confidence": 0.33},
                {"name": "ICT", "confidence": 0.18},
                {"name": "unknown", "confidence": 0.03},
                {"name": "ESIPT", "confidence": 0.02},
            ],
        )
    )

    instruction = result["decision"].task_instruction or ""
    assert result["decision"].action == "microscopic"
    assert instruction.startswith("Current reasoning phase:")
    assert "Execute ONLY `run_torsion_snapshots`" in instruction
    assert "parse_snapshot_outputs" not in instruction
    assert "extract_ct_descriptors_from_bundle" not in instruction
    assert result["decision"].agent_task_instructions["microscopic"] == instruction
    assert "single registry-backed action" in (result["decision"].contraction_reason or "")


def test_planner_diagnosis_redirects_structure_blocked_microscopic_to_verifier(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.58},
                {"name": "TICT", "confidence": 0.24},
                {"name": "neutral aromatic", "confidence": 0.11},
                {"name": "unknown", "confidence": 0.05},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "diagnosis": "A bounded microscopic follow-up would normally be next.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.58,
              "needs_verifier": false,
              "task_instruction": "Collect additional microscopic evidence for the current working hypothesis 'ICT'.",
              "evidence_summary": "The previous internal result was incomplete.",
              "main_gap": "Need one more discriminator between ICT and TICT.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual uncertainty remains.",
              "capability_assessment": "Microscopic can usually run one bounded follow-up.",
              "stagnation_assessment": "No stagnation yet."
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            microscopic_reports=[_microscopic_structure_blocked_report()],
            shared_structure_status="failed",
            shared_structure_error={
                "code": "embedding_failed",
                "message": "RDKit failed to embed any 3D conformer for the current molecule.",
            },
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].planned_agents == ["verifier"]
    assert result["decision"].needs_verifier is True
    assert "structure preparation is blocked" in (result["decision"].capability_assessment or "").lower()
    assert "high-confidence external verification" in (result["decision"].task_instruction or "")


def test_planner_reweight_redirects_structure_blocked_microscopic_to_macro_after_verifier(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.63},
                {"name": "TICT", "confidence": 0.21},
                {"name": "neutral aromatic", "confidence": 0.10},
                {"name": "unknown", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "diagnosis": "One more microscopic refinement would normally be useful before closure.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.63,
              "needs_verifier": false,
              "task_instruction": "Collect additional microscopic evidence for the current working hypothesis 'ICT'.",
              "evidence_summary": "Verifier already supplied the external context; one internal refinement would usually follow.",
              "main_gap": "Need one more pairwise discriminator between ICT and TICT.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual uncertainty remains.",
              "capability_assessment": "Microscopic can usually provide a bounded follow-up.",
              "stagnation_assessment": "No stagnation yet."
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            microscopic_reports=[_microscopic_structure_blocked_report()],
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT", "close_family")],
            shared_structure_status="failed",
            shared_structure_error={
                "code": "embedding_failed",
                "message": "RDKit failed to embed any 3D conformer for the current molecule.",
            },
        )
    )

    assert result["decision"].action == "macro"
    assert result["decision"].planned_agents == ["macro"]
    assert "microscopic" not in result["decision"].planned_agents
    assert result["decision"].task_instruction
    assert "shared 3d structure preparation is unavailable" in (result["decision"].task_instruction or "").lower()


def test_planner_reweight_redirects_finalize_to_targeted_task_when_closure_is_missing(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.64},
                {"name": "neutral aromatic", "confidence": 0.24},
                {"name": "TICT", "confidence": 0.05},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.03}
              ],
              "diagnosis": "Verifier supplementation exists, but closure justification has not yet been established for ICT versus neutral aromatic.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.64,
              "finalize": true,
              "evidence_summary": "Verifier returned new external context, but no closing discriminator was yet stated.",
              "main_gap": "Need a final targeted discriminator between ICT and neutral aromatic.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            runner_up_hypothesis="neutral aromatic",
            runner_up_confidence=0.24,
            decision_pair=["ICT", "neutral aromatic"],
            hypothesis_pool=[
                {"name": "ICT", "confidence": 0.64},
                {"name": "neutral aromatic", "confidence": 0.24},
                {"name": "TICT", "confidence": 0.05},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.03},
            ],
            verifier_reports=[_verifier_report_for_pair("ICT__vs__neutral aromatic", "close_family")],
        )
    )

    assert result["decision"].action == "microscopic"
    assert result["decision"].finalize is False
    assert result["decision"].decision_gate_status == "needs_pairwise_discriminative_task"
    assert result["decision"].closure_justification_status == "collecting"
    assert result["decision"].closure_justification_basis == "new_targeted_task"


def test_planner_reweight_does_not_use_main_gap_keywords_to_force_macro_pairwise_agent(
    tmp_path: Path,
) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.64},
                {"name": "neutral aromatic", "confidence": 0.24},
                {"name": "TICT", "confidence": 0.05},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.03}
              ],
              "diagnosis": "Verifier supplementation exists, but closure justification has not yet been established for ICT versus neutral aromatic.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.64,
              "finalize": true,
              "evidence_summary": "Verifier returned new external context, but no closing discriminator was yet stated.",
              "main_gap": "Need a final planarity and rotor discriminator between ICT and neutral aromatic.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            runner_up_hypothesis="neutral aromatic",
            runner_up_confidence=0.24,
            decision_pair=["ICT", "neutral aromatic"],
            hypothesis_pool=[
                {"name": "ICT", "confidence": 0.64},
                {"name": "neutral aromatic", "confidence": 0.24},
                {"name": "TICT", "confidence": 0.05},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.03},
            ],
            verifier_reports=[_verifier_report_for_pair("ICT__vs__neutral aromatic", "close_family")],
        )
    )

    assert result["decision"].action == "microscopic"
    assert result["decision"].planned_agents == ["microscopic"]
    assert result["decision"].finalize is False
    assert result["decision"].decision_gate_status == "needs_pairwise_discriminative_task"
    assert "bounded microscopic discriminative task" in (result["decision"].task_instruction or "")


def test_planner_reweight_normalizes_prepare_finalization_alias_to_finalize(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "neutral aromatic", "confidence": 0.83},
                {"name": "TICT", "confidence": 0.11},
                {"name": "unknown", "confidence": 0.03},
                {"name": "ICT", "confidence": 0.02},
                {"name": "ESIPT", "confidence": 0.01}
              ],
              "diagnosis": "No further agent execution is needed; prepare final closure synthesis from the existing evidence chain.",
              "action": "prepare_finalization",
              "current_hypothesis": "neutral aromatic",
              "confidence": 0.83,
              "task_instruction": "No further agent execution. Prepare final closure write-up for neutral aromatic vs TICT from the parsed torsion bundle and verifier precedent.",
              "evidence_summary": "Existing internal and verifier evidence already close the pair.",
              "main_gap": "The decisive gap is closed.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            current_hypothesis="neutral aromatic",
            confidence=0.83,
            runner_up_hypothesis="TICT",
            runner_up_confidence=0.11,
            decision_pair=["neutral aromatic", "TICT"],
            hypothesis_pool=[
                {"name": "neutral aromatic", "confidence": 0.83},
                {"name": "TICT", "confidence": 0.11},
                {"name": "unknown", "confidence": 0.03},
                {"name": "ICT", "confidence": 0.02},
                {"name": "ESIPT", "confidence": 0.01},
            ],
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="neutral aromatic__vs__TICT",
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="sufficient",
            pairwise_task_rationale="Parsed torsion snapshots show the lowest state remains bright across the discriminator.",
            verifier_reports=[_verifier_report_for_pair("neutral aromatic__vs__TICT", "close_family")],
        )
    )

    assert result["decision"].action == "finalize"
    assert result["decision"].finalize is True
    assert result["decision"].planned_agents == []
    assert result["decision"].decision_gate_status == "ready_to_finalize_decisive"
    assert result["decision"].pairwise_task_outcome == "resolved_with_verifier_support"


def test_planner_reweight_allows_decisive_finalize_when_verifier_and_closure_are_sufficient(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.81},
                {"name": "TICT", "confidence": 0.10},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "neutral aromatic", "confidence": 0.03},
                {"name": "unknown", "confidence": 0.02}
              ],
              "diagnosis": "Verifier supplementation and existing internal evidence together now justify decisive closure for ICT over TICT.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.81,
              "finalize": true,
              "evidence_summary": "Internal and external evidence both support the current top pair ordering.",
              "main_gap": "The decisive gap is closed.",
              "conflict_status": "none"
            }
            """
        ],
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            confidence=0.81,
            runner_up_confidence=0.10,
            hypothesis_pool=[
                {"name": "ICT", "confidence": 0.81},
                {"name": "TICT", "confidence": 0.10},
                {"name": "ESIPT", "confidence": 0.04},
                {"name": "neutral aromatic", "confidence": 0.03},
                {"name": "unknown", "confidence": 0.02},
            ],
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="ICT__vs__TICT",
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="sufficient",
            pairwise_task_rationale="Existing internal evidence directly separates ICT from TICT.",
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT", "close_family")],
        )
    )

    assert result["decision"].finalize is True
    assert result["decision"].finalization_mode == "decisive"
    assert result["decision"].decision_gate_status == "ready_to_finalize_decisive"
    assert result["decision"].closure_justification_status == "sufficient"
    assert result["decision"].verifier_supplement_status == "sufficient"
    assert result["decision"].pairwise_task_outcome == "resolved_with_verifier_support"


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
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="collecting",
            pairwise_task_rationale="The bounded microscopic discriminator stayed ambiguous.",
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT")],
        )
    )

    assert result["decision"].finalize is True
    assert result["decision"].finalization_mode == "best_available"
    assert result["decision"].decision_gate_status == "ready_to_finalize_best_available"
    assert result["decision"].verifier_supplement_status == "sufficient"
    assert result["decision"].closure_justification_status == "collecting"
    assert result["decision"].pairwise_task_outcome == "resolved_with_verifier_support"
    assert "Best-available closure" in (result["decision"].final_hypothesis_rationale or "")


def test_planner_reweight_allows_best_available_finalize_when_closure_is_blocked(tmp_path: Path) -> None:
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
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="blocked",
            pairwise_task_rationale="The bounded microscopic discriminator failed locally.",
            verifier_reports=[_verifier_report_for_pair("ICT__vs__TICT")],
        )
    )

    assert result["decision"].finalize is True
    assert result["decision"].finalization_mode == "best_available"
    assert result["decision"].closure_justification_status == "blocked"
    assert result["decision"].decision_gate_status == "ready_to_finalize_best_available"
    assert result["decision"].pairwise_task_outcome == "best_available_tool_blocked"


def test_planner_diagnosis_forces_finalize_on_last_allowed_round(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.61},
                {"name": "TICT", "confidence": 0.25},
                {"name": "neutral aromatic", "confidence": 0.08},
                {"name": "unknown", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "diagnosis": "A final microscopic refinement would normally be helpful.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.61,
              "needs_verifier": false,
              "finalize": false,
              "task_instruction": "Collect additional microscopic evidence for ICT versus TICT.",
              "evidence_summary": "Internal evidence is still incomplete.",
              "main_gap": "Need one more ICT-vs-TICT discriminator.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual uncertainty remains.",
              "capability_assessment": "Microscopic can usually provide one bounded follow-up.",
              "stagnation_assessment": "No stagnation yet."
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            round_idx=3,
            latest_main_gap="Need one more ICT-vs-TICT discriminator.",
        )
    )

    assert result["decision"].action == "finalize"
    assert result["decision"].finalize is True
    assert result["decision"].planned_agents == []
    assert result["decision"].task_instruction is None
    assert result["decision"].finalization_mode == "best_available"
    assert result["decision"].decision_gate_status == "ready_to_finalize_best_available"
    assert "Round-budget closure at round 4/4" in (result["decision"].final_hypothesis_rationale or "")


def test_planner_diagnosis_preserves_budget_stop_alias_on_last_allowed_round(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.61},
                {"name": "TICT", "confidence": 0.25},
                {"name": "neutral aromatic", "confidence": 0.08},
                {"name": "unknown", "confidence": 0.04},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "reasoning_phase": "portfolio_screening",
              "portfolio_screening_complete": false,
              "credible_alternative_hypotheses": ["ESIPT"],
              "coverage_debt_hypotheses": ["ESIPT"],
              "hypothesis_screening_ledger": [
                {
                  "hypothesis": "ESIPT",
                  "screening_status": "untested",
                  "screening_priority": "high",
                  "evidence_families_covered": [],
                  "screening_note": "Still needs one direct screen."
                }
              ],
              "portfolio_screening_summary": "ESIPT remains untested, but the round budget is exhausted.",
              "diagnosis": "Chosen next action is to stop (no action) because the round budget is exhausted.",
              "action": "no_action_budget_exhausted",
              "current_hypothesis": "ICT",
              "confidence": 0.61,
              "needs_verifier": false,
              "finalize": false,
              "task_instruction": "",
              "agent_task_instructions": {},
              "evidence_summary": "Internal evidence is still incomplete.",
              "main_gap": "ESIPT still lacks a direct screen.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual uncertainty remains.",
              "capability_assessment": "Budget is exhausted.",
              "stagnation_assessment": "No further action can run within the remaining budget.",
              "decision_gate_status": "needs_portfolio_screening"
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            round_idx=3,
            latest_main_gap="ESIPT still lacks a direct screen.",
        )
    )

    decision = result["decision"]
    assert decision.action == "stop"
    assert decision.finalize is False
    assert decision.planned_agents == []
    assert decision.task_instruction is None
    assert decision.agent_task_instructions == {}
    assert decision.decision_gate_status == "needs_portfolio_screening"


def test_planner_diagnosis_redirects_repeated_microscopic_local_uncertainty_to_verifier(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.63},
                {"name": "TICT", "confidence": 0.24},
                {"name": "neutral aromatic", "confidence": 0.08},
                {"name": "unknown", "confidence": 0.03},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "diagnosis": "One more microscopic parse-only pass would normally be the next step.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.63,
              "needs_verifier": false,
              "task_instruction": "Collect additional microscopic evidence for the current working hypothesis 'ICT'.",
              "evidence_summary": "The same artifact-backed route remains available.",
              "main_gap": "Need one more ICT-vs-TICT discriminator.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual uncertainty remains.",
              "capability_assessment": "Microscopic can usually provide one bounded follow-up.",
              "stagnation_assessment": "No stagnation yet."
            }
            """
        ],
    )
    repeated_uncertainty = (
        "Microscopic local uncertainty after this Amesp run: this bounded Amesp route "
        "'artifact_parse_only' does not adjudicate the global mechanism. it only parses existing artifacts "
        "and cannot create new microscopic evidence."
    )

    result = planner.plan_diagnosis(
        _base_state(
            microscopic_reports=[
                {
                    "agent_name": "microscopic",
                    "task_received": "microscopic task",
                    "task_understanding": "microscopic understanding",
                    "reasoning_summary": "microscopic reasoning summary",
                    "execution_plan": "microscopic execution plan",
                    "result_summary": "microscopic result summary",
                    "remaining_local_uncertainty": repeated_uncertainty,
                    "tool_calls": [],
                    "raw_results": {},
                    "structured_results": {},
                    "status": "success",
                    "planner_readable_report": "microscopic planner readable report",
                }
            ],
            working_memory=[
                _working_memory_entry_with_agent_uncertainty(
                    round_id=1,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                ),
                _working_memory_entry_with_agent_uncertainty(
                    round_id=2,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                ),
            ],
        )
    )

    assert result["decision"].action == "verifier"
    assert result["decision"].needs_verifier is True
    assert result["decision"].stagnation_detected is True
    assert "repeats the same microscopic local uncertainty" in (result["decision"].contraction_reason or "")
    assert "high-confidence external verification" in (result["decision"].task_instruction or "")


def test_planner_reweight_finalizes_when_repeated_microscopic_local_uncertainty_persists_after_verifier(
    tmp_path: Path,
) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ESIPT", "confidence": 0.66},
                {"name": "TICT", "confidence": 0.24},
                {"name": "ICT", "confidence": 0.05},
                {"name": "unknown", "confidence": 0.03},
                {"name": "neutral aromatic", "confidence": 0.02}
              ],
              "diagnosis": "Another microscopic parse-only pass might still clarify the remaining CT-like gap.",
              "action": "microscopic",
              "current_hypothesis": "ESIPT",
              "confidence": 0.66,
              "needs_verifier": false,
              "task_instruction": "Collect additional microscopic evidence for the current working hypothesis 'ESIPT'.",
              "evidence_summary": "Verifier already ran, but the remaining gap still looks internal.",
              "main_gap": "Need the CT-localization character of the 90-degree brightened state.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Residual ESIPT-vs-TICT uncertainty remains.",
              "capability_assessment": "Microscopic can parse existing artifact bundles.",
              "stagnation_assessment": "No stagnation yet."
            }
            """
        ],
    )
    repeated_uncertainty = (
        "Microscopic local uncertainty after this Amesp run: this bounded Amesp route "
        "'artifact_parse_only' does not adjudicate the global mechanism. it only parses existing artifacts "
        "and cannot create new microscopic evidence."
    )

    result = planner.plan_reweight_or_finalize(
        _base_state(
            current_hypothesis="ESIPT",
            confidence=0.66,
            runner_up_hypothesis="TICT",
            runner_up_confidence=0.24,
            decision_pair=["ESIPT", "TICT"],
            hypothesis_pool=[
                {"name": "ESIPT", "confidence": 0.66},
                {"name": "TICT", "confidence": 0.24},
                {"name": "ICT", "confidence": 0.05},
                {"name": "unknown", "confidence": 0.03},
                {"name": "neutral aromatic", "confidence": 0.02},
            ],
            pairwise_task_agent="microscopic",
            pairwise_task_completed_for_pair="ESIPT__vs__TICT",
            pairwise_task_outcome="dedicated_pairwise_task_completed",
            pairwise_resolution_mode="dedicated_pairwise_task_completed",
            closure_justification_status="collecting",
            pairwise_task_rationale="Existing torsion and geometry evidence narrowed ESIPT versus TICT but did not close the gap.",
            microscopic_reports=[
                {
                    "agent_name": "microscopic",
                    "task_received": "microscopic task",
                    "task_understanding": "microscopic understanding",
                    "reasoning_summary": "microscopic reasoning summary",
                    "execution_plan": "microscopic execution plan",
                    "result_summary": "microscopic result summary",
                    "remaining_local_uncertainty": repeated_uncertainty,
                    "tool_calls": [],
                    "raw_results": {},
                    "structured_results": {},
                    "status": "success",
                    "planner_readable_report": "microscopic planner readable report",
                }
            ],
            verifier_reports=[_verifier_report_for_pair("ESIPT__vs__TICT", "close_family")],
            working_memory=[
                _working_memory_entry_with_agent_uncertainty(
                    round_id=4,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                    current_hypothesis="ESIPT",
                    confidence=0.64,
                    main_gap="Need the CT-localization character of the 90-degree brightened state.",
                ),
                _working_memory_entry_with_agent_uncertainty(
                    round_id=5,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                    current_hypothesis="ESIPT",
                    confidence=0.65,
                    main_gap="Need the CT-localization character of the 90-degree brightened state.",
                ),
            ],
        )
    )

    assert result["decision"].action == "finalize"
    assert result["decision"].finalize is True
    assert result["decision"].finalization_mode == "best_available"
    assert result["decision"].decision_gate_status == "ready_to_finalize_best_available"
    assert result["decision"].closure_justification_status == "blocked"
    assert result["decision"].pairwise_task_outcome == "best_available_tool_blocked"
    assert "repeated microscopic local limitation" in (result["decision"].final_hypothesis_rationale or "")


def test_planner_diagnosis_does_not_finalize_when_switching_to_new_supported_microscopic_capability(
    tmp_path: Path,
) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.46},
                {"name": "neutral aromatic", "confidence": 0.27},
                {"name": "unknown", "confidence": 0.14},
                {"name": "TICT", "confidence": 0.11},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "diagnosis": "The density/population route failed; switch to a different microscopic observable family.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.46,
              "needs_verifier": false,
              "task_instruction": "Microscopic (single registry-backed action): run `run_targeted_transition_dipole_analysis` using artifact_bundle_id='round_01_baseline_bundle'.",
              "agent_task_instructions": {
                "microscopic": "Run exactly one Amesp action: `run_targeted_transition_dipole_analysis` using artifact_bundle_id='round_01_baseline_bundle'."
              },
              "evidence_summary": "The latest density/population action failed because the backend did not expose the requested discriminator.",
              "main_gap": "Need a molecule-specific ICT-vs-LE localization discriminator.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "Still missing molecule-specific CT-localization observables.",
              "capability_assessment": "The current density/population route is insufficient, but transition-dipole and RIS routes remain available.",
              "stagnation_assessment": "The failing density/population route should not be repeated.",
              "contraction_reason": "Pivot to run_targeted_transition_dipole_analysis instead of repeating the failing density/population path.",
              "verifier_supplement_status": "sufficient",
              "verifier_information_gain": "high",
              "verifier_evidence_relation": "mixed",
              "verifier_supplement_summary": "Close-family verifier evidence remains sufficient for ICT vs neutral aromatic.",
              "closure_justification_status": "blocked",
              "closure_justification_evidence_source": "internal",
              "closure_justification_basis": "existing_evidence",
              "closure_justification_summary": "Need one more internal molecule-specific discriminator after the density/population route failed.",
              "pairwise_task_agent": "microscopic",
              "pairwise_task_completed_for_pair": "ICT__vs__neutral aromatic",
              "pairwise_task_outcome": "not_run",
              "pairwise_task_rationale": "Switch to a different microscopic capability rather than repeating the same failing one.",
              "finalization_mode": "best_available"
            }
            """
        ],
    )
    repeated_uncertainty = (
        "Microscopic local uncertainty after this Amesp run: this bounded Amesp route "
        "'targeted_property_follow_up' does not adjudicate the global mechanism. it does not execute full-DFT "
        "or heavy excited-state optimization. it also leaves unsupported local requests unresolved: excited-state "
        "relaxation; relaxed scan; solvent response. targeted follow-up remains bounded by current Amesp route "
        "availability and resource limits."
    )

    result = planner.plan_diagnosis(
        _base_state(
            current_hypothesis="ICT",
            confidence=0.46,
            runner_up_hypothesis="neutral aromatic",
            runner_up_confidence=0.27,
            decision_pair=["ICT", "neutral aromatic"],
            microscopic_reports=[
                {
                    "agent_name": "microscopic",
                    "task_received": "Run density/population analysis.",
                    "task_understanding": "density/population analysis",
                    "reasoning_summary": "density/population reasoning summary",
                    "execution_plan": "density/population execution plan",
                    "result_summary": "density/population result summary",
                    "remaining_local_uncertainty": repeated_uncertainty,
                    "tool_calls": [],
                    "raw_results": {},
                    "structured_results": {
                        "executed_capability": "run_targeted_density_population_analysis",
                    },
                    "status": "failed",
                    "planner_readable_report": "microscopic planner readable report",
                }
            ],
            verifier_reports=[_verifier_report_for_pair("ICT__vs__neutral aromatic", "close_family")],
            working_memory=[
                _working_memory_entry_with_agent_uncertainty(
                    round_id=4,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                    current_hypothesis="ICT",
                    confidence=0.47,
                    main_gap="Need a molecule-specific ICT-vs-LE localization discriminator.",
                ),
                _working_memory_entry_with_agent_uncertainty(
                    round_id=5,
                    action_taken="microscopic",
                    uncertainty=repeated_uncertainty,
                    current_hypothesis="ICT",
                    confidence=0.48,
                    main_gap="Need a molecule-specific ICT-vs-LE localization discriminator.",
                ),
            ],
        )
    )

    assert result["decision"].action == "microscopic"
    assert result["decision"].finalize is False
    assert "run_targeted_transition_dipole_analysis" in (result["decision"].task_instruction or "")


def test_initial_response_can_enter_portfolio_screening_with_coverage_debt(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.49, "rationale": "Current lead."},
                {"name": "TICT", "confidence": 0.28, "rationale": "Runner-up."},
                {"name": "ESIPT", "confidence": 0.17, "rationale": "Still credible alternative."},
                {"name": "neutral aromatic", "confidence": 0.04, "rationale": "Weak fallback."},
                {"name": "unknown", "confidence": 0.02, "rationale": "Residual uncertainty."}
              ],
              "current_hypothesis": "ICT",
              "confidence": 0.49,
              "reasoning_phase": "portfolio_screening",
              "portfolio_screening_complete": false,
              "credible_alternative_hypotheses": ["TICT", "ESIPT"],
              "coverage_debt_hypotheses": ["TICT", "ESIPT"],
              "hypothesis_screening_ledger": [
                {
                  "hypothesis": "TICT",
                  "screening_status": "untested",
                  "screening_priority": "high",
                  "evidence_families_covered": [],
                  "screening_note": "Needs direct torsion-sensitive screening."
                },
                {
                  "hypothesis": "ESIPT",
                  "screening_status": "indirectly_weakened",
                  "screening_priority": "normal",
                  "evidence_families_covered": ["state_ordering_brightness"],
                  "screening_note": "Still credible but not directly screened."
                }
              ],
              "portfolio_screening_summary": "TICT and ESIPT remain credible and still carry direct-screening debt.",
              "diagnosis": "Remain in portfolio screening before pairwise contraction.",
              "action": "macro_and_microscopic",
              "task_instruction": "Dispatch first-round tasks.",
              "agent_task_instructions": {
                "macro": "Inspect low-cost structural readiness.",
                "microscopic": "Run the first-round bounded baseline bundle."
              }
            }
            """
        ],
    )

    result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="C1=CC=CC=C1",
        )
    )

    decision = result["decision"]
    assert decision.reasoning_phase == "portfolio_screening"
    assert decision.portfolio_screening_complete is False
    assert decision.coverage_debt_hypotheses == ["TICT", "ESIPT"]
    assert decision.decision_gate_status == "needs_portfolio_screening"
    assert decision.decision_pair == []


def test_portfolio_screening_gate_blocks_finalize_when_coverage_debt_remains(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.58, "rationale": "Still leads."},
                {"name": "TICT", "confidence": 0.24, "rationale": "Runner-up."},
                {"name": "ESIPT", "confidence": 0.12, "rationale": "Still credible."},
                {"name": "neutral aromatic", "confidence": 0.04, "rationale": "Weak fallback."},
                {"name": "unknown", "confidence": 0.02, "rationale": "Residual uncertainty."}
              ],
              "reasoning_phase": "portfolio_screening",
              "portfolio_screening_complete": false,
              "credible_alternative_hypotheses": ["ESIPT"],
              "coverage_debt_hypotheses": ["ESIPT"],
              "hypothesis_screening_ledger": [
                {
                  "hypothesis": "ESIPT",
                  "screening_status": "untested",
                  "screening_priority": "high",
                  "evidence_families_covered": [],
                  "screening_note": "Still needs one direct screening task."
                }
              ],
              "portfolio_screening_summary": "ESIPT remains a still-credible but untested alternative.",
              "diagnosis": "Do not finalize before screening ESIPT directly.",
              "action": "finalize",
              "current_hypothesis": "ICT",
              "confidence": 0.58,
              "needs_verifier": false,
              "finalize": true,
              "task_instruction": "Use run_targeted_state_characterization to directly screen the remaining alternative.",
              "agent_task_instructions": {
                "microscopic": "Use run_targeted_state_characterization to directly screen the remaining alternative."
              },
              "evidence_summary": "Baseline evidence supports ICT, but ESIPT is still untested.",
              "main_gap": "ESIPT has not yet been directly screened.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "A credible third hypothesis is still outstanding.",
              "final_hypothesis_rationale": "This should be blocked by the portfolio-screening gate.",
              "capability_assessment": "A bounded targeted screen is still available.",
              "stagnation_assessment": "No stagnation is present.",
              "contraction_reason": "Do not collapse to pairwise before screening debt clears.",
              "information_gain_assessment": "One more direct screen is still required.",
              "gap_trend": "The gap is shrinking but remains open.",
              "stagnation_detected": false,
              "capability_lesson_candidates": [],
              "hypothesis_reweight_explanation": {
                "ICT": "Current lead from existing evidence.",
                "TICT": "Still plausible runner-up.",
                "ESIPT": "Still credible and not directly screened.",
                "neutral aromatic": "Weak fallback.",
                "unknown": "Residual uncertainty."
              },
              "decision_gate_status": "ready_to_finalize_best_available",
              "verifier_supplement_status": "sufficient",
              "verifier_information_gain": "medium",
              "verifier_evidence_relation": "supports_top1",
              "closure_justification_status": "sufficient",
              "closure_justification_evidence_source": "mixed",
              "closure_justification_basis": "existing_evidence",
              "finalization_mode": "best_available"
            }
            """
        ],
    )
    state = _base_state()

    result = planner.plan_diagnosis(state)

    decision = result["decision"]
    assert decision.finalize is False
    assert decision.action == "microscopic"
    assert decision.reasoning_phase == "portfolio_screening"
    assert decision.portfolio_screening_complete is False
    assert decision.coverage_debt_hypotheses == ["ESIPT"]
    assert decision.decision_gate_status == "needs_portfolio_screening"
    assert decision.decision_pair == []


def test_portfolio_screening_completes_when_alternatives_are_blocked_or_dropped(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "neutral aromatic", "confidence": 0.63},
                {"name": "unknown", "confidence": 0.17},
                {"name": "TICT", "confidence": 0.11},
                {"name": "ICT", "confidence": 0.07},
                {"name": "ESIPT", "confidence": 0.02}
              ],
              "reasoning_phase": "portfolio_screening",
              "portfolio_screening_complete": false,
              "credible_alternative_hypotheses": ["TICT", "ICT", "ESIPT"],
              "coverage_debt_hypotheses": [],
              "hypothesis_screening_ledger": [
                {
                  "hypothesis": "TICT",
                  "screening_status": "blocked_by_capability",
                  "screening_priority": "high",
                  "evidence_families_covered": ["torsion_sensitivity"],
                  "screening_note": "Further bounded torsion evidence is unavailable."
                },
                {
                  "hypothesis": "ICT",
                  "screening_status": "blocked_by_capability",
                  "screening_priority": "normal",
                  "evidence_families_covered": ["charge_localization"],
                  "screening_note": "No additional bounded internal discriminator remains."
                },
                {
                  "hypothesis": "ESIPT",
                  "screening_status": "dropped_with_reason",
                  "screening_priority": "low",
                  "evidence_families_covered": ["geometry_precondition"],
                  "screening_note": "Current evidence does not justify further ESIPT screening."
                }
              ],
              "portfolio_screening_summary": "All remaining alternatives are now either blocked or explicitly dropped.",
              "diagnosis": "Chosen next action is to stop (no action) because portfolio screening is complete and the round budget is exhausted.",
              "action": "no_action_budget_exhausted",
              "current_hypothesis": "neutral aromatic",
              "confidence": 0.63,
              "needs_verifier": false,
              "finalize": false,
              "task_instruction": "",
              "agent_task_instructions": {},
              "evidence_summary": "Coverage debt is cleared, but no further bounded screening action remains.",
              "main_gap": "No further screening debt remains.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "The current lead remains provisional but screening debt is cleared.",
              "capability_assessment": "No additional bounded screening task remains.",
              "stagnation_assessment": "Round budget is exhausted.",
              "decision_gate_status": "needs_portfolio_screening"
            }
            """
        ],
    )

    result = planner.plan_diagnosis(
        _base_state(
            round_idx=3,
            current_hypothesis="neutral aromatic",
            confidence=0.63,
            runner_up_hypothesis="unknown",
            runner_up_confidence=0.17,
            hypothesis_pool=[
                {"name": "neutral aromatic", "confidence": 0.63},
                {"name": "unknown", "confidence": 0.17},
                {"name": "TICT", "confidence": 0.11},
                {"name": "ICT", "confidence": 0.07},
                {"name": "ESIPT", "confidence": 0.02},
            ],
            latest_main_gap="No further screening debt remains.",
            decision_gate_status="needs_portfolio_screening",
        )
    )

    decision = result["decision"]
    assert decision.action == "stop"
    assert decision.reasoning_phase == "pairwise_contraction"
    assert decision.portfolio_screening_complete is True
    assert decision.coverage_debt_hypotheses == []
    assert decision.decision_gate_status == "not_ready"
    assert decision.planned_agents == []
    assert decision.task_instruction is None
    assert decision.agent_task_instructions == {}


def test_initial_portfolio_screening_uses_portfolio_neutral_agent_framing(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.46},
                {"name": "TICT", "confidence": 0.31},
                {"name": "ESIPT", "confidence": 0.17},
                {"name": "neutral aromatic", "confidence": 0.04},
                {"name": "unknown", "confidence": 0.02}
              ],
              "current_hypothesis": "ICT",
              "confidence": 0.46,
              "reasoning_phase": "portfolio_screening",
              "portfolio_screening_complete": false,
              "credible_alternative_hypotheses": ["TICT", "ESIPT"],
              "coverage_debt_hypotheses": ["TICT", "ESIPT"],
              "hypothesis_screening_ledger": [
                {
                  "hypothesis": "TICT",
                  "screening_status": "untested",
                  "screening_priority": "high",
                  "evidence_families_covered": [],
                  "screening_note": "Needs direct screening."
                },
                {
                  "hypothesis": "ESIPT",
                  "screening_status": "indirectly_weakened",
                  "screening_priority": "normal",
                  "evidence_families_covered": ["state_ordering_brightness"],
                  "screening_note": "Still needs direct screening."
                }
              ],
              "portfolio_screening_summary": "TICT and ESIPT remain coverage-debt hypotheses.",
              "screening_focus_hypotheses": ["TICT", "ESIPT"],
              "screening_focus_summary": "Use the first round to screen TICT and ESIPT without anchoring on ICT.",
              "diagnosis": "Remain in portfolio screening.",
              "action": "macro_and_microscopic",
              "task_instruction": "Dispatch first-round screening tasks.",
              "agent_task_instructions": {
                "macro": "Assess low-cost structural readiness for the still-credible alternatives.",
                "microscopic": "Run the bounded baseline bundle to reduce portfolio uncertainty."
              }
            }
            """
        ],
    )

    result = planner.plan_initial(
        AieMasState(
            user_query="Assess the likely AIE mechanism for this molecule.",
            smiles="C1=CC=CC=C1",
        )
    )

    decision = result["decision"]
    assert decision.agent_framing_mode == "portfolio_neutral"
    assert decision.screening_focus_hypotheses == ["TICT", "ESIPT"]
    assert decision.screening_focus_summary is not None
    assert decision.agent_task_instructions["macro"].startswith("Current reasoning phase: portfolio_screening.")
    assert "provisional top1" in decision.agent_task_instructions["macro"]
    assert "Screening focus hypotheses: TICT, ESIPT." in decision.agent_task_instructions["microscopic"]


def test_pairwise_contraction_uses_hypothesis_anchored_agent_framing(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            """
            {
              "hypothesis_pool": [
                {"name": "ICT", "confidence": 0.73},
                {"name": "TICT", "confidence": 0.21},
                {"name": "ESIPT", "confidence": 0.03},
                {"name": "neutral aromatic", "confidence": 0.02},
                {"name": "unknown", "confidence": 0.01}
              ],
              "reasoning_phase": "pairwise_contraction",
              "portfolio_screening_complete": true,
              "credible_alternative_hypotheses": [],
              "coverage_debt_hypotheses": [],
              "hypothesis_screening_ledger": [],
              "portfolio_screening_summary": "Portfolio screening is complete.",
              "screening_focus_hypotheses": ["ICT", "TICT"],
              "screening_focus_summary": "The remaining task is pairwise contraction between ICT and TICT.",
              "diagnosis": "Enter pairwise contraction.",
              "action": "microscopic",
              "current_hypothesis": "ICT",
              "confidence": 0.73,
              "needs_verifier": false,
              "finalize": false,
              "task_instruction": "Run one bounded discriminative microscopic task.",
              "agent_task_instructions": {
                "microscopic": "Run one bounded discriminative microscopic task."
              },
              "evidence_summary": "Portfolio screening is complete.",
              "main_gap": "Need one more pairwise discriminator between ICT and TICT.",
              "conflict_status": "none",
              "hypothesis_uncertainty_note": "The champion still needs one more pairwise discriminator.",
              "final_hypothesis_rationale": "",
              "capability_assessment": "A bounded microscopic follow-up is still available.",
              "stagnation_assessment": "No stagnation is present.",
              "contraction_reason": "Pairwise contraction is now appropriate.",
              "information_gain_assessment": "One more discriminative task should be enough.",
              "gap_trend": "narrowing",
              "stagnation_detected": false,
              "capability_lesson_candidates": [],
              "hypothesis_reweight_explanation": {
                "ICT": "Current champion after screening.",
                "TICT": "Current challenger after screening.",
                "ESIPT": "Dropped after screening.",
                "neutral aromatic": "Weak fallback.",
                "unknown": "Residual uncertainty."
              },
              "decision_gate_status": "not_ready",
              "verifier_supplement_status": "missing",
              "verifier_information_gain": "none",
              "verifier_evidence_relation": "no_new_info",
              "closure_justification_status": "missing",
              "closure_justification_evidence_source": "",
              "closure_justification_basis": "",
              "finalization_mode": "none"
            }
            """
        ],
    )
    state = _base_state(
        reasoning_phase="pairwise_contraction",
        portfolio_screening_complete=True,
        coverage_debt_hypotheses=[],
        credible_alternative_hypotheses=[],
    )

    result = planner.plan_diagnosis(state)

    decision = result["decision"]
    assert decision.reasoning_phase == "pairwise_contraction"
    assert decision.agent_framing_mode == "hypothesis_anchored"
    assert decision.screening_focus_hypotheses == ["ICT", "TICT"]
    assert decision.agent_task_instructions["microscopic"].startswith("Current reasoning phase: pairwise_contraction.")
    assert "anchored to current working hypothesis 'ICT' against challenger 'TICT'" in decision.agent_task_instructions["microscopic"]


def test_working_memory_records_portfolio_fields_and_evidence_families() -> None:
    manager = WorkingMemoryManager()
    state = _base_state()
    state.round_idx = 1
    state.latest_evidence_summary = "A torsion screening action completed."
    state.latest_main_gap = "ESIPT remains untested."
    state.latest_conflict_status = "none"
    state.last_planner_decision = PlannerDecision(
        diagnosis="Remain in portfolio screening.",
        action="microscopic",
        current_hypothesis="ICT",
        confidence=0.66,
        reasoning_phase="portfolio_screening",
        agent_framing_mode="portfolio_neutral",
        portfolio_screening_complete=False,
        coverage_debt_hypotheses=["ESIPT"],
        credible_alternative_hypotheses=["TICT", "ESIPT"],
        hypothesis_screening_ledger=[
            HypothesisScreeningRecord(
                hypothesis="ESIPT",
                screening_status="untested",
                screening_priority="high",
            )
        ],
        portfolio_screening_summary="ESIPT remains a coverage-debt hypothesis.",
        screening_focus_hypotheses=["ESIPT"],
        screening_focus_summary="Use one bounded screening action to reduce ESIPT coverage debt.",
        planned_agents=["microscopic"],
        task_instruction="Use run_torsion_snapshots for one bounded direct screen.",
        agent_task_instructions={
            "microscopic": "Use run_torsion_snapshots for one bounded direct screen."
        },
    )
    state.active_round_reports = [
        AgentReport(
            agent_name="microscopic",
            task_received="Run one torsion screen.",
            task_understanding="Collect torsion sensitivity evidence only.",
            execution_plan="Bounded torsion snapshot follow-up.",
            result_summary="A torsion snapshot bundle was generated.",
            remaining_local_uncertainty="One more ESIPT-oriented screen may still be needed.",
            tool_calls=[],
            raw_results={},
            structured_results={"executed_capability": "run_torsion_snapshots"},
            planner_readable_report="Torsion sensitivity evidence was collected.",
            status="success",
        )
    ]

    manager.append_round_summary(state)

    entry = state.working_memory[-1]
    assert entry.reasoning_phase == "portfolio_screening"
    assert entry.agent_framing_mode == "portfolio_neutral"
    assert entry.coverage_debt_hypotheses == ["ESIPT"]
    assert entry.hypothesis_screening_ledger[0].hypothesis == "ESIPT"
    assert entry.screening_focus_hypotheses == ["ESIPT"]
    assert entry.screening_focus_summary == "Use one bounded screening action to reduce ESIPT coverage debt."
    assert entry.executed_evidence_families == ["torsion_sensitivity"]


def test_planner_diagnosis_payload_uses_compact_artifact_projection(tmp_path: Path) -> None:
    planner, fake_client = _build_planner(tmp_path, [_round_response_json()])
    huge_path = "/very/long/generated/path/" + ("nested/" * 12) + "artifact_file.aop"
    state = _base_state(
        microscopic_reports=[
            AgentReport(
                agent_name="microscopic",
                task_received="Inspect exact-member follow-up artifacts.",
                task_understanding="Inspect the generated follow-up bundle only.",
                reasoning_summary="Use reusable artifacts for a bounded direct screen.",
                execution_plan="Inspect the follow-up bundle and summarize missing deliverables.",
                result_summary="A targeted follow-up bundle was generated for two torsion members.",
                remaining_local_uncertainty="One more discriminative screen may still be required.",
                tool_calls=[],
                raw_results={},
                structured_results={
                    "executed_capability": "run_ris_state_characterization",
                    "artifact_bundle_id": "round_20_run_ris_state_characterization_bundle",
                    "artifact_bundle_kind": "targeted_property_follow_up",
                    "missing_deliverables": ["ct_number", "electron_hole_distance"],
                    "resolved_target_ids": {
                        "artifact_bundle_id": "round_02_torsion_snapshots",
                        "artifact_member_ids": ["torsion_01", "torsion_06"],
                    },
                },
                generated_artifacts={
                    "artifact_bundle_id": "round_20_run_ris_state_characterization_bundle",
                    "artifact_bundle_kind": "targeted_property_follow_up",
                    "source_bundle_id": "round_02_torsion_snapshots",
                    "source_member_ids": ["torsion_01", "torsion_06"],
                    "artifact_bundle_registry_entries": [
                        {
                            "artifact_bundle": {
                                "bundle_id": "round_20_run_ris_state_characterization_bundle",
                                "bundle_kind": "targeted_property_follow_up",
                                "source_capability": "run_ris_state_characterization",
                                "parse_capabilities_supported": ["inspect_raw_artifact_bundle"],
                            },
                            "bundle_members": [
                                {
                                    "member_id": "torsion_01",
                                    "generated_files": [huge_path for _ in range(40)],
                                    "parse_capabilities_supported": ["inspect_raw_artifact_bundle"],
                                }
                            ],
                            "generated_artifacts": {
                                "snapshot_artifacts": [{"aop_path": huge_path} for _ in range(40)]
                            },
                        }
                    ],
                },
                planner_readable_report="Reusable follow-up artifacts were generated for exact torsion members.",
                status="success",
            )
        ],
    )

    result = planner.plan_diagnosis(state)

    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "artifact_bundle_registry_entries" not in message_payload
    assert huge_path not in message_payload
    assert "round_20_run_ris_state_characterization_bundle" in message_payload
    assert '"selected_member_ids": [' in message_payload
    assert result["decision"].planner_context_budget_status in {
        "ok",
        "soft_compacted",
        "aggressive_compacted",
    }


def test_planner_diagnosis_marks_context_compaction_when_budget_is_tight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    planner, _ = _build_planner(tmp_path, [_round_response_json()])
    monkeypatch.setattr(planner_module, "_PLANNER_CONTEXT_SOFT_TOKEN_BUDGET", 150)
    monkeypatch.setattr(planner_module, "_PLANNER_CONTEXT_HARD_TOKEN_BUDGET", 220)
    state = _base_state(
        working_memory=[
            WorkingMemoryEntry(
                round_id=index,
                current_hypothesis="ICT",
                confidence=0.61,
                action_taken="macro, microscopic",
                evidence_summary="A very long but still compact history summary for planner budgeting.",
                diagnosis_summary="The same screening debt remains open and still needs follow-up.",
                main_gap="Need one more direct screen.",
                conflict_status="none",
                next_action="microscopic",
                planner_task_instruction="Use one bounded direct microscopic screen to reduce portfolio debt.",
                planned_action_label="run_targeted_state_characterization",
                executed_action_labels=["run_baseline_bundle"],
                executed_evidence_families=["state_ordering_brightness"],
                agent_reports=[
                    WorkingMemoryAgentEntry(
                        agent_name="microscopic",
                        task_received="Run baseline bundle.",
                        task_understanding="Collect bounded baseline evidence.",
                        execution_plan="Run exactly one baseline bundle.",
                        result_summary="Baseline completed successfully.",
                        remaining_local_uncertainty="Another screen is still needed.",
                        planner_compact_summary={
                            "key_observations": [
                                "executed_capability=run_baseline_bundle",
                                "Baseline completed successfully.",
                            ],
                            "key_missing_deliverables": ["ct_number"],
                            "artifact_references": [],
                        },
                    )
                ],
            )
            for index in range(1, 10)
        ],
    )

    result = planner.plan_diagnosis(state)

    decision = result["decision"]
    assert decision.planner_context_budget_status in {"soft_compacted", "aggressive_compacted"}
    assert decision.planner_context_compaction_level in {"soft", "aggressive"}
    assert decision.planner_context_estimated_tokens > 0


def test_working_memory_projection_tolerates_string_error_payloads() -> None:
    manager = WorkingMemoryManager()
    report = AgentReport(
        agent_name="verifier",
        task_received="Verifier task",
        task_completion_status="failed",
        task_completion="Verifier retrieval failed before any evidence cards could be returned.",
        task_understanding="Retrieve external evidence for the current pairwise gap.",
        execution_plan="Run verifier_evidence_lookup only.",
        result_summary="Verifier request failed because the upstream network path is unavailable.",
        remaining_local_uncertainty="No external evidence was retrieved.",
        structured_results={
            "status": "failed",
            "error": "upstream connect error",
            "verifier_target_pair": "ICT__vs__TICT",
            "verifier_supplement_status": "missing",
        },
        status="failed",
        planner_readable_report="Verifier failed before returning usable evidence cards.",
    )

    compact = manager._compact_agent_report_for_planner(report)

    assert compact is not None
    assert compact["structured_results"]["error"] == {"message": "upstream connect error"}
    assert compact["structured_results"]["verifier_target_pair"] == "ICT__vs__TICT"


def test_working_memory_projection_exposes_esipt_typed_geometry_descriptors() -> None:
    manager = WorkingMemoryManager()
    report = AgentReport(
        agent_name="microscopic",
        task_received="Geometry parse task",
        task_completion_status="contracted",
        task_completion="Local geometry parse completed in contracted form.",
        task_understanding="Extract ESIPT-relevant geometry descriptors from a reusable bundle.",
        execution_plan="Run extract_geometry_descriptors_from_bundle on the selected baseline bundle.",
        result_summary="Amesp geometry parse returned typed O-H···N descriptors.",
        remaining_local_uncertainty="Local parse cannot adjudicate the global mechanism.",
        structured_results={
            "executed_capability": "extract_geometry_descriptors_from_bundle",
            "selected_capability": "extract_geometry_descriptors_from_bundle",
            "fulfillment_mode": "exact",
            "artifact_bundle_id": "round_18_baseline_bundle",
            "artifact_bundle_kind": "baseline_bundle",
            "route_summary": {
                "artifact_scope": "baseline_bundle",
                "artifact_source_round": 18,
                "geometry_proxy_availability": "available",
                "available_geometry_descriptors": [
                    "best_phenolic_oh_to_imine_n_contact",
                    "phenolic_oh_to_imine_n_proximity",
                    "phenolic_oh_to_imine_n_orientation",
                ],
                "missing_geometry_descriptors": ["ESIPT_preorganization_compatibility"],
                "records_with_phenolic_oh_to_imine_n_candidate": 1,
                "phenolic_oh_to_imine_n_candidate_count": 2,
            },
            "parsed_snapshot_records": [
                {
                    "best_phenolic_oh_to_imine_n_contact": {
                        "donor_atom_index": 1,
                        "acceptor_atom_index": 7,
                    },
                    "phenolic_oh_to_imine_n_proximity": {
                        "matching_contact_found": True,
                        "donor_acceptor_distance_angstrom": 2.71,
                        "hydrogen_acceptor_distance_angstrom": 1.85,
                    },
                    "phenolic_oh_to_imine_n_orientation": {
                        "matching_contact_found": True,
                        "donor_hydrogen_acceptor_angle_deg": 145.2,
                        "hbond_like_geometry": True,
                    },
                }
            ],
        },
        status="success",
        planner_readable_report="Typed ESIPT geometry descriptors are available.",
    )

    compact = manager._compact_agent_report_for_planner(report)

    assert compact is not None
    assert compact["planner_compact_summary"]["best_phenolic_oh_to_imine_n_contact"] == {
        "donor_atom_index": 1,
        "acceptor_atom_index": 7,
    }
    assert compact["planner_compact_summary"]["phenolic_oh_to_imine_n_proximity"]["matching_contact_found"] is True
    assert compact["planner_compact_summary"]["phenolic_oh_to_imine_n_orientation"]["matching_contact_found"] is True
    assert compact["structured_results"]["best_phenolic_oh_to_imine_n_contact"] == {
        "donor_atom_index": 1,
        "acceptor_atom_index": 7,
    }
    assert compact["structured_results"]["phenolic_oh_to_imine_n_proximity"]["matching_contact_found"] is True
    assert compact["structured_results"]["phenolic_oh_to_imine_n_orientation"]["matching_contact_found"] is True


def test_planner_diagnosis_accepts_null_pairwise_fields(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            _round_response_json(
                action="verifier",
                pairwise_task_agent=None,
                pairwise_task_completed_for_pair=None,
                pairwise_task_rationale=None,
                pairwise_resolution_mode=None,
                pairwise_resolution_summary=None,
                verifier_supplement_target_pair=None,
                verifier_supplement_summary=None,
                closure_justification_target_pair=None,
                closure_justification_evidence_source=None,
                closure_justification_basis=None,
                closure_justification_summary=None,
            )
        ],
    )

    result = planner.plan_diagnosis(_base_state())

    decision = result["decision"]
    assert decision.action == "verifier"
    assert decision.pairwise_task_agent is None
    assert decision.pairwise_task_completed_for_pair is None


def test_planner_diagnosis_normalizes_medium_screening_priority_to_normal(tmp_path: Path) -> None:
    planner, _ = _build_planner(
        tmp_path,
        [
            _round_response_json(
                hypothesis_screening_ledger=[
                    {
                        "hypothesis": "ESIPT",
                        "screening_status": "untested",
                        "screening_priority": "medium",
                        "evidence_families_covered": [],
                        "screening_note": "Still needs a direct screen.",
                    }
                ]
            )
        ],
    )

    result = planner.plan_diagnosis(_base_state())

    ledger = result["decision"].hypothesis_screening_ledger
    assert ledger
    assert ledger[0].screening_priority == "normal"
