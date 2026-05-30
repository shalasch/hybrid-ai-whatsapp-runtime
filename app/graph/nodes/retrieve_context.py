from app.graph.state import DecisionGraphState
from app.rag.retriever import BasicRetriever

retriever = BasicRetriever()


def retrieve_context(state: DecisionGraphState) -> DecisionGraphState:
    ctx = state["runtime_context"]
    docs = retriever.retrieve(ctx.message.text)
    return {**state, "retrieved_docs": docs}
