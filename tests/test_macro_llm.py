from __future__ import annotations

from pathlib import Path

from aie_mas.agents.macro import MacroAgent
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import SharedStructureContext
from aie_mas.llm.openai_compatible import OpenAICompatibleMacroClient
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


def _shared_structure_context(tmp_path: Path) -> SharedStructureContext:
    return SharedStructureContext(
        input_smiles="C1=CC=CC=C1",
        canonical_smiles="c1ccccc1",
        charge=0,
        multiplicity=1,
        atom_count=12,
        conformer_count=4,
        selected_conformer_id=1,
        prepared_xyz_path=str(tmp_path / "prepared.xyz"),
        prepared_sdf_path=str(tmp_path / "prepared.sdf"),
        summary_path=str(tmp_path / "summary.json"),
        rotatable_bond_count=2,
        aromatic_ring_count=2,
        ring_system_count=1,
        hetero_atom_count=1,
        branch_point_count=3,
        donor_acceptor_partition_proxy=0.5,
        planarity_proxy=0.82,
        compactness_proxy=0.41,
        torsion_candidate_count=2,
        principal_span_proxy=8.1,
        conformer_dispersion_proxy=0.63,
    )


def test_openai_macro_reasoning_backend_uses_configured_model_and_shared_context(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            """
            {
              "task_understanding": "Collect bounded macro structural evidence for the current working hypothesis using the shared prepared structure context.",
              "reasoning_summary": "Reuse the shared structure, focus on topology and geometry proxies, and keep global mechanism judgment out of scope.",
              "execution_plan": {
                "local_goal": "Collect bounded macro structural evidence only.",
                "requested_deliverables": [
                  "rotor topology summary",
                  "planarity and torsion summary"
                ],
                "focus_areas": [
                  "rotor topology",
                  "planarity and torsion"
                ],
                "unsupported_requests": [
                  "aggregate-state simulation"
                ]
              },
              "capability_limit_note": "Current macro capability is bounded to deterministic low-cost structure analysis only.",
              "expected_outputs": [
                "rotor topology",
                "planarity and torsion summary"
              ],
              "failure_policy": "Return a fallback macro report if shared structure is unavailable."
            }
            """
        ]
    )
    config = AieMasConfig(
        project_root=tmp_path,
        execution_profile="linux-prod",
        macro_backend="openai_sdk",
        macro_base_url="http://34.13.73.248:3888/v1",
        macro_model="gpt-4.1-mini",
        macro_api_key="test-key",
        prompts_dir=PROMPTS_DIR,
    )
    agent = MacroAgent(
        prompts=PromptRepository(PROMPTS_DIR),
        config=config,
        llm_client=OpenAICompatibleMacroClient(config, client=fake_client),
    )

    report = agent.run(
        smiles="C1=CC=CC=C1",
        task_received="Use the shared structure to summarize rotor topology and planarity proxies only.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        recent_rounds_context=[{"round_id": 1, "action_taken": "macro, microscopic", "main_gap": "Need richer macro evidence."}],
        shared_structure_context=_shared_structure_context(tmp_path),
        case_id="case123",
        round_index=2,
    )

    assert report.reasoning_summary
    assert report.structured_results["execution_plan"]["structure_source"] == "shared_prepared_structure"
    assert report.structured_results["unsupported_requests"] == ["aggregate-state simulation"]
    assert report.structured_results["rotor_topology"]["rotatable_bond_count"] == 2
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    message_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "recent_rounds_context" in message_payload
    assert "shared_structure_context" in message_payload
    assert "runtime_context" in message_payload


def test_macro_agent_reuses_shared_structure_context_in_mock_mode(tmp_path: Path) -> None:
    agent = MacroAgent(
        prompts=PromptRepository(PROMPTS_DIR),
        config=AieMasConfig(project_root=tmp_path, execution_profile="local-dev", prompts_dir=PROMPTS_DIR),
    )

    report = agent.run(
        smiles="C1=CC=CC=C1",
        task_received="Inspect low-cost rotor topology and compactness proxies for the current hypothesis.",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        shared_structure_context=_shared_structure_context(tmp_path),
    )

    assert report.structured_results["structure_source"] == "shared_prepared_structure"
    assert report.structured_results["prepared_xyz_path"].endswith("prepared.xyz")
    assert report.structured_results["execution_plan"]["structure_source"] == "shared_prepared_structure"
    assert "shared_xyz=" in report.tool_calls[0]
