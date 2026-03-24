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
        return type(
            "RunResult",
            (),
            {
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
                        "excited_states": [type("State", (), {"total_energy_hartree": -231.0})()],
                        "first_oscillator_strength": 0.245,
                        "first_excitation_energy_ev": 3.347,
                        "state_count": 1,
                        "model_dump": lambda self, mode="json": {
                            "excited_states": [
                                {
                                    "state_index": 1,
                                    "total_energy_hartree": -231.0,
                                    "oscillator_strength": 0.245,
                                    "spin_square": 0.0,
                                    "excitation_energy_ev": 3.347,
                                }
                            ],
                            "first_excitation_energy_ev": 3.347,
                            "first_oscillator_strength": 0.245,
                            "state_count": 1,
                        },
                    },
                )(),
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
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    assert fake_client.chat.completions.calls[0]["temperature"] == 0.0
    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "recent_rounds_context" in message_payload
    assert "available_structure_context" in message_payload
    assert "shared_structure_context" in message_payload
    assert "runtime_context" in message_payload
