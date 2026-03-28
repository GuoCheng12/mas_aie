from __future__ import annotations

from pathlib import Path

import pytest

from aie_mas.agents.microscopic import _parse_tagged_microscopic_reasoning_response
from aie_mas.agents.result_agents import MicroscopicAgent
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import MicroscopicTaskSpec, SharedStructureContext
from aie_mas.llm.openai_compatible import OpenAICompatibleMicroscopicClient
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


class _SuccessfulAmespTool:
    name = "amesp_baseline_microscopic"

    def execute(
        self,
        *,
        plan,
        smiles,
        label,
        workdir,
        available_artifacts,
        progress_callback=None,
        round_index=1,
        case_id=None,
        current_hypothesis=None,
    ):
        del smiles, label, workdir, available_artifacts, progress_callback, round_index, case_id, current_hypothesis
        tool_request = plan.microscopic_tool_request
        return type(
            "RunResult",
            (),
            {
                "route": getattr(plan, "capability_route", "baseline_bundle"),
                "executed_capability": tool_request.capability_name,
                "performed_new_calculations": tool_request.perform_new_calculation,
                "reused_existing_artifacts": tool_request.reuse_existing_artifacts_only,
                "resolved_target_ids": (
                    {"dihedral_id": tool_request.dihedral_id}
                    if tool_request.dihedral_id
                    else {"artifact_bundle_id": tool_request.artifact_bundle_id}
                    if tool_request.artifact_bundle_id
                    else {}
                ),
                "honored_constraints": [],
                "unmet_constraints": [],
                "missing_deliverables": [],
                "structure": type(
                    "PreparedStructure",
                    (),
                    {"model_dump": lambda self, mode="json": {"canonical_smiles": "C1=CCCCC1", "charge": 0}},
                )(),
                "s0": type(
                    "S0Result",
                    (),
                    {
                        "final_energy_hartree": -231.123,
                        "model_dump": lambda self, mode="json": {
                            "final_energy_hartree": -231.123,
                            "dipole_debye": [0.0, 0.1, 0.0, 0.1],
                            "mulliken_charges": [-0.1, 0.1],
                            "homo_lumo_gap_ev": 7.21,
                            "geometry_atom_count": 16,
                            "geometry_xyz_path": "/tmp/s0.xyz",
                            "rmsd_from_prepared_structure_angstrom": 0.05,
                        },
                    },
                )(),
                "s1": type(
                    "S1Result",
                    (),
                    {
                        "excited_states": [
                            type(
                                "State",
                                (),
                                {
                                    "state_index": 1,
                                    "total_energy_hartree": -231.0,
                                    "oscillator_strength": 0.245,
                                    "excitation_energy_ev": 3.347,
                                },
                            )(),
                            type(
                                "State",
                                (),
                                {
                                    "state_index": 2,
                                    "total_energy_hartree": -230.95,
                                    "oscillator_strength": 0.02,
                                    "excitation_energy_ev": 3.52,
                                },
                            )(),
                        ],
                        "first_oscillator_strength": 0.245,
                        "first_excitation_energy_ev": 3.347,
                        "state_count": 2,
                        "model_dump": lambda self, mode="json": {
                            "excited_states": [
                                {
                                    "state_index": 1,
                                    "total_energy_hartree": -231.0,
                                    "oscillator_strength": 0.245,
                                    "spin_square": 0.0,
                                    "excitation_energy_ev": 3.347,
                                },
                                {
                                    "state_index": 2,
                                    "total_energy_hartree": -230.95,
                                    "oscillator_strength": 0.02,
                                    "spin_square": 0.0,
                                    "excitation_energy_ev": 3.52,
                                },
                            ],
                            "first_excitation_energy_ev": 3.347,
                            "first_oscillator_strength": 0.245,
                            "state_count": 2,
                        },
                    },
                )(),
                "parsed_snapshot_records": [],
                "route_records": [],
                "route_summary": {"state_count": 2},
                "raw_step_results": {"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
                "generated_artifacts": {"prepared_xyz_path": "/tmp/prepared_structure.xyz", "s0_aop_path": "/tmp/s0.aop"},
            },
        )()


class _CountingAmespTool(_SuccessfulAmespTool):
    def __init__(self) -> None:
        self.execute_calls = 0

    def execute(self, **kwargs):
        self.execute_calls += 1
        return super().execute(**kwargs)


def _shared_structure_context(tmp_path: Path) -> SharedStructureContext:
    return SharedStructureContext(
        input_smiles="C1=CCCCC1",
        canonical_smiles="C1=CCCCC1",
        charge=0,
        multiplicity=1,
        atom_count=16,
        conformer_count=3,
        selected_conformer_id=0,
        prepared_xyz_path=str(tmp_path / "prepared.xyz"),
        prepared_sdf_path=str(tmp_path / "prepared.sdf"),
        summary_path=str(tmp_path / "summary.json"),
        rotatable_bond_count=2,
        aromatic_ring_count=1,
        ring_system_count=1,
        hetero_atom_count=0,
        branch_point_count=1,
        donor_acceptor_partition_proxy=0.0,
        planarity_proxy=0.7,
        compactness_proxy=0.5,
        torsion_candidate_count=2,
        principal_span_proxy=6.0,
        conformer_dispersion_proxy=0.2,
    )


def _build_agent(
    tmp_path: Path,
    responses: list[str],
    *,
    amesp_tool=None,
) -> tuple[MicroscopicAgent, _FakeClient]:
    fake_client = _FakeClient(responses)
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        tool_backend="real",
        planner_backend="openai_sdk",
        microscopic_backend="openai_sdk",
        microscopic_base_url="http://34.13.73.248:3888/v1",
        microscopic_model="gpt-4.1-mini",
        microscopic_api_key="test-key",
        prompts_dir=PROMPTS_DIR,
    )
    agent = MicroscopicAgent(
        amesp_tool=amesp_tool or _SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )
    return agent, fake_client


def test_openai_microscopic_reasoning_backend_uses_configured_model(tmp_path: Path) -> None:
    agent, fake_client = _build_agent(
        tmp_path,
        [
            """
            {
              "status": "supported",
              "execution_action": "run_baseline_bundle",
              "discovery_actions": [],
              "params": {
                "perform_new_calculation": true,
                "optimize_ground_state": true
              },
              "unsupported_parts": ["torsion scan"],
              "local_execution_rationale": "Reuse or prepare a structure, run S0 optimization, then run S1 vertical excitation."
            }
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use Amesp to optimize S0, characterize S1, and also do a torsion scan if possible.",
        current_hypothesis="neutral aromatic",
        recent_rounds_context=[{"round_id": 1, "action_taken": "macro, microscopic", "main_gap": "Need more microscopic evidence."}],
        shared_structure_context=_shared_structure_context(tmp_path),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Use Amesp to optimize S0 and characterize S1.",
        ),
        case_id="case123",
        round_index=1,
    )

    assert report.structured_results["reasoning_parse_mode"] == "structured_action_decision"
    assert report.structured_results["execution_plan"]["capability_route"] == "baseline_bundle"
    assert report.structured_results["unsupported_requests"] == ["torsion scan"]
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    prompt_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "action_registry" in prompt_payload
    assert "baseline_action_card_example" in prompt_payload
    assert "torsion_action_card_example" in prompt_payload


def test_openai_microscopic_supports_semantic_contract_baseline(tmp_path: Path) -> None:
    agent, fake_client = _build_agent(
        tmp_path,
        [
            """
            {
              "status": "supported",
              "execution_action": "run_baseline_bundle",
              "discovery_actions": [],
              "params": {
                "perform_new_calculation": true,
                "optimize_ground_state": true
              },
              "unsupported_parts": [],
              "local_execution_rationale": "Run the default low-cost baseline bundle."
            }
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run the baseline S0 and S1 microscopic route.",
        current_hypothesis="neutral aromatic",
        shared_structure_context=_shared_structure_context(tmp_path),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Collect first-round microscopic baseline evidence.",
        ),
        case_id="case123",
        round_index=1,
    )

    plan = report.structured_results["execution_plan"]
    assert report.structured_results["reasoning_parse_mode"] == "structured_action_decision"
    assert report.structured_results["reasoning_contract_mode"] == "structured_action_decision"
    assert report.structured_results["reasoning_contract_errors"] == []
    assert report.structured_results["registry_action_name"] == "run_baseline_bundle"
    assert report.structured_results["registry_validation_errors"] == []
    assert plan["capability_route"] == "baseline_bundle"
    assert plan["microscopic_tool_request"]["capability_name"] == "run_baseline_bundle"
    assert len(plan["microscopic_tool_plan"]["calls"]) == 1
    assert plan["microscopic_tool_plan"]["calls"][0]["call_kind"] == "execution"
    assert fake_client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_openai_microscopic_recovers_unclosed_expected_outputs_section(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Run the first-round low-cost microscopic baseline study.
            </task_understanding>
            <reasoning_summary>
            Use the bounded baseline route and keep the task local.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability is bounded to low-cost baseline evidence collection.
            </capability_limit_note>
            <expected_outputs>
            S0 optimized geometry
            Vertical excited-state manifold data
            Torsion sensitivity summary
            ```
            <failure_policy>
            If local execution fails, return a bounded local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Run the first-round low-cost microscopic baseline task.
            execution_action=run_baseline_bundle
            requested_route_summary=Run the default low-cost baseline bundle.
            requested_deliverables=low-cost aTB S0 geometry optimization | vertical excited-state manifold characterization
            unsupported_requests=
            param.perform_new_calculation=true
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run the first-round low-cost S0/S1 microscopic baseline task.",
        current_hypothesis="neutral aromatic",
        shared_structure_context=_shared_structure_context(tmp_path),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Collect first-round microscopic baseline evidence.",
        ),
        case_id="case123",
        round_index=1,
    )

    assert report.status == "success"
    assert report.structured_results["reasoning_parse_mode"] == "semantic_contract"
    assert report.structured_results["execution_plan"]["capability_route"] == "baseline_bundle"


def test_openai_microscopic_contracts_bad_baseline_capability_back_to_baseline(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Run a first-round low-cost microscopic study on a torsion-like route.
            </task_understanding>
            <reasoning_summary>
            Use a bounded torsion follow-up.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability is bounded to low-cost routes.
            </capability_limit_note>
            <expected_outputs>
            S0 optimized geometry
            Vertical excited-state manifold data
            </expected_outputs>
            <failure_policy>
            If local execution fails, return a bounded local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Incorrectly choose torsion follow-up during baseline round.
            execution_action=run_torsion_snapshots
            discovery_actions=list_rotatable_dihedrals
            requested_route_summary=Run torsion snapshots.
            requested_deliverables=vertical excited-state manifold characterization | torsion sensitivity summary
            unsupported_requests=
            param.perform_new_calculation=true
            param.snapshot_count=2
            param.angle_offsets_deg=35,70
            param.state_window=1,2,3
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run the first-round low-cost S0/S1 microscopic baseline task.",
        current_hypothesis="neutral aromatic",
        shared_structure_context=_shared_structure_context(tmp_path),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Collect first-round microscopic baseline evidence.",
        ),
        case_id="case123",
        round_index=1,
    )

    assert report.task_completion_status == "contracted"
    assert report.structured_results["execution_plan"]["capability_route"] == "baseline_bundle"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "run_baseline_bundle"
    assert any("Baseline microscopic rounds must execute `run_baseline_bundle`" in item for item in report.structured_results["unmet_constraints"])


def test_openai_microscopic_supports_semantic_contract_torsion_with_discovery(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Perform a bounded torsion follow-up to distinguish torsion sensitivity without changing the global mechanism.
            </task_understanding>
            <reasoning_summary>
            Request rotatable-dihehdral discovery first, then one bounded torsion execution with exact angle and state constraints.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability cannot perform full torsion scans or excited-state relaxation.
            </capability_limit_note>
            <expected_outputs>
            snapshot geometry labels
            snapshot vertical-state proxies
            torsion sensitivity summary
            </expected_outputs>
            <failure_policy>
            If no suitable dihedral can be found, return a local failed microscopic report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Collect torsion-sensitive microscopic evidence with exact bounded constraints.
            execution_action=run_torsion_snapshots
            discovery_actions=list_rotatable_dihedrals
            requested_route_summary=Discover one relevant dihedral and run a bounded torsion follow-up.
            requested_deliverables=torsion sensitivity summary | vertical excited-state manifold characterization
            unsupported_requests=full torsion scan
            param.perform_new_calculation=true
            param.optimize_ground_state=false
            param.snapshot_count=2
            param.angle_offsets_deg=25,-25
            param.state_window=1,2,3
            param.honor_exact_target=true
            param.allow_fallback=false
            param.exclude_dihedral_ids=dih_0_1_2_3
            param.prefer_adjacent_to_nsnc_core=true
            param.min_relevance=high
            param.include_peripheral=false
            param.preferred_bond_types=aryl-vinyl | heteroaryl-linkage
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use a bounded torsion follow-up, do not re-optimize, and preserve the exact +/-25 degree snapshots.",
        current_hypothesis="TICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="torsion-follow-up",
            objective="Collect torsion-sensitive microscopic evidence.",
        ),
        case_id="case123",
        round_index=2,
    )

    plan = report.structured_results["execution_plan"]
    calls = plan["microscopic_tool_plan"]["calls"]
    assert report.structured_results["reasoning_parse_mode"] == "semantic_contract"
    assert plan["capability_route"] == "torsion_snapshot_follow_up"
    assert plan["microscopic_tool_request"]["capability_name"] == "run_torsion_snapshots"
    assert plan["microscopic_tool_request"]["optimize_ground_state"] is False
    assert plan["microscopic_tool_request"]["snapshot_count"] == 2
    assert plan["microscopic_tool_request"]["angle_offsets_deg"] == [25.0, -25.0]
    assert calls[0]["call_kind"] == "discovery"
    assert calls[0]["request"]["capability_name"] == "list_rotatable_dihedrals"
    assert calls[1]["call_kind"] == "execution"
    assert report.structured_results["unsupported_requests"] == ["full torsion scan"]


def test_semantic_contract_is_not_reinterpreted_from_task_text(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Reuse an existing torsion artifact bundle and perform parse-only microscopic extraction.
            </task_understanding>
            <reasoning_summary>
            Keep the task parse-only and preserve the semantic selection contract exactly as written.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability can parse existing snapshot bundles but cannot create new evidence in this route.
            </capability_limit_note>
            <expected_outputs>
            per-snapshot excitation energies
            per-snapshot oscillator strengths
            state-ordering records
            </expected_outputs>
            <failure_policy>
            If no canonical artifact bundle is discoverable, return a local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Extract parse-only microscopic evidence from a selected artifact bundle.
            execution_action=parse_snapshot_outputs
            discovery_actions=list_artifact_bundles
            requested_route_summary=Reuse a discovered torsion artifact bundle without new calculations.
            requested_deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            unsupported_requests=
            param.perform_new_calculation=false
            param.reuse_existing_artifacts_only=true
            param.state_window=1,2,3
            param.artifact_kind=torsion_snapshots
            param.source_round_selector=round_02
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Use a torsion follow-up with a central NSNC-adjacent dihedral, include peripheral candidates, "
            "and prefer the latest available round if possible."
        ),
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="semantic-contract-source-of-truth",
            objective="Ensure the semantic contract remains the single source of truth.",
        ),
        case_id="case123",
        round_index=3,
    )

    plan = report.structured_results["execution_plan"]
    assert plan["capability_route"] == "artifact_parse_only"
    assert plan["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"
    assert plan["microscopic_tool_request"]["source_round_preference"] == 2
    assert plan["microscopic_tool_plan"]["selection_policy"]["source_round_preference"] == 2
    assert plan["microscopic_tool_plan"]["selection_policy"]["artifact_kind"] == "torsion_snapshots"
    assert plan["microscopic_tool_plan"]["calls"][0]["request"]["capability_name"] == "list_artifact_bundles"


def test_openai_microscopic_supports_semantic_contract_parse_only_and_selector_normalization(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Reuse an existing torsion artifact bundle and perform parse-only microscopic extraction.
            </task_understanding>
            <reasoning_summary>
            Request artifact-bundle discovery and keep the route parse-only with no new calculations.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability can parse existing snapshot bundles but cannot create new evidence in this route.
            </capability_limit_note>
            <expected_outputs>
            per-snapshot excitation energies
            per-snapshot oscillator strengths
            state-ordering records
            </expected_outputs>
            <failure_policy>
            If no canonical artifact bundle is discoverable, return a local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Extract parse-only microscopic evidence from an existing torsion bundle.
            execution_action=parse_snapshot_outputs
            discovery_actions=list_artifact_bundles
            requested_route_summary=Reuse a discovered torsion artifact bundle without new calculations.
            requested_deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            unsupported_requests=
            param.perform_new_calculation=false
            param.reuse_existing_artifacts_only=true
            param.state_window=1,2,3
            param.artifact_kind=torsion_snapshots
            param.source_round_selector=round_02
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Do not run new calculations. Reuse round 2 torsion outputs and extract per-snapshot records only.",
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="parse-only-follow-up",
            objective="Reuse existing torsion snapshot artifacts without new calculations.",
        ),
        case_id="case123",
        round_index=3,
    )

    plan = report.structured_results["execution_plan"]
    assert report.structured_results["reasoning_parse_mode"] == "semantic_contract"
    assert plan["capability_route"] == "artifact_parse_only"
    assert plan["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"
    assert plan["microscopic_tool_request"]["perform_new_calculation"] is False
    assert plan["microscopic_tool_request"]["reuse_existing_artifacts_only"] is True
    assert plan["microscopic_tool_request"]["source_round_preference"] == 2
    assert plan["microscopic_tool_plan"]["selection_policy"]["source_round_preference"] == 2
    assert plan["microscopic_tool_plan"]["calls"][0]["request"]["capability_name"] == "list_artifact_bundles"


def test_semantic_contract_explicit_target_skips_discovery(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Perform a bounded torsion follow-up on an explicitly provided dihedral target.
            </task_understanding>
            <reasoning_summary>
            Use the explicit dihedral target directly and avoid extra discovery.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability remains bounded to low-cost torsion follow-up only.
            </capability_limit_note>
            <expected_outputs>
            snapshot geometry labels
            torsion sensitivity summary
            </expected_outputs>
            <failure_policy>
            If torsion execution fails, return a local failed microscopic report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Run a bounded torsion follow-up on an explicit dihedral target.
            execution_action=run_torsion_snapshots
            requested_route_summary=Use the explicit dihedral target directly.
            requested_deliverables=torsion sensitivity summary
            unsupported_requests=
            param.perform_new_calculation=true
            param.snapshot_count=3
            param.dihedral_id=dih_0_1_2_3
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use explicit dihedral target [0, 1, 2, 3] for a bounded torsion follow-up.",
        current_hypothesis="TICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="explicit-dihedral",
            objective="Use an explicit dihedral target.",
        ),
        case_id="case123",
        round_index=2,
    )

    calls = report.structured_results["execution_plan"]["microscopic_tool_plan"]["calls"]
    assert len(calls) == 1
    assert calls[0]["call_kind"] == "execution"
    assert calls[0]["request"]["dihedral_id"] == "dih_0_1_2_3"


def test_semantic_contract_multi_target_instruction_contracts_to_single_execution(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Compare torsion sensitivity on the most important conjugation-breaking target.
            </task_understanding>
            <reasoning_summary>
            Use one bounded torsion route with rotatable-dihehdral discovery and preserve the task as a single execution capability.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability does not execute multiple torsion targets in one microscopic round.
            </capability_limit_note>
            <expected_outputs>
            torsion sensitivity summary
            </expected_outputs>
            <failure_policy>
            If torsion execution fails, return a local failed microscopic report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Collect bounded torsion-sensitive evidence for the primary discriminative target.
            execution_action=run_torsion_snapshots
            discovery_actions=list_rotatable_dihedrals
            requested_route_summary=Contract the task to one bounded torsion execution target.
            requested_deliverables=torsion sensitivity summary
            unsupported_requests=
            param.perform_new_calculation=true
            param.snapshot_count=3
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run torsion snapshots on two selected rotatable dihedrals that are most central to conjugation.",
        current_hypothesis="TICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="contracted-multi-target",
            objective="Contract multi-target torsion requests to one bounded execution target.",
        ),
        case_id="case123",
        round_index=2,
    )

    assert report.task_completion_status == "contracted"
    assert report.structured_results["completion_reason_code"] == "partial_observable_only"
    unmet_constraints = report.structured_results["unmet_constraints"]
    assert any("multiple torsion targets" in item for item in unmet_constraints)


def test_semantic_contract_placeholder_target_returns_local_failed_report(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Perform a torsion follow-up after discovery.
            </task_understanding>
            <reasoning_summary>
            Use a placeholder target after discovery.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability requires stable IDs or semantic discovery requests.
            </capability_limit_note>
            <expected_outputs>
            torsion sensitivity summary
            </expected_outputs>
            <failure_policy>
            If planning fails, return a local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Collect torsion-sensitive evidence.
            execution_action=run_torsion_snapshots
            requested_route_summary=Use a placeholder target.
            requested_deliverables=torsion sensitivity summary
            unsupported_requests=
            param.dihedral_id=to_be_selected_after_call_1
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run torsion snapshots on a selected dihedral.",
        current_hypothesis="TICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="invalid-placeholder",
            objective="Reject placeholder targets in semantic contracts.",
        ),
        case_id="case123",
        round_index=2,
    )

    assert report.status == "failed"
    assert report.completion_reason_code == "action_not_supported_by_registry"
    assert report.structured_results["reasoning_parse_mode"] == "failed"
    assert report.structured_results["reasoning_contract_mode"] == "failed"
    assert report.structured_results["registry_infeasible_for_verifier_handshake"] is True
    assert any("Placeholder target values are not allowed" in item for item in report.structured_results["reasoning_contract_errors"])


def test_registry_blocked_raw_artifact_inspection_fails_fast_without_tool_execution(tmp_path: Path) -> None:
    counting_tool = _CountingAmespTool()
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            The Planner asked to inspect baseline evidence for CT-sensitive follow-up.
            </task_understanding>
            <reasoning_summary>
            Reuse a canonical artifact bundle and parse it without new calculations.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability is bounded to registry-backed parse-only reuse.
            </capability_limit_note>
            <expected_outputs>
            parsed snapshot summaries
            </expected_outputs>
            <failure_policy>
            If parsing is not possible, return a local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Reuse baseline artifacts for local inspection.
            execution_action=parse_snapshot_outputs
            discovery_actions=list_artifact_bundles
            requested_route_summary=Reuse a discovered baseline artifact bundle without new calculations.
            requested_deliverables=state-ordering summaries | CT/localization proxy
            unsupported_requests=
            param.perform_new_calculation=false
            param.reuse_existing_artifacts_only=true
            param.state_window=1,2,3
            param.artifact_kind=baseline_bundle
            param.source_round_selector=latest_available
            </microscopic_semantic_contract>
            """
        ],
        amesp_tool=counting_tool,
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Do not call parse_snapshot_outputs. Directly inspect the raw baseline output files and raw AOP/MO files "
            "to extract any CT-sensitive observables."
        ),
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="raw-artifact-inspection",
            objective="Request direct raw artifact inspection rather than registry-backed parsing.",
        ),
        case_id="case123",
        round_index=3,
    )

    assert report.status == "failed"
    assert report.completion_reason_code == "action_not_supported_by_registry"
    assert report.structured_results["registry_infeasible_for_verifier_handshake"] is True
    assert report.structured_results["registry_validation_errors"] == [
        "Planner requested unsupported registry-blocked microscopic task(s): raw artifact inspection."
    ]
    assert report.structured_results["executed_capability"] is None
    assert counting_tool.execute_calls == 0


def test_tagged_semantic_contract_parser_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        _parse_tagged_microscopic_reasoning_response(
            """
            <task_understanding>Test.</task_understanding>
            <reasoning_summary>Test.</reasoning_summary>
            <capability_limit_note>Test.</capability_limit_note>
            <expected_outputs>
            output one
            </expected_outputs>
            <failure_policy>Test.</failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Test goal
            execution_action=run_baseline_bundle
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            forbidden_key=oops
            </microscopic_semantic_contract>
            """
        )


def test_tagged_action_card_parser_rejects_unknown_param() -> None:
    with pytest.raises(ValueError):
        _parse_tagged_microscopic_reasoning_response(
            """
            <task_understanding>Test.</task_understanding>
            <reasoning_summary>Test.</reasoning_summary>
            <capability_limit_note>Test.</capability_limit_note>
            <expected_outputs>
            output one
            </expected_outputs>
            <failure_policy>Test.</failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Test goal
            execution_action=run_baseline_bundle
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            param.unknown_param=oops
            </microscopic_semantic_contract>
            """
        )


def test_tagged_action_card_parser_rejects_python_owned_param() -> None:
    with pytest.raises(ValueError):
        _parse_tagged_microscopic_reasoning_response(
            """
            <task_understanding>Test.</task_understanding>
            <reasoning_summary>Test.</reasoning_summary>
            <capability_limit_note>Test.</capability_limit_note>
            <expected_outputs>
            output one
            </expected_outputs>
            <failure_policy>Test.</failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Test goal
            execution_action=run_baseline_bundle
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            param.structure_source=shared_prepared_structure
            </microscopic_semantic_contract>
            """
        )


def test_tagged_action_card_parser_rejects_illegal_enum_value() -> None:
    with pytest.raises(ValueError):
        _parse_tagged_microscopic_reasoning_response(
            """
            <task_understanding>Test.</task_understanding>
            <reasoning_summary>Test.</reasoning_summary>
            <capability_limit_note>Test.</capability_limit_note>
            <expected_outputs>
            output one
            </expected_outputs>
            <failure_policy>Test.</failure_policy>
            <microscopic_semantic_contract>
            contract_version=2
            local_goal=Test goal
            execution_action=run_torsion_snapshots
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            param.preferred_bond_types=aryl-heteroaryl
            </microscopic_semantic_contract>
            """
        )


def test_openai_microscopic_supports_legacy_semantic_contract_fallback(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Reuse an existing torsion artifact bundle and perform parse-only microscopic extraction.
            </task_understanding>
            <reasoning_summary>
            Request artifact-bundle discovery and keep the route parse-only with no new calculations.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability can parse existing snapshot bundles but cannot create new evidence in this route.
            </capability_limit_note>
            <expected_outputs>
            per-snapshot excitation energies
            per-snapshot oscillator strengths
            state-ordering records
            </expected_outputs>
            <failure_policy>
            If no canonical artifact bundle is discoverable, return a local failed report.
            </failure_policy>
            <microscopic_semantic_contract>
            contract_version=1
            local_goal=Extract parse-only microscopic evidence from an existing torsion bundle.
            primary_capability=parse_snapshot_outputs
            needs_discovery=artifact_bundles
            target_object_kind=artifact_bundle
            requested_route_summary=Reuse a discovered torsion artifact bundle without new calculations.
            requested_deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            unsupported_requests=
            constraint.perform_new_calculation=false
            constraint.reuse_existing_artifacts_only=true
            constraint.state_window=1,2,3
            selection.artifact_kind=torsion_snapshots
            selection.source_round_selector=round_02
            </microscopic_semantic_contract>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Do not run new calculations. Reuse round 2 torsion outputs and extract per-snapshot records only.",
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="legacy-semantic-contract-follow-up",
            objective="Exercise legacy semantic contract fallback.",
        ),
        case_id="case123",
        round_index=3,
    )

    assert report.structured_results["reasoning_parse_mode"] == "legacy_semantic_contract_fallback"
    assert report.structured_results["execution_plan"]["capability_route"] == "artifact_parse_only"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"


def test_openai_microscopic_supports_legacy_tagged_protocol_fallback(tmp_path: Path) -> None:
    agent, _ = _build_agent(
        tmp_path,
        [
            """
            <task_understanding>
            Reuse an existing torsion artifact bundle and perform parse-only microscopic extraction without new calculations.
            </task_understanding>
            <reasoning_summary>
            Discover the correct artifact bundle first, then run parse_snapshot_outputs on that bundle only.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability can parse existing bounded snapshot outputs but cannot create new evidence in this path.
            </capability_limit_note>
            <expected_outputs>
            per-snapshot excitation energies
            per-snapshot oscillator strengths
            state-ordering records
            artifact reuse note
            </expected_outputs>
            <failure_policy>
            If no canonical artifact bundle is discoverable, return a local precondition-missing report.
            </failure_policy>
            <microscopic_protocol>
            protocol_version=1
            local_goal=Extract parse-only microscopic evidence from an existing torsion bundle.
            structure_strategy=reuse_if_available_else_prepare_from_smiles
            requested_route_summary=Reuse a discovered torsion artifact bundle without new calculations.
            requested_deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            unsupported_requests=
            call.1.kind=discovery
            call.1.capability_name=list_artifact_bundles
            call.1.artifact_kind=torsion_snapshots
            call.1.source_round_preference=latest
            call.2.kind=execution
            call.2.capability_name=parse_snapshot_outputs
            call.2.perform_new_calculation=false
            call.2.optimize_ground_state=false
            call.2.reuse_existing_artifacts_only=true
            call.2.artifact_kind=torsion_snapshots
            call.2.state_window=1,2,3
            call.2.deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            call.2.budget_profile=balanced
            call.2.requested_route_summary=Parse the selected torsion artifact bundle only.
            selection.artifact_kind=torsion_snapshots
            selection.source_round_preference=latest
            </microscopic_protocol>
            """
        ],
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Do not run new calculations. Reuse the latest torsion outputs and extract per-snapshot records only.",
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="legacy-tagged-follow-up",
            objective="Exercise legacy tagged protocol fallback.",
        ),
        case_id="case123",
        round_index=3,
    )

    assert report.structured_results["reasoning_parse_mode"] == "legacy_tagged_protocol_fallback"
    assert report.structured_results["execution_plan"]["capability_route"] == "artifact_parse_only"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"
