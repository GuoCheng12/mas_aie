from __future__ import annotations

from dataclasses import dataclass

from aie_mas.config import AieMasConfig
from aie_mas.tools.amesp import AmespBaselineMicroscopicTool
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.tools.shared_structure import SharedStructurePrepTool
from aie_mas.tools.verifier import DeterministicVerifierEvidenceTool


@dataclass
class ToolSet:
    shared_structure_tool: SharedStructurePrepTool
    macro_tool: DeterministicMacroStructureTool
    verifier_tool: DeterministicVerifierEvidenceTool
    amesp_micro_tool: AmespBaselineMicroscopicTool


def build_toolset(config: AieMasConfig) -> ToolSet:
    return ToolSet(
        shared_structure_tool=SharedStructurePrepTool(),
        macro_tool=DeterministicMacroStructureTool(),
        verifier_tool=DeterministicVerifierEvidenceTool(),
        amesp_micro_tool=AmespBaselineMicroscopicTool(
            amesp_bin=config.amesp_binary_path,
            npara=config.amesp_npara,
            maxcore_mb=config.amesp_maxcore_mb,
            use_ricosx=config.amesp_use_ricosx,
            s1_nstates=config.amesp_s1_nstates,
            td_tout=config.amesp_td_tout,
            probe_interval_seconds=config.amesp_probe_interval_seconds,
        ),
    )
