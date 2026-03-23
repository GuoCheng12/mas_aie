from __future__ import annotations

from dataclasses import dataclass

from aie_mas.config import AieMasConfig
from aie_mas.tools.amesp import AmespBaselineMicroscopicTool
from aie_mas.tools.macro import MockMacroStructureTool
from aie_mas.tools.microscopic import (
    MockS0OptimizationTool,
    MockS1OptimizationTool,
    MockTargetedMicroscopicTool,
)
from aie_mas.tools.verifier import MockVerifierEvidenceTool


@dataclass
class ToolSet:
    macro_tool: MockMacroStructureTool
    s0_tool: MockS0OptimizationTool
    s1_tool: MockS1OptimizationTool
    targeted_micro_tool: MockTargetedMicroscopicTool
    verifier_tool: MockVerifierEvidenceTool
    amesp_micro_tool: AmespBaselineMicroscopicTool | None = None


def build_toolset(config: AieMasConfig) -> ToolSet:
    if config.tool_backend == "real":
        return ToolSet(
            macro_tool=MockMacroStructureTool(),
            s0_tool=MockS0OptimizationTool(),
            s1_tool=MockS1OptimizationTool(),
            targeted_micro_tool=MockTargetedMicroscopicTool(),
            verifier_tool=MockVerifierEvidenceTool(),
            amesp_micro_tool=AmespBaselineMicroscopicTool(
                amesp_bin=config.amesp_binary_path,
            ),
        )

    return ToolSet(
        macro_tool=MockMacroStructureTool(),
        s0_tool=MockS0OptimizationTool(),
        s1_tool=MockS1OptimizationTool(),
        targeted_micro_tool=MockTargetedMicroscopicTool(),
        verifier_tool=MockVerifierEvidenceTool(),
        amesp_micro_tool=None,
    )
