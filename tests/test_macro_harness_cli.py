from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from aie_mas.macro_harness.cli import cli


runner = CliRunner()


def test_macro_harness_lists_capabilities() -> None:
    result = runner.invoke(cli, ["--json", "capability", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    capabilities = payload["capabilities"]
    capability_names = {entry["capability_name"] for entry in capabilities}
    assert "screen_neutral_aromatic_structure" in capability_names
    assert "screen_intramolecular_hbond_preorganization" in capability_names


def test_macro_harness_runs_neutral_aromatic_screen() -> None:
    result = runner.invoke(
        cli,
        [
            "--json",
            "screen",
            "run",
            "screen_neutral_aromatic_structure",
            "--smiles",
            "c1ccccc1",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["selected_capability"] == "screen_neutral_aromatic_structure"
    assert payload["executed_capability"] == "screen_neutral_aromatic_structure"
    assert payload["cli_harness"]["harness_name"] == "aie-mas-macro"


def test_macro_harness_repl_default_help_and_exit() -> None:
    result = runner.invoke(cli, input="help\nexit\n")
    assert result.exit_code == 0
    assert "AIE-MAS Macro REPL" in result.stdout
    assert "capability list" in result.stdout


def test_macro_harness_shows_capability_contract() -> None:
    result = runner.invoke(cli, ["--json", "capability", "show", "screen_intramolecular_hbond_preorganization"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["capability_name"] == "screen_intramolecular_hbond_preorganization"
    assert payload["requires_shared_structure_context"] is True
    assert payload["input_contract"]["shared_structure_context_file"]["required"] is True


def test_macro_harness_context_inspect_and_validate() -> None:
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        prepared_xyz = tmp_path / "prepared.xyz"
        prepared_sdf = tmp_path / "prepared.sdf"
        summary_json = tmp_path / "summary.json"
        prepared_xyz.write_text("1\n\nC 0.0 0.0 0.0\n", encoding="utf-8")
        prepared_sdf.write_text("", encoding="utf-8")
        summary_json.write_text("{}", encoding="utf-8")
        context_path = tmp_path / "shared_structure_context.json"
        context_path.write_text(
            json.dumps(
                {
                    "input_smiles": "c1ccccc1",
                    "canonical_smiles": "c1ccccc1",
                    "charge": 0,
                    "multiplicity": 1,
                    "atom_count": 6,
                    "conformer_count": 1,
                    "selected_conformer_id": 0,
                    "prepared_xyz_path": str(prepared_xyz),
                    "prepared_sdf_path": str(prepared_sdf),
                    "summary_path": str(summary_json),
                    "rotatable_bond_count": 0,
                    "aromatic_ring_count": 1,
                    "ring_system_count": 1,
                    "hetero_atom_count": 0,
                    "branch_point_count": 0,
                    "donor_acceptor_partition_proxy": 0.0,
                    "planarity_proxy": 1.0,
                    "compactness_proxy": 1.0,
                    "torsion_candidate_count": 0,
                    "principal_span_proxy": 1.0,
                    "conformer_dispersion_proxy": 0.0,
                }
            ),
            encoding="utf-8",
        )

        inspect_result = runner.invoke(cli, ["--json", "context", "inspect", str(context_path)])
        assert inspect_result.exit_code == 0
        inspect_payload = json.loads(inspect_result.stdout)
        assert inspect_payload["inspection"]["validation"]["valid"] is True
        assert inspect_payload["inspection"]["path_status"]["prepared_xyz_path"]["exists"] is True

        validate_result = runner.invoke(cli, ["--json", "context", "validate", str(context_path)])
        assert validate_result.exit_code == 0
        validate_payload = json.loads(validate_result.stdout)
        assert validate_payload["valid"] is True
        assert validate_payload["errors"] == []


def test_macro_harness_invalid_capability_returns_json_error_envelope() -> None:
    result = runner.invoke(
        cli,
        ["--json", "screen", "run", "screen_not_real", "--smiles", "c1ccccc1"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_input"
