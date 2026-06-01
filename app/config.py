from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    log_json: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "schillings-ai-runtime-local"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    decision_confidence_threshold: float = 0.75
    human_escalation_threshold: float = 0.60
    memory_db_path: str = "data/memory.sqlite"
    audit_log_path: str = "data/audit.jsonl"
    chroma_path: str = "data/chroma"
    rag_top_k: int = 3
    rag_embedding_provider: str = "onnx"  # "onnx" | "openai"
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
