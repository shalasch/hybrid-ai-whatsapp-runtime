from pydantic import BaseModel


class RetrievedDocument(BaseModel):
    source: str
    content: str
    score: float = 0.0


class BasicRetriever:
    """Keyword-based fallback retriever used when ChromaDB is unavailable."""

    _KNOWLEDGE_BASE = [
        RetrievedDocument(source="methodology", content="O curso usa aulas ao vivo online, abordagem prática e adaptação ao objetivo do aluno."),
        RetrievedDocument(source="offshore-english", content="O módulo offshore treina comunicação operacional, entrevistas, safety briefings, handover e vocabulário de rotina."),
        RetrievedDocument(source="trial-class", content="A aula experimental gratuita apresenta a metodologia e ajuda a diagnosticar o nível e objetivo do aluno."),
        RetrievedDocument(source="student-support", content="Alunos podem receber suporte por fora das aulas para dúvidas, materiais e acompanhamento."),
        RetrievedDocument(source="faq", content="Perguntas frequentes sobre o curso, módulo offshore, aula experimental e suporte ao aluno."),
        RetrievedDocument(source="commercial-policy-public", content="Reagendamento com 24h de antecedência. Cancelamentos frequentes sem aviso podem impactar o plano de curso."),
    ]

    def retrieve(self, query: str | None, limit: int = 3) -> list[RetrievedDocument]:
        if not query:
            return []
        q = query.lower()
        scored: list[tuple[float, RetrievedDocument]] = []
        for doc in self._KNOWLEDGE_BASE:
            hits = sum(1 for token in q.split() if token in doc.content.lower() or token in doc.source.lower())
            if hits:
                scored.append((float(hits), doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc.model_copy(update={"score": round(score / 10, 4)}) for score, doc in scored[:limit]]
