from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pyamesp_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pyamesp_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parser_rejects_molecule_and_smiles_together() -> None:
    module = _load_module()
    parser = module.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--molecule", "NH3", "--smiles", "C1=CCCCC1"])


def test_resolve_input_selection_defaults_to_legacy_molecule() -> None:
    module = _load_module()

    selection = module.resolve_input_selection(
        argparse.Namespace(molecule=None, smiles=None)
    )

    assert selection == ("molecule", "NH3")


def test_resolve_input_selection_prefers_smiles_when_provided() -> None:
    module = _load_module()

    selection = module.resolve_input_selection(
        argparse.Namespace(molecule=None, smiles="C1=CCCCC1")
    )

    assert selection == ("smiles", "C1=CCCCC1")
