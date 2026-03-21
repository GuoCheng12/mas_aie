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
    def read_text(self, prompt_name: str) -> str:
        filename = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
        return (self._prompts_dir / filename).read_text(encoding="utf-8").strip()

    @lru_cache(maxsize=None)
    def get(self, prompt_name: str) -> ChatPromptTemplate:
        prompt_text = self.read_text(prompt_name)
        return ChatPromptTemplate.from_messages(
            [
                ("system", prompt_text),
                ("human", "Planner context JSON:\n{context_json}"),
            ]
        )

    @lru_cache(maxsize=None)
    def get_sections(self, prompt_name: str) -> dict[str, str]:
        prompt_text = self.read_text(prompt_name)
        sections: dict[str, str] = {}
        current_section: str | None = None
        buffer: list[str] = []

        for line in prompt_text.splitlines():
            if line.startswith("## "):
                if current_section is not None:
                    sections[current_section] = "\n".join(buffer).strip()
                current_section = line[3:].strip()
                buffer = []
            elif current_section is not None:
                buffer.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(buffer).strip()

        if not sections:
            raise ValueError(f"Prompt '{prompt_name}' does not contain markdown sections.")
        return sections

    def render(self, prompt_name: str, payload: dict[str, Any]) -> Any:
        prompt = self.get(prompt_name)
        return prompt.invoke({"context_json": json.dumps(payload, ensure_ascii=False, indent=2)})

    def render_sections(self, prompt_name: str, payload: dict[str, Any]) -> dict[str, str]:
        sections = self.get_sections(prompt_name)
        render_values = dict(payload)
        rendered: dict[str, str] = {}
        for section_name, template in sections.items():
            rendered_text = template.format(**render_values).strip()
            rendered[section_name] = rendered_text
            render_values[section_name] = rendered_text
        return rendered
