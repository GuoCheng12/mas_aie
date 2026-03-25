from __future__ import annotations

from dataclasses import dataclass

from aie_mas.config import AieMasConfig
from aie_mas.tools.amesp import AmespMicroscopicTool
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.tools.shared_structure import SharedStructurePrepTool
from aie_mas.tools.verifier import OpenAIVerifierEvidenceTool


@dataclass
class ToolSet:
    shared_structure_tool: SharedStructurePrepTool
    macro_tool: DeterministicMacroStructureTool
    verifier_tool: OpenAIVerifierEvidenceTool
    amesp_micro_tool: AmespMicroscopicTool


def build_toolset(config: AieMasConfig) -> ToolSet:
    return ToolSet(
        shared_structure_tool=SharedStructurePrepTool(),
        macro_tool=DeterministicMacroStructureTool(),
        verifier_tool=OpenAIVerifierEvidenceTool(config=config),
        amesp_micro_tool=AmespMicroscopicTool(
            amesp_bin=config.amesp_binary_path,
            npara=config.amesp_npara,
            maxcore_mb=config.amesp_maxcore_mb,
            use_ricosx=config.amesp_use_ricosx,
            s1_nstates=config.amesp_s1_nstates,
            td_tout=config.amesp_td_tout,
            follow_up_max_conformers=config.amesp_follow_up_max_conformers,
            follow_up_max_torsion_snapshots_total=config.amesp_follow_up_max_torsion_snapshots_total,
            probe_interval_seconds=config.amesp_probe_interval_seconds,
        ),
    )
