# Hybrid AI WhatsApp Runtime

AI Decision API (v3) — a deterministic decision layer for a WhatsApp operational runtime built on **LangGraph + FastAPI**.

This is not a chatbot. It is a structured decision layer that sits behind n8n and returns a typed JSON routing decision.

---

## Architecture

```
WhatsApp Cloud API
  → n8n intake + deterministic validation
  → POST /decide  ←─ this service
      LangGraph pipeline:
        classify_intent
        memory_builder
        retrieve_context   (basic RAG mock)
        decision_node
        validation_node    (confidence + human escalation)
  → structured DecideResponse (JSON)
  → n8n validates routing_action
  → deterministic handler execution
  → Airtable logs / state updates
```

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
