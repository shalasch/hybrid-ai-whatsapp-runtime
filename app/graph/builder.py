from langgraph.graph import END, StateGraph
from app.graph.state import DecisionGraphState
from app.graph.nodes.classify_intent import classify_intent
from app.graph.nodes.memory_builder import memory_builder
from app.graph.nodes.retrieve_context import retrieve_context
from app.graph.nodes.decision_node import decision_node
from app.graph.nodes.validation_node import validation_node


def build_decision_graph():
    graph = StateGraph(DecisionGraphState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("memory_builder", memory_builder)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("decision_node", decision_node)
    graph.add_node("validation_node", validation_node)

    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "memory_builder")
    graph.add_edge("memory_builder", "retrieve_context")
    graph.add_edge("retrieve_context", "decision_node")
    graph.add_edge("decision_node", "validation_node")
    graph.add_edge("validation_node", END)
    return graph.compile()
