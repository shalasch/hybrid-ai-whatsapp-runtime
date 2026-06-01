# Política de Escalação para Atendimento Humano

Define quando o sistema deve encaminhar a conversa para um humano (`human_wait`) em vez de continuar o fluxo automatizado.

## Escalação imediata — sem exceção

Encaminhar para `human_wait` imediatamente quando o lead ou aluno mencionar:

- **Pagamento, mensalidade, boleto, Pix, cobrança** — qualquer questão financeira
- **Cancelamento de matrícula ou assinatura** — decisão que requer atendimento humano
- **Reembolso ou estorno** — não tratar automaticamente em nenhuma hipótese
- **Reclamação explícita** — sobre qualidade, atendimento, professora ou experiência
- **Pedido direto de humano** — "quero falar com alguém", "me chama no humano", "preciso de atendimento"
- **Negociação de preço ou condições** — promoções, descontos, parcelamento

## Escalação recomendada — contexto sensível

Encaminhar para `human_wait` quando:

- O aluno demonstra frustração ou insatisfação, mesmo sem mencionar palavras-chave
- A mensagem é ambígua e pode envolver dados sensíveis ou situação delicada
- O aluno quer confirmar informações contratuais (duração, cláusulas, condições)
- Há conflito de agendamento que requer decisão da professora
- O aluno menciona problema de saúde ou situação pessoal relevante para o curso
- A situação foge completamente do fluxo padrão e não há resposta automatizável

## Situações que NÃO requerem escalação imediata

- Dúvidas gerais sobre o curso (respondidas pelo fluxo de FAQ)
- Interesse em aula experimental (encaminhar para `route_payload_trial_class`)
- Interesse em módulo offshore (encaminhar para `route_payload_offshore_interview`)
- Solicitação de diagnóstico ou quiz (encaminhar para `send_quiz`)
- Lead sem nome coletado (encaminhar para `ask_name`)
- Dúvida sobre horário geral (encaminhar para suporte, não para `human_wait` imediato)

## Comportamento esperado após escalação

Quando `human_wait` é ativado:
- O lead recebe mensagem informando que será atendido por um humano
- `needs_human=true` é incluído na resposta ao sistema de execução
- O fluxo automatizado pausa até retomada por humano
- Nenhuma ação adicional é tomada pelo sistema até o handoff ser concluído

## Frases que indicam necessidade de escalação

- "Quero cancelar"
- "Não fui cobrado corretamente"
- "Quero o meu dinheiro de volta"
- "Isso não é o que foi combinado"
- "Estou insatisfeito com o atendimento"
- "Precisa falar com alguém da equipe"
- "Quero falar com a professora"
- "Tem algum desconto?"
- "Posso parcelar?"
- "Qual o valor?"
- "Quanto custa?"
