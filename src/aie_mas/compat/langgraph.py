from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

try:
    from langgraph.graph import END, START, StateGraph  # type: ignore
except ImportError:
    START = "__start__"
    END = "__end__"

    @dataclass
    class _ConditionalEdge:
        route: Callable[[Any], str]
        path_map: dict[str, str]

    class CompiledStateGraph:
        def __init__(
            self,
            entry_point: str,
            nodes: dict[str, Callable[[Any], Any]],
            edges: dict[str, str],
            conditional_edges: dict[str, _ConditionalEdge],
        ) -> None:
            self._entry_point = entry_point
            self._nodes = nodes
            self._edges = edges
            self._conditional_edges = conditional_edges

        def invoke(self, input_state: Any) -> Any:
            state = input_state
            current_node = self._entry_point
            steps = 0
            while current_node != END:
                steps += 1
                if steps > 100:
                    raise RuntimeError("Graph execution exceeded 100 steps.")
                state = self._nodes[current_node](state)
                if current_node in self._conditional_edges:
                    conditional = self._conditional_edges[current_node]
                    route_key = conditional.route(state)
                    current_node = conditional.path_map[route_key]
                    continue
                current_node = self._edges.get(current_node, END)
            return state

    class StateGraph:
        def __init__(self, state_type: type[Any]) -> None:
            self.state_type = state_type
            self._nodes: dict[str, Callable[[Any], Any]] = {}
            self._edges: dict[str, str] = {}
            self._conditional_edges: dict[str, _ConditionalEdge] = {}
            self._entry_point: str | None = None

        def add_node(self, name: str, func: Callable[[Any], Any]) -> None:
            self._nodes[name] = func

        def add_edge(self, source: str, target: str) -> None:
            self._edges[source] = target

        def add_conditional_edges(
            self,
            source: str,
            route: Callable[[Any], str],
            path_map: dict[str, str],
        ) -> None:
            self._conditional_edges[source] = _ConditionalEdge(route=route, path_map=path_map)

        def set_entry_point(self, name: str) -> None:
            self._entry_point = name

        def compile(self) -> CompiledStateGraph:
            if self._entry_point is None:
                raise ValueError("An entry point is required before compiling the graph.")
            return CompiledStateGraph(
                entry_point=self._entry_point,
                nodes=self._nodes,
                edges=self._edges,
                conditional_edges=self._conditional_edges,
            )


__all__ = ["END", "START", "StateGraph"]
