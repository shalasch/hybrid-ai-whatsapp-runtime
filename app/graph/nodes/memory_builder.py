from app.graph.state import DecisionGraphState
from app.memory.builder import build_memory_update


def memory_builder(state: DecisionGraphState) -> DecisionGraphState:
    update = build_memory_update(state["runtime_context"], state.get("intent"))
    return {**state, "memory_update": update}
