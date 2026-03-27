from __future__ import annotations

from aie_mas.agents.result_agents import MacroAgent, VerifierAgent


class _FakeVerifierTool:
    name = "verifier_evidence_lookup"

    def invoke(
        self,
        *,
        smiles: str,
        current_hypothesis: str,
        task_received: str,
        main_gap: str,
        molecule_identity_context,
        latest_macro_report,
        latest_microscopic_report,
    ):
        del smiles, task_received, main_gap, molecule_identity_context, latest_macro_report, latest_microscopic_report
        return {
            "status": "success",
            "source_count": 1,
            "verifier_target_pair": f"{current_hypothesis}__vs__unknown",
            "verifier_supplement_status": "sufficient",
            "verifier_information_gain": "medium",
            "verifier_evidence_relation": "supports_top1",
            "verifier_supplement_summary": "Test-only verifier supplement is available.",
            "evidence_cards": [
                {
                    "card_id": "test-verifier-card",
                    "source": "test_source",
                    "title": "Test verifier evidence",
                    "doi": None,
                    "url": None,
                    "observation": f"Retrieved external material discusses {current_hypothesis} in related AIE context.",
                    "topic_tags": ["restriction"],
                    "evidence_kind": "external_summary",
                    "why_relevant": "Test-only evidence card.",
                    "query_group": "similar_family",
                    "match_level": "same_family",
                    "mechanism_claim": None,
                    "experimental_context": None,
                }
            ],
            "queried_hypothesis": current_hypothesis,
            "retrieval_note": "Test-only verifier retrieval completed.",
            "raw_response": {"evidence_cards": 1},
            "queries_executed": [{"query_group": "similar_family", "query": "test query"}],
            "query_groups_attempted": ["exact_identity", "similar_family", "mechanistic_discriminator"],
            "query_groups_with_hits": ["similar_family"],
        }


def test_macro_agent_returns_specialized_local_report(install_specialized_test_doubles) -> None:
    install_specialized_test_doubles()
    agent = MacroAgent()
    report = agent.run(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        task_received=(
            "Assess macro-level structural evidence relevant to the current working hypothesis "
            "'restriction of intramolecular motion (RIM)-dominated AIE'. Summarize low-cost structural indicators only."
        ),
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
    )

    assert report.task_understanding
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.task_completion_status == "completed"
    assert "Task completed successfully" in report.task_completion
    assert report.structured_results["aromatic_atom_count"] >= 1
    assert report.planner_readable_report.startswith("Task completion:")
    assert "global mechanism judgment" in report.task_understanding
    assert "Task understanding:" in report.planner_readable_report


def test_verifier_agent_returns_specialized_local_report() -> None:
    agent = VerifierAgent(tool=_FakeVerifierTool())
    report = agent.run(
        smiles="C(c1ccccc1)(c1ccccc1)=C(c1ccccc1)c1ccccc1",
        current_hypothesis="restriction of intramolecular motion (RIM)-dominated AIE",
        task_received=(
            "Retrieve external supervision evidence for the current working hypothesis "
            "'restriction of intramolecular motion (RIM)-dominated AIE' and clarify the current gap."
        ),
        main_gap="Clarify the remaining external evidence gap.",
    )

    assert report.task_understanding
    assert report.execution_plan
    assert report.result_summary
    assert report.remaining_local_uncertainty
    assert report.task_completion_status == "completed"
    assert "retrieving raw verifier evidence" in report.task_completion
    assert report.structured_results["source_count"] >= 1
    assert report.structured_results["verifier_supplement_status"] == "sufficient"
    assert report.structured_results["evidence_cards"]
    assert "topic_tags" in report.structured_results["evidence_cards"][0]
    assert report.planner_readable_report.startswith("Task completion:")
    assert "Task understanding:" in report.planner_readable_report
