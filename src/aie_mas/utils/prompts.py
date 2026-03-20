from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from aie_mas.compat.langchain import ChatPromptTemplate


class PromptRepository:
    def __init__(self, prompts_dir: Path) -> None:
        self._prompts_dir = prompts_dir

    @lru_cache(maxsize=None)
    def get(self, prompt_name: str) -> ChatPromptTemplate:
        filename = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
        prompt_text = (self._prompts_dir / filename).read_text(encoding="utf-8").strip()
        return ChatPromptTemplate.from_messages(
            [
                ("system", prompt_text),
                ("human", "Planner context JSON:\n{context_json}"),
            ]
        )

    def render(self, prompt_name: str, payload: dict[str, Any]) -> Any:
        prompt = self.get(prompt_name)
        return prompt.invoke({"context_json": json.dumps(payload, ensure_ascii=False, indent=2)})
