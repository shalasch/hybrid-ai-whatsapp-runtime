from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    log_json: bool = True
    openai_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "schillings-ai-runtime-local"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    decision_confidence_threshold: float = 0.72
    human_escalation_threshold: float = 0.50

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
