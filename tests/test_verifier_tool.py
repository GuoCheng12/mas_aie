from __future__ import annotations

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import MoleculeIdentityContext
from aie_mas.tools.verifier import (
    OpenAIVerifierEvidenceTool,
    VerifierRetrievedCardDraft,
    VerifierRetrievalResponse,
)


class _FakeVerifierClient:
    def __init__(self, response: VerifierRetrievalResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def invoke_json_schema(self, *, messages, response_model, schema_name):
        del messages, response_model, schema_name
        if self._error is not None:
            raise self._error
        return self._response


def test_verifier_tool_normalizes_retrieved_cards() -> None:
    tool = OpenAIVerifierEvidenceTool(
        config=AieMasConfig(verifier_api_key="test-key"),
        client=_FakeVerifierClient(
            VerifierRetrievalResponse(
                retrieval_note="Search succeeded.",
                evidence_cards=[
                    VerifierRetrievedCardDraft(
                        card_id="",
                        source="journal_page",
                        title="AIE mechanism paper",
                        doi="10.1000/test",
                        url="https://example.com/paper",
                        observation="This related system shows mixed RIR and ICT behavior.",
                        topic_tags=["ICT", "heteroatom", "ICT"],
                        evidence_kind="unsupported_kind",
                        why_relevant="The scaffold is mechanistically similar.",
                        query_group="exact_identity",
                        match_level="exact_molecule",
                        mechanism_claim="Restriction of Intramolecular Rotation (RIR)",
                        experimental_context="aggregate state",
                    )
                ],
            )
        ),
    )

    result = tool.invoke(
        smiles="C1=CC=CC=C1",
        current_hypothesis="Restriction of Intramolecular Rotation (RIR)",
        task_received="Retrieve external supervision evidence for the current hypothesis.",
        main_gap="Clarify the remaining external evidence gap.",
        molecule_identity_context=MoleculeIdentityContext(
            input_smiles="C1=CC=CC=C1",
            canonical_smiles="c1ccccc1",
            molecular_formula="C6H6",
            inchi="InChI=1S/C6H6/c1-2-4-6-5-3-1/h1-6H",
            inchikey="UHOVQNZJYSORNB-UHFFFAOYSA-N",
        ),
        latest_macro_report=None,
        latest_microscopic_report=None,
    )

    assert result["status"] == "success"
    assert result["source_count"] == 1
    card = result["evidence_cards"][0]
    assert card["card_id"].startswith("verifier-card-1-")
    assert card["evidence_kind"] == "external_summary"
    assert card["topic_tags"] == ["ict", "heteroatom"]
    assert card["doi"] == "10.1000/test"
    assert card["why_relevant"] == "The scaffold is mechanistically similar."
    assert card["query_group"] == "exact_identity"
    assert card["match_level"] == "exact_molecule"
    assert card["mechanism_claim"] == "Restriction of Intramolecular Rotation (RIR)"
    assert card["experimental_context"] == "aggregate state"
    assert result["query_groups_attempted"] == [
        "exact_identity",
        "champion_family",
        "challenger_family",
        "pairwise_discriminator",
    ]
    assert result["query_groups_with_hits"] == ["exact_identity"]
    assert result["queries_executed"]


def test_verifier_tool_returns_failed_payload_on_client_error() -> None:
    tool = OpenAIVerifierEvidenceTool(
        config=AieMasConfig(verifier_api_key="test-key"),
        client=_FakeVerifierClient(error=RuntimeError("network unavailable")),
    )

    result = tool.invoke(
        smiles="C1=CC=CC=C1",
        current_hypothesis="Restriction of Intramolecular Rotation (RIR)",
        task_received="Retrieve external supervision evidence for the current hypothesis.",
        main_gap="Clarify the remaining external evidence gap.",
        molecule_identity_context=None,
        latest_macro_report=None,
        latest_microscopic_report=None,
    )

    assert result["status"] == "failed"
    assert result["source_count"] == 0
    assert result["evidence_cards"] == []
    assert "network unavailable" in result["error"]


def test_verifier_tool_returns_partial_with_limitation_card_when_no_cards_are_returned() -> None:
    tool = OpenAIVerifierEvidenceTool(
        config=AieMasConfig(verifier_api_key="test-key"),
        client=_FakeVerifierClient(
            VerifierRetrievalResponse(
                retrieval_note="Search completed but did not find specific sources.",
                evidence_cards=[],
            )
        ),
    )

    result = tool.invoke(
        smiles="C1=CC=CC=C1",
        current_hypothesis="Restriction of Intramolecular Rotation (RIR)",
        task_received="Retrieve external supervision evidence for the current hypothesis.",
        main_gap="Clarify the remaining external evidence gap.",
        molecule_identity_context=None,
        latest_macro_report=None,
        latest_microscopic_report=None,
    )

    assert result["status"] == "partial"
    assert result["source_count"] == 1
    card = result["evidence_cards"][0]
    assert card["query_group"] == "limitation"
    assert card["match_level"] == "retrieval_limitation"
