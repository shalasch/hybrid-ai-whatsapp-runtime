# Hybrid AI WhatsApp Runtime

AI Decision API **(v3.1)** — OpenAI-powered decision layer for a WhatsApp operational runtime built on **LangGraph + FastAPI**.

This is not a chatbot. It is a structured decision layer that sits behind n8n and returns a typed JSON routing decision.

---

## Architecture

```
WhatsApp Cloud API
  → n8n intake + deterministic validation
  → POST /decide  ←─ this service
      LangGraph pipeline:
        classify_intent       (pre-classify intent hint)
        memory_builder        (memory update contract)
        retrieve_context      (basic RAG)
        decision_node         (OpenAI gpt-4.1-mini structured output)
                               └─ fallback: deterministic rules if no API key
        validation_node       (confidence thresholds + human escalation)
  → structured DecideResponse (JSON)
  → n8n validates routing_action
  → deterministic handler execution
  → Airtable logs / state updates
```

### Decision modes

| Mode | When | Behaviour |
|------|------|-----------|
| **OpenAI** | `OPENAI_API_KEY` is set | `gpt-4.1-mini` returns structured JSON via `response_format` |
| **Deterministic fallback** | no key or API error | rule-based routing, same contract |

`validation_node` enforces confidence thresholds in **both** modes.

**Design principle:** the AI layer recommends — n8n validates and executes. This service never sends WhatsApp messages, mutates Airtable records, or triggers business-critical side-effects directly.

---

## Quick start (local)

### 1. Create and activate a virtual environment

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if needed — all fields have safe defaults for local dev
```

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive docs: <http://localhost:8000/docs>

Health check: <http://localhost:8000/health>

---

## POST /decide — test payload

```bash
curl -X POST http://localhost:8000/decide \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_context": {
      "lead": {
        "id": "lead_001",
        "nome": "Maria Silva",
        "interesse": "offshore"
      },
      "conversation": {
        "id": "conv_001",
        "etapa": "Menu",
        "status": "Ativa",
        "session_id": "5521999999999"
      },
      "message": {
        "text": "Quero treinar entrevista offshore",
        "type": "text",
        "idempotency_key": "wamid_abc123"
      },
      "routing": {
        "previous_action": "send_menu"
      }
    }
  }'
```

### Example response

```json
{
  "routing_action": "send_quiz",
  "message_type": "text",
  "message_body": "Perfeito. Posso te enviar um diagnóstico rápido de inglês para offshore e entrevistas?",
  "confidence": 0.88,
  "needs_human": false,
  "reason": "Mensagem indica interesse em inglês offshore ou entrevista.",
  "reasoning": {
    "intent": "offshore_interest",
    "matched_signals": ["offshore/interview signal"],
    "risk_flags": [],
    "decision_factors": ["deterministic_guardrails", "runtime_context"]
  },
  "memory_update": {
    "last_intent": "offshore_interest",
    "interest_area": "offshore"
  },
  "retrieval": { "used": false, "sources": [] },
  "runtime_warnings": []
}
```

### v3.1 — OpenAI-powered response example

With `OPENAI_API_KEY` set, the same offshore request above returns an AI-generated decision:

```json
{
  "routing_action": "send_quiz",
  "message_type": "text",
  "message_body": "Ótimo, Maria! Para entender melhor o seu perfil e objetivo com o inglês offshore, posso te enviar um diagnóstico rápido? Leva menos de 2 minutos e nos ajuda a personalizar sua trilha. Pode ser?",
  "confidence": 0.91,
  "needs_human": false,
  "reason": "Lead demonstrou interesse explícito em inglês offshore para entrevistas; diagnóstico é o próximo passo natural.",
  "reasoning": {
    "intent": "offshore_interest",
    "matched_signals": ["offshore", "entrevista", "lead.interesse=offshore"],
    "risk_flags": [],
    "decision_factors": ["openai_structured_output", "runtime_context"]
  },
  "memory_update": {
    "last_intent": "offshore_interest",
    "interest_area": "offshore"
  },
  "retrieval": { "used": false, "sources": [] },
  "runtime_warnings": []
}
```

Without `OPENAI_API_KEY` the deterministic fallback produces the same `routing_action` with a shorter `message_body`.

---

### Missing-name test (triggers `ask_name`)

```bash
curl -X POST http://localhost:8000/decide \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_context": {
      "lead": {},
      "conversation": { "id": "conv_002", "session_id": "5521888888888" },
      "message": { "text": "Oi", "type": "text", "idempotency_key": "wamid_xyz" },
      "routing": {}
    }
  }'
```

---

## Run tests

```bash
pytest
```

---

## LangSmith tracing (optional)

Set these in `.env` to enable cloud tracing:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=schillings-ai-runtime
```

Leave `LANGSMITH_TRACING=false` (the default) to run fully offline.

---

## Routing actions

| `routing_action`                    | Meaning                          |
|-------------------------------------|----------------------------------|
| `ask_name`                          | Lead has no name — collect it    |
| `capture_name`                      | Confirm/capture name payload     |
| `send_menu`                         | Show main options menu           |
| `send_quiz`                         | Trigger offshore/English quiz    |
| `human_wait`                        | Escalate to human agent          |
| `ask_goal`                          | Clarify learning goal            |
| `answer_faq`                        | Answer from knowledge base       |
| `route_payload_offshore_interview`  | Offshore interview track         |
| `route_payload_professional_english`| Professional English track       |
| `route_payload_general_english`     | General English track            |
| `route_payload_trial_class`         | Free trial class booking         |
| `route_payload_student_support`     | Existing student support         |
| `route_payload_human_support`       | Human support request            |

---

## Confidence thresholds

| Variable                        | Default | Effect                                        |
|---------------------------------|---------|-----------------------------------------------|
| `DECISION_CONFIDENCE_THRESHOLD` | `0.72`  | Below this → fallback to `send_menu`          |
| `HUMAN_ESCALATION_THRESHOLD`    | `0.50`  | Below this → force `human_wait + needs_human` |

---

## Roadmap

- **v3** (current): deterministic AI decision layer, basic RAG, memory contract
- **v4**: persistent memory + vector RAG (pgvector / Pinecone)
- **v5**: LangSmith evals, replay tests, production hardening
