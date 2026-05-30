from pydantic import BaseModel

class RetrievedDocument(BaseModel):
    source: str
    content: str

KNOWLEDGE_BASE = [
    RetrievedDocument(source="methodology", content="O curso usa aulas ao vivo online, abordagem prática e adaptação ao objetivo do aluno."),
    RetrievedDocument(source="offshore", content="O módulo offshore treina comunicação operacional, entrevistas, safety briefings, handover e vocabulário de rotina."),
    RetrievedDocument(source="trial_class", content="A aula experimental gratuita apresenta a metodologia e ajuda a diagnosticar o nível e objetivo do aluno."),
    RetrievedDocument(source="student_support", content="Alunos podem receber suporte por fora das aulas para dúvidas, materiais e acompanhamento."),
]

class BasicRetriever:
    def retrieve(self, query: str | None, limit: int = 3) -> list[RetrievedDocument]:
        if not query:
            return []
        q = query.lower()
        scored: list[tuple[int, RetrievedDocument]] = []
        for doc in KNOWLEDGE_BASE:
            score = sum(1 for token in q.split() if token in doc.content.lower() or token in doc.source.lower())
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:limit]]
