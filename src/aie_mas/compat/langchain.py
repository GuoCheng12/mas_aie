from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

try:
    from langchain_core.prompts import ChatPromptTemplate  # type: ignore
    from langchain_core.runnables import RunnableLambda  # type: ignore
except ImportError:
    @dataclass
    class RenderedPrompt:
        messages: list[dict[str, str]]
        text: str

        def to_string(self) -> str:
            return self.text

    class RunnableLambda:
        def __init__(self, func: Callable[[Any], Any]) -> None:
            self._func = func

        def invoke(self, input_value: Any) -> Any:
            return self._func(input_value)

    class ChatPromptTemplate:
        def __init__(self, messages: list[tuple[str, str]]) -> None:
            self._messages = messages

        @classmethod
        def from_messages(cls, messages: list[tuple[str, str]]) -> "ChatPromptTemplate":
            return cls(messages)

        def invoke(self, input_value: dict[str, Any]) -> RenderedPrompt:
            rendered_messages: list[dict[str, str]] = []
            for role, template in self._messages:
                rendered_messages.append({"role": role, "content": template.format(**input_value)})
            text = "\n\n".join(
                f"[{message['role']}] {message['content']}" for message in rendered_messages
            )
            return RenderedPrompt(messages=rendered_messages, text=text)


def prompt_value_to_text(prompt_value: Any) -> str:
    if hasattr(prompt_value, "to_string"):
        return prompt_value.to_string()
    if hasattr(prompt_value, "messages"):
        messages = getattr(prompt_value, "messages")
        parts: list[str] = []
        for message in messages:
            role = getattr(message, "type", None) or getattr(message, "role", "message")
            content = getattr(message, "content", str(message))
            parts.append(f"[{role}] {content}")
        return "\n\n".join(parts)
    return str(prompt_value)


__all__ = ["ChatPromptTemplate", "RunnableLambda", "prompt_value_to_text"]
