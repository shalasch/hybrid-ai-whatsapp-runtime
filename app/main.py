from fastapi import FastAPI
from app.api.decide import router as decide_router
from app.observability.logger import configure_logging
from app.observability.tracing import configure_langsmith_env

configure_logging()
configure_langsmith_env()

app = FastAPI(
    title="Hybrid AI WhatsApp Runtime",
    version="0.3.0",
    description="AI Decision API for deterministic n8n execution, memory, RAG and LangSmith-ready tracing.",
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "hybrid-ai-whatsapp-runtime"}

app.include_router(decide_router)
