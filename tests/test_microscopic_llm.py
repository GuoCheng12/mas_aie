from __future__ import annotations

from pathlib import Path

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
