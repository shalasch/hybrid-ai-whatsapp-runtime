from app.contracts.runtime_context import RuntimeContext
from app.rag.retriever import RetrievedDocument

_SYSTEM_PROMPT = """\
You are the AI decision engine for an English-language sales WhatsApp assistant for an online English school.

Analyze the lead context and message, then return a routing decision that directs the n8n orchestration layer.

## ALLOWED ROUTING ACTIONS — select exactly one

ask_name                           Lead has no registered name
capture_name                       Lead just provided their name
send_menu                          Intent unclear; present the options menu
send_quiz                          Lead shows offshore/interview interest
human_wait                         Lead requests a human agent
ask_goal                           Clarify learning objective
answer_faq                         General question answerable from the knowledge base
route_payload_offshore_interview   Confirmed offshore interview track
route_payload_professional_english Professional English track
route_payload_general_english      General English track
route_payload_trial_class          Free trial class booking
route_payload_student_support      Existing student support request
route_payload_human_support        Human support escalation

## CONFIDENCE GUIDELINES

0.85–1.0   clear intent, high certainty
0.72–0.85  confident match, normal execution path
0.50–0.72  uncertain — prefer send_menu over specific routing
< 0.50     escalate: set needs_human=true, routing_action=human_wait

## RULES

- message_body must be in Brazilian Portuguese, warm and conversational
- needs_human must be true when confidence < 0.50 OR user explicitly asked for a human
- matched_signals: list the text cues, payload values, or context signals that drove the decision
- risk_flags: list concerns such as ambiguity, missing info, or conflicting signals (empty list if none)
- Return valid JSON only — no markdown fences, no extra text"""


def build_messages(
    ctx: RuntimeContext,
    intent: str,
    docs: list[RetrievedDocument],
) -> list[dict]:
    kb_section = (
        "\n".join(f"- [{d.source}]: {d.content}" for d in docs)
        if docs
        else "No knowledge base matches."
    )
    pain = ", ".join(ctx.lead.pain_points) if ctx.lead.pain_points else "none"

    user_content = f"""\
LEAD CONTEXT
  name:          {ctx.lead.nome or 'unknown'}
  stage:         {ctx.lead.stage or ctx.conversation.etapa or 'unknown'}
  interest:      {ctx.lead.interesse or ctx.lead.interest_area or 'unknown'}
  last_intent:   {ctx.lead.last_intent or 'none'}
  pain_points:   {pain}
  lead_summary:  {ctx.lead.lead_summary or 'none'}

CONVERSATION
  session:       {ctx.conversation.session_id or 'unknown'}
  etapa:         {ctx.conversation.etapa or 'unknown'}
  status:        {ctx.conversation.status or 'unknown'}

CURRENT MESSAGE
  text:          {ctx.message.text or '(empty)'}
  type:          {ctx.message.type}
  payload:       {ctx.message.payload or 'none'}
  pre_intent:    {intent}

KNOWLEDGE BASE MATCHES
{kb_section}

Return the routing decision as JSON."""

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
