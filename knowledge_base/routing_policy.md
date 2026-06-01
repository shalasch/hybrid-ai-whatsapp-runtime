# Política de Roteamento — Sinais e Ações

Mapeamento de sinais de mensagem para ações de roteamento. Usado pelo sistema para decidir qual `routing_action` é mais apropriada com base no contexto do lead.

## Ações de roteamento disponíveis

| routing_action | Quando usar |
|---|---|
| `ask_name` | Lead não tem nome coletado |
| `capture_name` | Lead acabou de enviar o nome |
| `send_menu` | Intenção pouco clara, apresentar opções |
| `send_quiz` | Lead demonstrou interesse claro, próximo passo é o diagnóstico |
| `human_wait` | Questão sensível, pagamento, reclamação, pedido explícito de humano |
| `ask_goal` | Lead quer o curso mas não definiu o objetivo |
| `answer_faq` | Pergunta geral respondível pela knowledge base |
| `route_payload_offshore_interview` | Interesse confirmado em inglês offshore/entrevista |
| `route_payload_professional_english` | Interesse em inglês profissional/corporativo |
| `route_payload_general_english` | Interesse em inglês geral/conversação/viagem |
| `route_payload_trial_class` | Solicitação de aula experimental/gratuita |
| `route_payload_student_support` | Aluno ativo com dúvida operacional |
| `route_payload_human_support` | Escalação solicitada ou necessária |

## Mapeamento de frases por categoria

### Interesse em offshore / entrevista offshore

Frases → `route_payload_offshore_interview` ou `send_quiz`:
- "Quero treinar inglês para entrevista offshore"
- "Preciso melhorar meu inglês para trabalhar em plataforma"
- "Vou fazer uma entrevista em inglês para empresa de Oil & Gas"
- "Trabalho embarcado e preciso melhorar meu inglês"
- "Estou buscando vaga offshore e preciso de inglês"
- "Preciso aprender vocabulary de safety briefing"
- "Tenho entrevista em inglês para a petrolífera"
- "Quero treinar inglês técnico de plataforma"

### Interesse em inglês profissional

Frases → `route_payload_professional_english`:
- "Preciso melhorar meu inglês para reuniões de trabalho"
- "Uso inglês no trabalho mas tenho dificuldade"
- "Preciso de inglês para me comunicar com equipes internacionais"
- "Tenho inglês básico mas preciso evoluir para o trabalho"
- "Preciso de inglês para apresentações"

### Interesse em inglês geral ou conversação

Frases → `route_payload_general_english`:
- "Quero aprender inglês do zero"
- "Quero melhorar minha conversação em inglês"
- "Inglês geral, para me virar no dia a dia"
- "Viajo bastante e preciso melhorar meu inglês"
- "Quero falar inglês com mais confiança"

### Solicitação de aula experimental

Frases → `route_payload_trial_class`:
- "Quero a aula experimental"
- "Tem aula gratuita?"
- "Posso experimentar antes de pagar?"
- "Como funciona a aula de teste?"
- "Quero agendar uma aula grátis"
- "Quero conhecer o curso antes de decidir"

### Suporte a aluno existente

Frases → `route_payload_student_support`:
- "Sou aluno e tenho uma dúvida"
- "Preciso reagendar minha aula"
- "Não recebi o link da aula"
- "Tenho dúvida sobre o material enviado"
- "Minha aula é hoje e não sei o horário"

### Escalação para humano

Frases → `human_wait`:
- "Quero cancelar minha matrícula"
- "Tenho um problema com a cobrança"
- "Não fui cobrado corretamente"
- "Quero falar com alguém da equipe"
- "Qual o preço do curso?"
- "Tem desconto?"
- "Quero meu dinheiro de volta"
- "Preciso de atendimento humano"
- "Estou insatisfeito com o curso"

### Dúvida geral — FAQ

Frases → `answer_faq`:
- "As aulas são ao vivo ou gravadas?"
- "Preciso ter experiência offshore para fazer o módulo?"
- "Posso começar do zero?"
- "As aulas são em português ou inglês?"

### Objetivo indefinido

Frases → `ask_goal`:
- "Quero aprender inglês" (sem especificação)
- "Preciso de inglês" (contexto insuficiente)
- "Tenho interesse no curso" (contexto insuficiente)

## Regras de prioridade

1. Se o lead não tem nome → `ask_name` antes de qualquer outra ação
2. Se há sinal de pagamento, reclamação ou escalação explícita → `human_wait` imediatamente
3. Se o interesse é claro e o lead tem nome → `send_quiz` ou `route_payload_*` conforme a trilha
4. Se a intenção é ambígua → `send_menu` para apresentar as opções
5. Se a pergunta é factual e respondível → `answer_faq`
