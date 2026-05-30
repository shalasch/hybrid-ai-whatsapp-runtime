import os
from app.config import settings


def configure_langsmith_env() -> None:
    os.environ.setdefault("LANGSMITH_TRACING", str(settings.langsmith_tracing).lower())
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    os.environ.setdefault("LANGSMITH_ENDPOINT", settings.langsmith_endpoint)
