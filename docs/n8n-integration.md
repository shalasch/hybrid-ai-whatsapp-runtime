# n8n Integration Guide

This document describes how n8n connects to the Python AI runtime and what fields it should read from the `/decide` response to continue deterministic execution.

---

## Role separation

| Layer | Responsibility |
|---|---|
| **n8n** | WhatsApp intake, schema validation, handler execution, Airtable writes |
| **Python runtime** | Intent classification, memory update, RAG retrieval, AI decision, confidence validation |

n8n is the **execution runtime**. Python is the **cognitive runtime**. Python never writes to Airtable or dispatches WhatsApp messages directly.

---

## Request — what n8n sends

n8n builds a `runtime_context` from its internal state and POSTs to `/decide`.

```
POST http://<runtime-host>:8000/decide
Content-Type: application/json
```

```json
{
  "runtime_context": {
    "lead": {
      "id": "{{$node.GetLead.json.id}}",
      "nome": "{{$node.GetLead.json.nome}}",
      "interesse": "{{$node.GetLead.json.interesse}}",
      "stage": "{{$node.GetLead.json.stage}}",
      "lead_summary": "{{$node.GetLead.json.lead_summary}}",
      "last_intent": "{{$node.GetLead.json.last_intent}}"
    },
    "conversation": {
      "id": "{{$node.GetConversation.json.id}}",
      "etapa": "{{$node.GetConversation.json.etapa}}",
      "status": "{{$node.GetConversation.json.status}}",
      "session_id": "{{$node.Webhook.json.from}}"
    },
    "message": {
      "text": "{{$node.Webhook.json.text.body}}",
      "type": "{{$node.Webhook.json.type}}",
      "payload": "{{$node.Webhook.json.interactive.button_reply.id}}",
      "idempotency_key": "{{$node.Webhook.json.id}}"
    },
    "routing": {
      "previous_action": "{{$node.GetConversation.json.last_routing_action}}"
    }
  }
}
```

---

## Response — what n8n reads

The response always contains these top-level fields:

```json
{
  "lead_id": "lead_001",
  "conversation_id": "conv_001",
  "runtime_context": { ... },

  "routing_action": "send_quiz",
  "message_body": "Perfeito. Posso te enviar um diagnóstico rápido?",
  "message_type": "text",
  "confidence": 0.91,
  "needs_human": false,
  "reason": "...",

  "reasoning": { ... },
  "memory_update": { ... },
  "retrieval": { ... },
  "runtime_warnings": []
}
```

### Fields n8n must read

| Field | Type | n8n usage |
|---|---|---|
| `lead_id` | `string \| null` | Airtable record lookup for lead update |
| `conversation_id` | `string \| null` | Airtable record lookup for conversation update |
| `routing_action` | `string` (enum) | Switch node — determines which handler runs |
| `message_body` | `string \| null` | WhatsApp message content to dispatch |
| `message_type` | `"text" \| "interactive" \| "none"` | Determines WhatsApp node type |
| `needs_human` | `boolean` | If true, trigger human escalation branch |
| `confidence` | `float 0–1` | Can be logged to Airtable for observability |
| `memory_update` | `object` | Fields to write back to lead Airtable record |
| `runtime_warnings` | `array` | Log to Airtable if non-empty |

### `runtime_context` passthrough

The response echoes the full `runtime_context` that was sent. This allows n8n to access any lead or conversation field downstream without performing additional Airtable reads.

```
{{ $json.runtime_context.lead.nome }}
{{ $json.runtime_context.conversation.etapa }}
{{ $json.runtime_context.lead.interest_area }}
```

---

## n8n workflow structure

```
Webhook (WhatsApp intake)
  │
  ▼
Validate schema + deduplicate (idempotency_key)
  │
  ▼
GET Lead from Airtable
GET Conversation from Airtable
  │
  ▼
Build runtime_context
  │
  ▼
HTTP Request → POST /decide
  │
  ▼
Read response fields
  │
  ├── needs_human = true  →  Human Escalation branch
  │
  └── Switch on routing_action
        │
        ├── ask_name                     → Send name-request message
        ├── send_menu                    → Send options menu
        ├── send_quiz                    → Trigger quiz payload
        ├── route_payload_trial_class    → Trial class booking flow
        ├── route_payload_offshore_interview → Offshore track
        ├── route_payload_student_support   → Student support handler
        ├── answer_faq                   → Send FAQ message_body
        └── human_wait                  → Queue for human agent
              │
              ▼
        Update Airtable (lead_id, conversation_id, memory_update fields)
        Dispatch WhatsApp message (message_body, message_type)
```

---

## Airtable update after decision

Use `lead_id` and `conversation_id` from the response root — not from `runtime_context` — to avoid expression nesting issues in n8n.

```
PATCH airtable/leads/{{ $json.lead_id }}
  last_intent:         {{ $json.memory_update.last_intent }}
  interest_area:       {{ $json.memory_update.interest_area }}
  lead_summary:        {{ $json.memory_update.lead_summary }}
  stage:               {{ $json.memory_update.stage }}

PATCH airtable/conversations/{{ $json.conversation_id }}
  last_routing_action: {{ $json.routing_action }}
  last_confidence:     {{ $json.confidence }}
  runtime_warnings:    {{ $json.runtime_warnings.join(', ') }}
```

---

## Error handling

If `/decide` returns a non-200 status, n8n should:
1. Log the error with `idempotency_key` and `session_id`
2. Send a safe fallback message to the lead ("Tivemos um problema técnico, já estou avisando a equipe.")
3. Set `needs_human = true` in Airtable
4. Do not retry automatically — wait for manual review

The Python runtime handles its own fallback internally (deterministic rules activate if OpenAI is unavailable), so non-200 responses represent infrastructure-level failures, not decision failures.

---

## Confidence thresholds reference

These are enforced inside the Python runtime before the response is returned. n8n does not need to re-apply them.

| Threshold | Value | Behaviour |
|---|---|---|
| Decision threshold | `0.72` | Below → `send_menu` override |
| Human escalation floor | `0.50` | Below → `human_wait` + `needs_human=true` |
