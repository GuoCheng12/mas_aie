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
                                }
                            ],
                            "first_excitation_energy_ev": 3.347,
                            "first_oscillator_strength": 0.245,
                            "state_count": 2,
                        },
                    },
                )(),
                "route_records": [],
                "route_summary": {"state_count": 2},
                "raw_step_results": {"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
                "generated_artifacts": {"prepared_xyz_path": "/tmp/prepared_structure.xyz", "s0_aop_path": "/tmp/s0.aop"},
            },
        )()


def test_openai_microscopic_reasoning_backend_uses_configured_model(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "task_understanding": "Collect bounded local microscopic evidence for the current working hypothesis using Amesp baseline execution only.",
              "reasoning_summary": "Reuse or prepare a 3D structure, run S0 optimization, then run S1 vertical excitation, and keep unsupported tasks out of scope.",
              "execution_plan": {
                "local_goal": "Collect bounded microscopic evidence with Amesp baseline execution.",
                        "requested_deliverables": [
                          "S0 geometry optimization",
                          "S1 vertical excitation characterization",
                          "dipole summary"
                        ],
                        "capability_route": "baseline_bundle",
                        "requested_route_summary": "Use the default low-cost baseline bundle.",
                        "microscopic_tool_request": {
                          "capability_name": "run_baseline_bundle",
                          "perform_new_calculation": true,
                          "reuse_existing_artifacts_only": false,
                          "artifact_source_round": null,
                          "artifact_scope": null,
                          "snapshot_count": null,
                          "angle_offsets_deg": [],
                          "state_window": [1, 2],
                          "deliverables": [
                            "S0 geometry optimization",
                            "S1 vertical excitation characterization",
                            "dipole summary"
                          ],
                          "budget_profile": "balanced",
                          "requested_route_summary": "Use the default low-cost baseline bundle."
                        },
                        "structure_strategy": "prepare_from_smiles",
                        "step_sequence": [
                          "structure_prep",
                  "s0_optimization",
                  "s1_vertical_excitation"
                ],
                "unsupported_requests": [
                  "torsion scan"
                ]
              },
              "capability_limit_note": "Current capability is restricted to baseline S0 and S1 tasks only.",
              "expected_outputs": [
                "S0 optimized geometry",
                "S0 dipole",
                "S1 first oscillator strength"
              ],
              "failure_policy": "Return a local failed or partial report if Amesp fails."
            }
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use Amesp to optimize S0, summarize the dipole, characterize S1, and also do a torsion scan if possible.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        recent_rounds_context=[{"round_id": 1, "action_taken": "macro, microscopic", "main_gap": "Need more microscopic evidence."}],
        shared_structure_context=SharedStructureContext(
            input_smiles="C1=CCCCC1",
            canonical_smiles="C1=CCCCC1",
            charge=0,
            multiplicity=1,
            atom_count=16,
            conformer_count=2,
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
            planarity_proxy=0.6,
            compactness_proxy=0.4,
            torsion_candidate_count=2,
            principal_span_proxy=6.0,
            conformer_dispersion_proxy=0.4,
        ),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Use Amesp to optimize S0 and characterize S1.",
        ),
        case_id="case123",
        round_index=1,
    )

    assert report.structured_results["reasoning"]["task_understanding"].startswith("Collect bounded local microscopic evidence")
    assert report.reasoning_summary
    assert report.structured_results["reasoning"]["capability_limit_note"] == "Current capability is restricted to baseline S0 and S1 tasks only."
    assert report.structured_results["reasoning_parse_mode"] == "legacy_json_fallback"
    assert report.structured_results["execution_plan"]["steps"][2]["step_type"] == "s1_vertical_excitation"
    assert report.structured_results["unsupported_requests"] == ["torsion scan"]
    assert report.structured_results["execution_plan"]["capability_route"] == "baseline_bundle"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "run_baseline_bundle"
    assert report.structured_results["vertical_state_manifold"]["state_count"] == 2
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "recent_rounds_context" in message_payload
    assert "available_structure_context" in message_payload
    assert "shared_structure_context" in message_payload
    assert "runtime_context" in message_payload


def test_openai_microscopic_reasoning_supports_tagged_protocol_torsion_follow_up(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            <task_understanding>
            Perform a bounded torsion follow-up for the current microscopic task and preserve the exact Planner constraints.
            </task_understanding>
            <reasoning_summary>
            First discover the best rotatable dihedral, then execute a single torsion-snapshot follow-up with exact snapshot and angle controls.
            </reasoning_summary>
            <capability_limit_note>
            Current Amesp capability is bounded to low-cost discovery plus torsion follow-up and does not support global mechanism adjudication.
            </capability_limit_note>
            <expected_outputs>
            snapshot geometry labels
            snapshot vertical-state proxies
            torsion sensitivity summary
            </expected_outputs>
            <failure_policy>
            If no suitable dihedral can be discovered, return a local failed or partial microscopic report.
            </failure_policy>
            <microscopic_protocol>
            protocol_version=1
            local_goal=Collect torsion-sensitive microscopic evidence with exact Planner constraints.
            structure_strategy=reuse_if_available_else_prepare_from_smiles
            requested_route_summary=Use discovery plus a single torsion follow-up execution.
            requested_deliverables=torsion sensitivity summary | vertical excited-state manifold characterization
            unsupported_requests=
            call.1.kind=discovery
            call.1.capability_name=list_rotatable_dihedrals
            call.1.structure_source=round_s0_optimized_geometry
            call.1.min_relevance=high
            call.1.include_peripheral=false
            call.2.kind=execution
            call.2.capability_name=run_torsion_snapshots
            call.2.snapshot_count=2
            call.2.angle_offsets_deg=25,-25
            call.2.state_window=1,2,3
            call.2.perform_new_calculation=true
            call.2.optimize_ground_state=false
            call.2.honor_exact_target=true
            call.2.allow_fallback=false
            call.2.deliverables=torsion sensitivity summary | vertical excited-state manifold characterization
            call.2.budget_profile=balanced
            call.2.requested_route_summary=Run the bounded torsion execution after discovery.
            selection.exclude_dihedral_ids=dih_0_1_2_3
            selection.prefer_adjacent_to_nsnc_core=true
            selection.min_relevance=high
            selection.include_peripheral=false
            selection.preferred_bond_types=aryl-vinyl | heteroaryl-linkage
            </microscopic_protocol>
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Use a bounded torsion follow-up, do not re-optimize, avoid the old dihedral, and preserve the exact ±25 degree snapshots."
        ),
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
    assert report.structured_results["reasoning_parse_mode"] == "tagged_protocol"
    assert plan["capability_route"] == "torsion_snapshot_follow_up"
    assert plan["microscopic_tool_request"]["capability_name"] == "run_torsion_snapshots"
    assert plan["microscopic_tool_request"]["optimize_ground_state"] is False
    assert plan["microscopic_tool_request"]["snapshot_count"] == 2
    assert plan["microscopic_tool_request"]["angle_offsets_deg"] == [25.0, -25.0]
    assert plan["microscopic_tool_plan"]["calls"][0]["call_kind"] == "discovery"
    assert plan["microscopic_tool_plan"]["calls"][1]["call_kind"] == "execution"
    assert "response_format" not in fake_client.chat.completions.calls[0]


def test_openai_microscopic_reasoning_route_is_taken_from_llm_not_keyword_fallback(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "task_understanding": "Perform a bounded torsion snapshot follow-up using the explicitly requested route.",
              "reasoning_summary": "The instruction explicitly requests torsion_snapshot_follow_up and explicitly forbids excited_state_relaxation_follow_up, so the torsion route should be used.",
              "execution_plan": {
                "local_goal": "Collect torsion-sensitivity evidence with bounded snapshots.",
                "requested_deliverables": [
                  "torsion-sensitivity summary",
                  "vertical excited-state manifold characterization"
                ],
                "capability_route": "torsion_snapshot_follow_up",
                "requested_route_summary": "Use the explicitly requested torsion_snapshot_follow_up route.",
                "microscopic_tool_request": {
                  "capability_name": "run_torsion_snapshots",
                  "perform_new_calculation": true,
                  "reuse_existing_artifacts_only": false,
                  "artifact_source_round": null,
                  "artifact_scope": "torsion_snapshots",
                  "snapshot_count": 2,
                  "angle_offsets_deg": [25.0, -25.0],
                  "state_window": [1, 2, 3],
                  "deliverables": [
                    "torsion-sensitivity summary",
                    "vertical excited-state manifold characterization"
                  ],
                  "budget_profile": "balanced",
                  "requested_route_summary": "Use the explicitly requested torsion snapshot capability."
                },
                "structure_strategy": "reuse_if_available_else_prepare_from_smiles",
                "step_sequence": [
                  "torsion_snapshot_generation",
                  "s0_optimization",
                  "s1_vertical_excitation"
                ],
                "unsupported_requests": []
              },
              "capability_limit_note": "Use the supported torsion snapshot route only.",
              "expected_outputs": [
                "snapshot geometry labels",
                "snapshot vertical-state proxies",
                "torsion sensitivity summary"
              ],
              "failure_policy": "Return a local failed or partial report if Amesp fails."
            }
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "IMPORTANT: execute the supported Amesp route 'torsion_snapshot_follow_up'. "
            "Do NOT use 'excited_state_relaxation_follow_up'. "
            "Generate torsion snapshots and compute bounded vertical excitations."
        ),
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="round-2-targeted",
            objective="Use the explicitly requested torsion snapshot route.",
        ),
        case_id="case123",
        round_index=2,
    )

    assert report.structured_results["execution_plan"]["capability_route"] == "torsion_snapshot_follow_up"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "run_torsion_snapshots"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["snapshot_count"] == 2
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["angle_offsets_deg"] == [25.0, -25.0]
    assert report.structured_results["attempted_route"] == "torsion_snapshot_follow_up"


def test_openai_microscopic_reasoning_accepts_capability_name_in_compatibility_route(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "task_understanding": "Reuse existing torsion snapshot artifacts and parse them without new calculations.",
              "reasoning_summary": "The instruction explicitly requests parse_snapshot_outputs and no new calculations.",
              "execution_plan": {
                "local_goal": "Parse existing torsion snapshot outputs.",
                "requested_deliverables": [
                  "per-snapshot excitation energies",
                  "per-snapshot oscillator strengths",
                  "state-ordering records"
                ],
                "capability_route": "parse_snapshot_outputs",
                "requested_route_summary": "Use parse_snapshot_outputs on an existing torsion bundle.",
                "microscopic_tool_request": {
                  "capability_name": "parse_snapshot_outputs",
                  "perform_new_calculation": false,
                  "optimize_ground_state": false,
                  "reuse_existing_artifacts_only": true,
                  "artifact_bundle_id": "round_02_torsion_snapshots",
                  "artifact_scope": "torsion_snapshots",
                  "state_window": [1, 2, 3],
                  "deliverables": [
                    "per-snapshot excitation energies",
                    "per-snapshot oscillator strengths",
                    "state-ordering records"
                  ],
                  "budget_profile": "balanced",
                  "requested_route_summary": "Use parse_snapshot_outputs on an existing torsion bundle."
                },
                "structure_strategy": "reuse_if_available_else_prepare_from_smiles",
                "step_sequence": [
                  "artifact_parse"
                ],
                "unsupported_requests": []
              },
              "capability_limit_note": "Current capability supports parse-only artifact reuse for existing torsion bundles.",
              "expected_outputs": [
                "per-snapshot excitation energies",
                "per-snapshot oscillator strengths",
                "state-ordering records"
              ],
              "failure_policy": "Return a local failed or partial report if artifact parsing fails."
            }
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received=(
            "Do not run new calculations. Reuse the existing torsion snapshot outputs and "
            "run parse_snapshot_outputs on round_02_torsion_snapshots."
        ),
        current_hypothesis="ICT",
        task_spec=MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label="parse-only-follow-up",
            objective="Reuse existing torsion snapshot artifacts without new calculations.",
        ),
        case_id="case123",
        round_index=3,
    )

    assert report.structured_results["execution_plan"]["capability_route"] == "artifact_parse_only"
    assert report.structured_results["execution_plan"]["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"
    assert report.structured_results["attempted_route"] == "artifact_parse_only"


def test_openai_microscopic_reasoning_supports_tagged_protocol_parse_only_follow_up(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            <task_understanding>
            Reuse an existing torsion artifact bundle and perform parse-only microscopic extraction without any new calculations.
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
            call.1.source_round_preference=2
            call.2.kind=execution
            call.2.capability_name=parse_snapshot_outputs
            call.2.perform_new_calculation=false
            call.2.optimize_ground_state=false
            call.2.reuse_existing_artifacts_only=true
            call.2.artifact_kind=torsion_snapshots
            call.2.artifact_source_round=2
            call.2.state_window=1,2,3
            call.2.deliverables=per-snapshot excitation energies | per-snapshot oscillator strengths | state-ordering records
            call.2.budget_profile=balanced
            call.2.requested_route_summary=Parse the selected torsion artifact bundle only.
            selection.artifact_kind=torsion_snapshots
            selection.source_round_preference=2
            </microscopic_protocol>
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
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
    assert report.structured_results["reasoning_parse_mode"] == "tagged_protocol"
    assert plan["capability_route"] == "artifact_parse_only"
    assert plan["microscopic_tool_request"]["capability_name"] == "parse_snapshot_outputs"
    assert plan["microscopic_tool_request"]["perform_new_calculation"] is False
    assert plan["microscopic_tool_request"]["reuse_existing_artifacts_only"] is True
    assert plan["microscopic_tool_plan"]["calls"][0]["request"]["capability_name"] == "list_artifact_bundles"
    assert plan["microscopic_tool_plan"]["calls"][1]["request"]["capability_name"] == "parse_snapshot_outputs"


def test_openai_microscopic_reasoning_drops_trailing_discovery_calls_after_execution(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "task_understanding": "Run the baseline bundle and ignore the accidental trailing discovery call.",
              "reasoning_summary": "The baseline execution is sufficient for this task.",
              "execution_plan": {
                "local_goal": "Collect baseline microscopic evidence.",
                "requested_deliverables": [
                  "S0 geometry optimization",
                  "S1 vertical excitation characterization"
                ],
                "capability_route": "baseline_bundle",
                "requested_route_summary": "Use the default low-cost baseline bundle.",
                "microscopic_tool_plan": {
                  "calls": [
                    {
                      "call_id": "execute_baseline",
                      "call_kind": "execution",
                      "request": {
                        "capability_name": "run_baseline_bundle",
                        "perform_new_calculation": true,
                        "reuse_existing_artifacts_only": false,
                        "state_window": [1, 2],
                        "deliverables": [
                          "S0 geometry optimization",
                          "S1 vertical excitation characterization"
                        ],
                        "budget_profile": "balanced",
                        "requested_route_summary": "Run the baseline bundle."
                      }
                    },
                    {
                      "call_id": "discover_dihedrals_after_execution",
                      "call_kind": "discovery",
                      "request": {
                        "capability_name": "list_rotatable_dihedrals",
                        "structure_source": "round_s0_optimized_geometry",
                        "requested_route_summary": "This trailing discovery call should be dropped."
                      }
                    }
                  ],
                  "requested_route_summary": "Baseline tool plan with a bad trailing discovery call.",
                  "requested_deliverables": [
                    "S0 geometry optimization",
                    "S1 vertical excitation characterization"
                  ],
                  "failure_reporting": "Return a failed or partial report if Amesp fails."
                },
                "structure_strategy": "prepare_from_smiles",
                "step_sequence": [
                  "structure_prep",
                  "s0_optimization",
                  "s1_vertical_excitation"
                ],
                "unsupported_requests": []
              },
              "capability_limit_note": "Current capability is restricted to baseline S0 and S1 tasks only.",
              "expected_outputs": [
                "S0 optimized geometry",
                "S1 first oscillator strength"
              ],
              "failure_policy": "Return a local failed or partial report if Amesp fails."
            }
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Use Amesp to optimize S0 and characterize S1.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Use Amesp to optimize S0 and characterize S1.",
        ),
        case_id="case123",
        round_index=1,
    )

    calls = report.structured_results["execution_plan"]["microscopic_tool_plan"]["calls"]
    normalization_notes = report.structured_results["execution_plan"]["microscopic_tool_plan"]["normalization_notes"]
    assert len(calls) == 1
    assert calls[0]["call_kind"] == "execution"
    assert any("Dropped trailing discovery call" in note for note in normalization_notes)


def test_openai_microscopic_tagged_protocol_recovers_aliases_and_multiple_execution_calls(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            <task_understanding>
            Perform a first-round low-cost ground-state optimization and vertical excited-state characterization with optional conformer and torsion sensitivity summaries.
            </task_understanding>
            <reasoning_summary>
            Reuse the shared prepared structure context, then emit bounded baseline, conformer, and torsion execution calls under the balanced budget profile.
            </reasoning_summary>
            <capability_limit_note>
            The Amesp microscopic capability is limited to bounded low-cost routes and cannot perform heavy full-DFT geometry optimization or excited-state relaxation.
            </capability_limit_note>
            <expected_outputs>
            low-cost aTB S0 optimized geometry
            vertical excited-state manifold characterization
            conformer-sensitivity summary
            torsion-sensitivity summary
            </expected_outputs>
            <failure_policy>
            If any local step fails, report the available partial outputs without making a mechanism judgment.
            </failure_policy>
            <microscopic_protocol>
            protocol_version=1
            local_goal=First-round low-cost S0 optimization and vertical excited-state characterization with conformer and torsion sensitivity.
            structure_strategy=prefer_shared_prepared_structure
            requested_route_summary=Run baseline low-cost aTB S0 optimization plus vertical excitations and optional bounded sensitivity analyses.
            requested_deliverables=low-cost aTB S0 geometry optimization | vertical excited-state manifold characterization | conformer-sensitivity summary | torsion-sensitivity summary
            unsupported_requests=heavy full-DFT geometry optimization
            call.1.kind=discovery
            call.1.capability_name=list_available_conformers
            call.1.structure_source=shared_prepared_structure_context
            call.1.min_relevance=high
            call.1.include_peripheral=false
            call.2.kind=discovery
            call.2.capability_name=list_rotatable_dihedrals
            call.2.structure_source=shared_prepared_structure_context
            call.2.min_relevance=high
            call.2.include_peripheral=false
            call.3.kind=execution
            call.3.capability_name=run_baseline_bundle
            call.3.structure_source=shared_prepared_structure_context
            call.3.perform_new_calculation=true
            call.3.optimize_ground_state=true
            call.3.deliverables=low-cost aTB S0 geometry optimization | vertical excited-state manifold characterization
            call.3.budget_profile=balanced
            call.3.honor_exact_target=true
            call.4.kind=execution
            call.4.capability_name=run_conformer_bundle
            call.4.conformer_ids=conformer_0,conformer_1,conformer_2
            call.4.perform_new_calculation=true
            call.4.deliverables=conformer-sensitivity summary
            call.4.budget_profile=balanced
            call.5.kind=execution
            call.5.capability_name=run_torsion_snapshots
            call.5.dihedral_id=dih_0_1_2_3
            call.5.snapshot_count=6
            call.5.angle_offsets_deg=30,60,90,120,150,180
            call.5.perform_new_calculation=true
            call.5.deliverables=torsion-sensitivity summary
            call.5.budget_profile=balanced
            selection.min_relevance=high
            selection.include_peripheral=false
            selection.preferred_bond_types=aryl-vinyl | heteroaryl-linkage
            </microscopic_protocol>
            """
        ]
    )
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
        amesp_tool=_SuccessfulAmespTool(),
        tools_work_dir=tmp_path / "tools",
        config=config,
        prompts=PromptRepository(PROMPTS_DIR),
        llm_client=OpenAICompatibleMicroscopicClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CCCCC1",
        task_received="Run first-round microscopic baseline evidence collection using the shared prepared structure.",
        current_hypothesis="neutral aromatic",
        shared_structure_context=SharedStructureContext(
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
        ),
        task_spec=MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Collect first-round microscopic baseline evidence.",
        ),
        case_id="case123",
        round_index=1,
    )

    plan = report.structured_results["execution_plan"]
    calls = plan["microscopic_tool_plan"]["calls"]
    normalization_notes = plan["microscopic_tool_plan"]["normalization_notes"]

    assert report.structured_results["reasoning_parse_mode"] == "tagged_protocol"
    assert plan["capability_route"] == "baseline_bundle"
    assert plan["microscopic_tool_request"]["capability_name"] == "run_baseline_bundle"
    assert len(calls) == 3
    assert calls[0]["call_kind"] == "discovery"
    assert calls[0]["request"]["structure_source"] == "shared_prepared_structure"
    assert calls[1]["call_kind"] == "discovery"
    assert calls[2]["call_kind"] == "execution"
    assert any("Dropped trailing execution call" in note for note in normalization_notes)


def test_tagged_microscopic_protocol_rejects_unknown_capability_name() -> None:
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
            <microscopic_protocol>
            protocol_version=1
            local_goal=Test goal
            structure_strategy=prepare_from_smiles
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            call.1.kind=execution
            call.1.capability_name=run_fake_bundle
            call.1.perform_new_calculation=true
            call.1.deliverables=output one
            call.1.budget_profile=balanced
            call.1.requested_route_summary=Test execution
            </microscopic_protocol>
            """
        )


def test_tagged_microscopic_protocol_rejects_discovery_after_execution() -> None:
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
            <microscopic_protocol>
            protocol_version=1
            local_goal=Test goal
            structure_strategy=prepare_from_smiles
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            call.1.kind=execution
            call.1.capability_name=run_baseline_bundle
            call.1.perform_new_calculation=true
            call.1.deliverables=output one
            call.1.budget_profile=balanced
            call.1.requested_route_summary=Test execution
            call.2.kind=discovery
            call.2.capability_name=list_rotatable_dihedrals
            call.2.structure_source=round_s0_optimized_geometry
            </microscopic_protocol>
            """
        )


def test_tagged_microscopic_protocol_rejects_multiple_execution_calls() -> None:
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
            <microscopic_protocol>
            protocol_version=1
            local_goal=Test goal
            structure_strategy=prepare_from_smiles
            requested_route_summary=Test summary
            requested_deliverables=output one
            unsupported_requests=
            call.1.kind=execution
            call.1.capability_name=run_baseline_bundle
            call.1.perform_new_calculation=true
            call.1.deliverables=output one
            call.1.budget_profile=balanced
            call.1.requested_route_summary=Baseline execution
            call.2.kind=execution
            call.2.capability_name=run_torsion_snapshots
            call.2.perform_new_calculation=true
            call.2.snapshot_count=2
            call.2.angle_offsets_deg=25,-25
            call.2.deliverables=output one
            call.2.budget_profile=balanced
            call.2.requested_route_summary=Torsion execution
            </microscopic_protocol>
            """
        )
