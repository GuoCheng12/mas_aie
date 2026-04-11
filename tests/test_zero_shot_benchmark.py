from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aie_mas.cli.benchmark_zero_shot import app
from aie_mas.config import AieMasConfig
from aie_mas.evaluation.zero_shot_benchmark import ZeroShotPredictor
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


def test_zero_shot_predictor_normalizes_pool_and_reasoning(tmp_path: Path) -> None:
    fake_client = _FakeClient(
        [
            json.dumps(
                {
                    "hypothesis_pool": [
                        {"name": "ICT", "confidence": 0.7, "rationale": "Donor-acceptor layout is evident."},
                        {"name": "neutral_aromatic", "confidence": 0.2, "rationale": "Large aromatic core still matters."},
                    ],
                    "current_hypothesis": "ICT",
                    "confidence": 0.7,
                    "reasoning_summary": "ICT leads from the SMILES-only read. Neutral aromatic remains the main fallback.",
                    "hypothesis_reweight_explanation": {
                        "ICT": "Charge-transfer-like architecture is visible.",
                        "neutral aromatic": "Aromatic core remains relevant.",
                    },
                }
            )
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
    predictor = ZeroShotPredictor(
        config=config,
        prompt_repo=PromptRepository(PROMPTS_DIR),
        client=OpenAICompatiblePlannerClient(config, client=fake_client),
        structure_summary_provider=lambda smiles, label: {
            "structure_source": "shared_prepared_structure",
            "canonical_smiles": smiles,
            "label": label,
            "rotatable_bond_count": 4,
            "aromatic_ring_count": 3,
            "ring_system_count": 2,
            "hetero_atom_count": 2,
            "branch_point_count": 5,
            "donor_acceptor_partition_proxy": 0.5,
            "planarity_proxy": 0.81,
            "compactness_proxy": 0.42,
            "torsion_candidate_count": 4,
            "principal_span_proxy": 10.2,
            "conformer_dispersion_proxy": 0.3,
        },
    )

    result = predictor.predict("C1=CC=CC=C1")

    assert result["predicted_top1"] == "ICT"
    assert result["predicted_top2"] == "neutral aromatic"
    pool = json.loads(result["hypothesis_pool_json"])
    assert {entry["name"] for entry in pool} == {"ICT", "TICT", "ESIPT", "neutral aromatic", "unknown"}
    assert "Neutral aromatic remains the main fallback" in result["reasoning_summary"]
    assert fake_client.chat.completions.calls[0]["model"] == "gpt-4.1-mini"
    prompt_payload = fake_client.chat.completions.calls[0]["messages"][1]["content"]
    assert "STRUCTURE SUMMARY" in prompt_payload
    assert "rotatable_bond_count" in prompt_payload


def test_zero_shot_cli_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    from aie_mas.cli import benchmark_zero_shot as module

    class _StubPredictor:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def predict(self, smiles: str, *, label: str | None = None) -> dict[str, object]:
            del smiles, label
            return {
                "predicted_top1": "ICT",
                "predicted_confidence": 0.61,
                "predicted_top2": "TICT",
                "predicted_top2_confidence": 0.21,
                "reasoning_summary": "ICT leads from the zero-shot prompt.",
                "hypothesis_pool_json": json.dumps(
                    [
                        {"name": "ICT", "confidence": 0.61},
                        {"name": "TICT", "confidence": 0.21},
                        {"name": "neutral aromatic", "confidence": 0.1},
                        {"name": "ESIPT", "confidence": 0.05},
                        {"name": "unknown", "confidence": 0.03},
                    ]
                ),
                "hypothesis_reweight_explanation": {},
            }

    monkeypatch.setattr(module, "ZeroShotPredictor", _StubPredictor)

    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "id,code,SMILES,mechanism_id\n1,test_case,C1=CC=CC=C1,ICT\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(tmp_path / "zero_shot_out"),
            "--model",
            "gpt-4.1-mini",
        ],
    )

    assert result.exit_code == 0
    assert "top1_accuracy" in result.stdout
    assert (tmp_path / "zero_shot_out" / "case_results.csv").exists()
    assert (tmp_path / "zero_shot_out" / "metrics.json").exists()
